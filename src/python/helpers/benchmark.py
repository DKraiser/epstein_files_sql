"""Benchmark the air FTS query; restore original indexes even on interruption.

Run: src/.venv/bin/python src/python/benchmark.py
Uses POSTGRES_* variables from the environment or the project's .env.
Index changes hold table locks until rollback: run on an idle database.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from statistics import mean, median

from dotenv import load_dotenv
import psycopg
from psycopg import sql
from python.shared.main_constants import PROJECT_ROOT, PROJECT_ENV
from python.shared.importer_constants import IMPORT_SCHEMA


TARGETS = {"documents": "full_text_searchvec", "chunks": "content_searchvec"}
QUERY = """SELECT dc.id
FROM (
    SELECT d.id AS id
    FROM documents AS d
    WHERE d.full_text_searchvec @@ plainto_tsquery('english', 'air')

    UNION

    SELECT c.document_id AS id
    FROM chunks AS c
    WHERE c.content_searchvec @@ plainto_tsquery('english', 'air')
) AS dc
ORDER BY dc.id ASC;"""
EXPLAIN = "EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON) "


def connection_info():
    load_dotenv(PROJECT_ENV)
    return dict(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DBNAME", os.getenv("POSTGRES_DB", "dbs2")),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD"),
        connect_timeout=5,
        application_name="fts_index_benchmark",
    )


def target_indexes(connection, schema):
    """Find vector indexes, including expression indexes and arbitrary names."""
    indexes = []
    for table, column in TARGETS.items():
        rows = connection.execute("""
            SELECT ic.relname, am.amname, pg_get_indexdef(i.indexrelid),
                   i.indisvalid AND i.indisready AND i.indnkeyatts = 1
                   AND i.indnatts = 1 AND i.indpred IS NULL
                   AND i.indexprs IS NULL AND i.indkey[0] = a.attnum AS plain
            FROM pg_index i
            JOIN pg_class t ON t.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_class ic ON ic.oid = i.indexrelid
            JOIN pg_am am ON am.oid = ic.relam
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attname = %s
            WHERE n.nspname = %s AND t.relname = %s
              AND (a.attnum = ANY(i.indkey) OR EXISTS (
                  SELECT 1 FROM pg_depend dep
                  WHERE dep.classid = 'pg_class'::regclass
                    AND dep.objid = i.indexrelid
                    AND dep.refobjid = t.oid AND dep.refobjsubid = a.attnum
              ))
            ORDER BY ic.relname
        """, (column, schema, table)).fetchall()
        indexes.extend(dict(table=table, name=name, method=method,
                            definition=definition, plain=plain)
                       for name, method, definition, plain in rows)
    return indexes


def configure_indexes(connection, schema, variant, original):
    retained = set()
    for index in original:
        expected = f"idx_{index['table']}_{TARGETS[index['table']]}_{variant}"
        if (variant != "no_index" and index["plain"]
                and index["method"] == variant and index["name"] == expected):
            retained.add(index["table"])
        else:
            connection.execute(sql.SQL("DROP INDEX {}").format(
                sql.Identifier(schema, index["name"])))
    if variant != "no_index":
        for table, column in TARGETS.items():
            if table not in retained:
                print(f"Building {variant.upper()} index on {table}.{column}...", flush=True)
                connection.execute(sql.SQL("CREATE INDEX {} ON {} USING {} ({})").format(
                    sql.Identifier(f"idx_{table}_{column}_{variant}"),
                    sql.Identifier(schema, table), sql.SQL(variant), sql.Identifier(column)))
    return target_indexes(connection, schema)


def benchmark(connection, schema):
    started = datetime.now(timezone.utc).isoformat()
    # An outer forced rollback restores every DDL change, also on exceptions.
    with connection.transaction(force_rollback=True):
        connection.execute("SET LOCAL lock_timeout = '10s'")
        connection.execute(sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(
            sql.Identifier(schema)))
        # Stable data and exclusive access to index DDL throughout all variants.
        connection.execute(sql.SQL("LOCK TABLE {}, {} IN ACCESS EXCLUSIVE MODE").format(
            sql.Identifier(schema, "documents"), sql.Identifier(schema, "chunks")))
        for table in TARGETS:
            connection.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(schema, table)))
        original = target_indexes(connection, schema)
        tables = {}
        for table, column in TARGETS.items():
            estimate, size = connection.execute("""
                SELECT reltuples::bigint, pg_table_size(oid)
                FROM pg_class WHERE oid = %s::regclass
            """, (sql.Identifier(schema, table).as_string(connection),)).fetchone()
            tables[table] = {"estimated_rows": estimate, "table_bytes": size, "column": column}
        settings = {name: connection.execute(sql.SQL("SHOW {}").format(sql.Identifier(name))).fetchone()[0]
                    for name in ("work_mem", "shared_buffers", "maintenance_work_mem", "jit",
                                 "max_parallel_workers_per_gather", "enable_seqscan",
                                 "enable_indexscan", "enable_bitmapscan", "random_page_cost",
                                 "effective_cache_size", "statement_timeout")}
        result = {
            "query": QUERY, "started_at": started,
            "postgresql_version": connection.execute("SELECT version()").fetchone()[0],
            "schema": schema, "runs_per_variant": 3, "time_unit": "ms",
            "metric": "PostgreSQL EXPLAIN ANALYZE Execution Time (TIMING OFF)",
            "methodology": {
                "variant_order": ["no_index", "gin", "gist"],
                "warmup_runs": 0, "cache_reset": False,
                "explain_options": "ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON",
                "saved_explain_run": 1, "analyze_before_benchmark": True,
                "planner_forced": False, "index_build_time_included": False,
                "original_indexes_restored_by_rollback": True,
            },
            "tables": tables, "settings": settings, "original_vector_indexes": original,
            "variants": {},
        }
        row_count = None
        for variant in result["methodology"]["variant_order"]:
            # Reuse original GIN indexes if available; undo each variant's DDL.
            with connection.transaction(force_rollback=True):
                print(f"Preparing {variant}...", flush=True)
                indexes = configure_indexes(connection, schema, variant, original)
                runs, counts, first_plan = [], [], None
                for run in range(1, 4):
                    plan = connection.execute(EXPLAIN + QUERY, prepare=False).fetchone()[0][0]
                    duration = plan["Execution Time"]
                    count = int(plan["Plan"]["Actual Rows"])
                    if row_count is None:
                        row_count = count
                    if count != row_count:
                        raise ValueError(f"Result row count changed in {variant} run {run}")
                    runs.append(duration)
                    counts.append(count)
                    if first_plan is None:
                        first_plan = plan
                    print(f"{variant} run {run}/3: {duration:.3f} ms ({count} rows)", flush=True)
                result["variants"][variant] = {
                    "indexes": indexes, "execution_times_ms": runs,
                    "mean_ms": mean(runs), "median_ms": median(runs),
                    "result_rows_per_run": counts, "explain": first_plan,
                }
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


def plan_nodes(node):
    yield node
    for child in node.get("Plans", []):
        yield from plan_nodes(child)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default=IMPORT_SCHEMA)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "observations/benchmark.json")
    args = parser.parse_args()

    with psycopg.connect(**connection_info(), autocommit=True) as connection:
        result = benchmark(connection, args.schema)
        
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(f"Saved measurements: {args.output}", flush=True)


if __name__ == "__main__":
    main()
