"""Compare written rows with transformed source rows, and check every FK."""

from psycopg import sql
from psycopg.types.json import Jsonb

from .parsing import json_value

JSON_COLUMNS = {
    "documents": {"email_fields_parsed"},
    "persons": {"aliases_parsed", "search_terms_parsed", "sources_parsed"},
    "kg_entities": {"metadata_parsed"}, "kg_relationships": {"metadata_parsed"},
    "curated_docs": {"also_appears_as_parsed"},
}
BRIDGES = {
    "provenance_runs": ("provenance_run_models", "run_id"),
    "provenance_files": ("provenance_file_models", "file_id"),
}


def comparable(row, table, stored=False):
    """SQL NULL and JSON null remain distinct during source comparison."""
    result = dict(row)
    for column in JSON_COLUMNS.get(table, ()):
        value = row[column]
        raw = value if stored else value.obj if isinstance(value, Jsonb) else None
        result[column] = (raw is None, json_value(raw) if raw is not None else None)
    for column, value in result.items():
        if isinstance(value, memoryview):
            result[column] = bytes(value)
    return result


def read_rows(connection, table, columns, identifiers):
    key = "run_id" if table == "provenance_runs" else "id"
    selected = []
    for column in columns:
        expression = sql.Identifier(column)
        if column in JSON_COLUMNS.get(table, ()):
            # The text cast gives 'null' for JSON null and None for SQL NULL.
            expression = sql.SQL("{}::text").format(expression)
        selected.append(expression)
    query = sql.SQL("SELECT {} FROM {} WHERE {} = ANY(%s)").format(
        sql.SQL(", ").join(selected), sql.Identifier(table), sql.Identifier(key))
    rows = connection.execute(query, (identifiers,)).fetchall()
    result = {}
    for values in rows:
        row = dict(zip(columns, values))
        result[row[key]] = comparable(row, table, stored=True)
    return result


def identical(connection, table, row):
    key = "run_id" if table == "provenance_runs" else "id"
    stored = read_rows(connection, table, list(row), [row[key]])
    return stored.get(row[key]) == comparable(row, table)


def verify_batch(connection, table, entries):
    """Verify prepared source values/links for new rows and existing duplicates."""
    if not entries:
        return
    key = "run_id" if table == "provenance_runs" else "id"
    identifiers = [entry.values[key] for entry in entries]
    expected = {entry.values[key]: comparable(entry.values, table) for entry in entries}
    actual = read_rows(connection, table, list(entries[0].values), identifiers)
    if actual != expected:
        raise ValueError(f"Stored {table} values differ from accepted source rows")
    if table in BRIDGES:
        bridge, parent_key = BRIDGES[table]
        expected_links = {link for entry in entries for link in entry.models}
        query = sql.SQL("SELECT {}, model_id FROM {} WHERE {} = ANY(%s)").format(
            sql.Identifier(parent_key), sql.Identifier(bridge), sql.Identifier(parent_key))
        actual_links = set(connection.execute(query, (identifiers,)).fetchall())
        if actual_links != expected_links:
            raise ValueError(f"Stored {bridge} links differ from parsed source model lists")


def verify_counts(connection, counts, bridge_counts):
    """Check expected totals, including rows/links committed before this run."""
    for table, expected in {**counts, **bridge_counts}.items():
        actual = connection.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]

        if actual != expected:
            raise ValueError(f"{table} count is {actual}, expected {expected}")


def verify_foreign_keys(connection):
    """Discover all FK columns from PostgreSQL, including status/lookup FKs."""

    if connection.execute("SHOW session_replication_role").fetchone()[0] != "origin":
        raise ValueError("Foreign-key enforcement is disabled")
    
    constraints = connection.execute("""
        SELECT c.oid, c.conname, c.convalidated, child.relname, parent.relname,
               child_ns.nspname, parent_ns.nspname,
               ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(num, ord)
                     JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.num ORDER BY ord),
               ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY k(num, ord)
                     JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.num ORDER BY ord)
        FROM pg_constraint c JOIN pg_class child ON child.oid=c.conrelid
        JOIN pg_namespace child_ns ON child_ns.oid=child.relnamespace
        JOIN pg_class parent ON parent.oid=c.confrelid
        JOIN pg_namespace parent_ns ON parent_ns.oid=parent.relnamespace
        WHERE c.contype='f' AND child_ns.nspname=current_schema()
    """).fetchall()

    mandatory = {("chunks", "document_id", "documents", "id"),
                 ("kg_relationships", "source_id", "kg_entities", "id"),
                 ("kg_relationships", "target_id", "kg_entities", "id"),
                 ("event_participants", "event_id", "derived_events", "id"),
                 ("event_sources", "event_id", "derived_events", "id")}
    
    declared = {(child, a, parent, b) for _, _, _, child, parent, _, _, children, parents in constraints
                for a, b in zip(children, parents)}
    
    if not mandatory <= declared:
        raise ValueError(f"Mandatory FKs missing: {mandatory - declared}")
    
    for oid, name, valid, child, parent, child_schema, parent_schema, children, parents in constraints:
        disabled = connection.execute("SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgconstraint=%s AND tgenabled NOT IN ('O','A'))", (oid,)).fetchone()[0]
        
        if not valid or disabled:
            raise ValueError(f"FK {name} is not validated/enforced")
        
        nonnull = sql.SQL(" AND ").join(sql.SQL("c.{} IS NOT NULL").format(sql.Identifier(a)) for a in children)
        match = sql.SQL(" AND ").join(sql.SQL("c.{}=p.{}").format(sql.Identifier(a), sql.Identifier(b)) for a, b in zip(children, parents))
        query = sql.SQL("SELECT EXISTS (SELECT 1 FROM {} c WHERE {} AND NOT EXISTS (SELECT 1 FROM {} p WHERE {}))").format(
            sql.Identifier(child_schema, child), nonnull, sql.Identifier(parent_schema, parent), match)
        
        if connection.execute(query).fetchone()[0]:
            raise ValueError(f"Orphan records violate FK {name}")
    
    invalid = connection.execute("""SELECT EXISTS (SELECT 1 FROM pg_index i
        JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname=current_schema() AND (i.indisprimary OR i.indisunique)
        AND (NOT i.indisvalid OR NOT i.indisready))""").fetchone()[0]
    
    if invalid:
        raise ValueError("A primary/unique key index is invalid")
    
    return len(constraints)
