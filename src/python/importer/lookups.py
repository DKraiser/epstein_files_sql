"""Collect category labels, populate lookup tables, and read their IDs."""

import polars as pl
from psycopg import sql

from ..shared.importer_constants import BATCH_SIZE
from .literals import ParseStatus, MatchStatus, RunStatus, FileStatus, CuratedStatus, CuratedTier, Model
from .parsing import capitalize_document_type, ocr_source

# layer, source field, enum table, label column, optional case conversion
CATEGORIES = (
    ("documents", "dataset", "enum_datasets", "dataset", None),
    ("financial_transactions", "dataset", "enum_datasets", "dataset", None),
    ("documents", "document_type", "enum_document_types", "type", capitalize_document_type),
    ("documents", "ocr_source", "enum_ocr_sources", "source", ocr_source),
    ("entities", "entity_type", "enum_entity_types", "type", None),
    ("persons", "category", "enum_person_categories", "code", None),
    ("kg_entities", "entity_type", "enum_kg_entity_types", "type", None),
    ("kg_relationships", "relationship_type", "enum_relationship_types", "type", None),
    ("derived_events", "track", "enum_event_tracks", "track", None),
    ("derived_events", "event_type", "enum_event_types", "type", None),
    ("derived_events", "confidence", "enum_event_confidences", "label", None),
    ("event_participants", "role", "enum_participant_roles", "role", None),
    ("curated_docs", "subject", "enum_curated_subjects", "subject", None),
)
FIXED = (
    ("enum_parse_statuses", "status_id", "status_code", ParseStatus),
    ("enum_match_statuses", "status_id", "status_code", MatchStatus),
    ("enum_run_statuses", "status_id", "status_code", RunStatus),
    ("enum_file_statuses", "status_id", "status_code", FileStatus),
    ("enum_curated_statuses", "status_id", "status_code", CuratedStatus),
    ("enum_curated_tiers", "id", "tier", CuratedTier),
    ("enum_models", "model_id", "model_name", Model),
)


def populate_lookups(connection, paths):
    """Collect labels and return enum table -> {label: database ID} mappings.

    All lookup inserts share one transaction, before any source layer is loaded.
    Two source fields can contribute to the same table, such as dataset labels.
    """

    labels, columns = {}, {}

    # Each source field contributes distinct labels, not one lookup per row.
    # Normalize before excluding NULL: a missing OCR source becomes Flash Lite
    # and must have an enum row even if every source value was missing.
    for layer, field, table, column, convert in CATEGORIES:
        values = pl.scan_parquet(paths[layer]).select(field).unique().collect()[field]
        labels.setdefault(table, set())
        for value in values:
            label = convert(value) if convert else value
            if label is not None:
                labels[table].add(label)
        columns[table] = column

    result = {}

    with connection.transaction():
        for table, values in labels.items():
            column = columns[table]

            # Filter existing labels before evaluating an identity default.
            insert = sql.SQL("INSERT INTO {} ({}) SELECT %s WHERE NOT EXISTS (SELECT 1 FROM {} WHERE {}=%s)").format(
                sql.Identifier(table), sql.Identifier(column), sql.Identifier(table), sql.Identifier(column))
            
            with connection.cursor() as cursor:
                # Sorting gives stable IDs when starting from empty enum tables.
                cursor.executemany(insert, [(value, value) for value in sorted(values)])

            query = sql.SQL("SELECT {}, id FROM {}").format(sql.Identifier(column), sql.Identifier(table))
            result[table] = dict(connection.execute(query).fetchall())

            if set(result[table]) != values:
                raise ValueError(f"Lookup labels differ from the source: {table}")
            
        # literals.py explicitly assigns IDs. Verify that seed.sql uses those
        # same IDs before any layer writes them into foreign-key columns.
        for table, identifier, column, enum in FIXED:
            query = sql.SQL("SELECT {}, {} FROM {}").format(sql.Identifier(column), sql.Identifier(identifier), sql.Identifier(table))
            actual = dict(connection.execute(query).fetchall())
            expected = {value.value: value.id for value in enum}

            if actual != expected:
                raise ValueError(f"{table} does not match literals.py: expected {expected}, got {actual}")
            
    return result


def load_parents(connection, table, parents):
    """Build dictionaries for later FK matching after a parent layer commits.

    Source IDs are retained, so the ID -> ID maps primarily prove acceptance.
    file_key -> document ID translates a different source key into the same FK.
    """

    if table == "documents":
        parents["documents"], parents["file_keys"] = {}, {}

        with connection.transaction(), connection.cursor(name="document_keys") as cursor:
            # A named cursor fetches BATCH_SIZE rows at a time from PostgreSQL.
            # The dictionaries ultimately retain all keys, but query results do
            # not require a second full-sized list from fetchall().
            cursor.itersize = BATCH_SIZE
            cursor.execute("SELECT id, file_key FROM documents")

            for identifier, key in cursor:
                parents["documents"][identifier] = identifier
                parents["file_keys"][key] = identifier

    elif table in ("kg_entities", "derived_events", "provenance_runs"):
        key = "run_id" if table == "provenance_runs" else "id"
        query = sql.SQL("SELECT {} FROM {}").format(sql.Identifier(key), sql.Identifier(table))
        parents[table] = {row[0]: row[0] for row in connection.execute(query)}
