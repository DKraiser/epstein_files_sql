"""Benchmark the air FTS query; restore original indexes even on interruption.

Run: PYTHONPATH=src src/.venv/bin/python -m python.helpers.benchmark
Uses POSTGRES_* variables from the environment or the project's .env.
Enables pgcrypto. Search and insertion each have one warm-up and three measured
runs per variant. Inserted rows and any temporarily removed conflicts roll back.
Index changes hold table locks until rollback: run on an idle database.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from dotenv import load_dotenv
import psycopg
from psycopg import sql
from python.shared.main_constants import PROJECT_ROOT, PROJECT_ENV
from python.shared.importer_constants import IMPORT_SCHEMA


TARGETS = {"documents": "full_text_searchvec", "chunks": "content_searchvec"}
QUERY = """WITH selected_ids AS (
    WITH params AS (
        SELECT plainto_tsquery('english', 'air') AS query
    )
    SELECT DISTINCT dc.id
    FROM params AS p
    CROSS JOIN LATERAL (
        SELECT d.id AS id
        FROM documents AS d
        WHERE d.full_text_searchvec @@ p.query
        UNION ALL
        SELECT c.document_id AS id
        FROM chunks AS c
        WHERE c.content_searchvec @@ p.query
    ) AS dc
    ORDER BY dc.id ASC
)
SELECT
    digest(string_agg(si.id::TEXT, ', ' ORDER BY si.id), 'sha256')::TEXT AS hash,
    count(*) AS count
FROM selected_ids AS si;"""
EXPLAIN = "EXPLAIN (FORMAT JSON)"
INSERT_QUERY = """INSERT INTO chunks (
    id, document_id, chunk_index, token_count, char_start, char_end,
    content, content_searchvec
) VALUES (
    100000000, 1, 1000000, 0, 0, 0,
    'Some text chunk', to_tsvector('english', 'Some text chunk')
);"""


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
                   AND i.indexprs IS NULL AND i.indkey[0] = a.attnum AS plain,
                   pg_relation_size(i.indexrelid) AS size_bytes
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
                            definition=definition, plain=plain, size_bytes=size_bytes)
                       for name, method, definition, plain, size_bytes in rows)
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


def benchmark_insertion(connection, variant):
    runs = []
    for run in range(4):
        label = "warm-up" if run == 0 else f"run {run}/3"
        # Restore conflicting records and remove the sample after every run.
        with connection.transaction(force_rollback=True):
            connection.execute("""
                DELETE FROM chunks
                WHERE id = 100000000
            """)
            if run == 0:
                plan = connection.execute(EXPLAIN + INSERT_QUERY, prepare=False).fetchone()[0][0]
            before = perf_counter()
            cursor = connection.execute(INSERT_QUERY, prepare=False)
            duration = (perf_counter() - before) * 1000
            if cursor.rowcount != 1:
                raise ValueError(f"Expected one inserted row in {variant} insertion {label}")
        if run == 0:
            print(f"{variant} insertion warm-up complete", flush=True)
        else:
            runs.append(duration)
            print(f"{variant} insertion {label}: {duration:.3f} ms", flush=True)
    return {
        "execution_times_ms": runs, "mean_ms": mean(runs), "median_ms": median(runs),
        "explain": plan,
    }


def benchmark(connection, schema):
    started = datetime.now(timezone.utc).isoformat()
    # Initialize outside the forced rollback so pgcrypto stays enabled.
    connection.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")
    crypto_schema = connection.execute("""
        SELECT n.nspname FROM pg_extension e
        JOIN pg_namespace n ON n.oid = e.extnamespace
        WHERE e.extname = 'pgcrypto'
    """).fetchone()[0]
    # An outer forced rollback restores every DDL change, also on exceptions.
    with connection.transaction(force_rollback=True):
        connection.execute("SET LOCAL lock_timeout = '10s'")
        connection.execute(sql.SQL("SET LOCAL search_path TO {}, pg_catalog, {}").format(
            sql.Identifier(schema), sql.Identifier(crypto_schema)))
        # Stable data and exclusive access to index DDL throughout all variants.
        connection.execute(sql.SQL("LOCK TABLE {}, {} IN ACCESS EXCLUSIVE MODE").format(
            sql.Identifier(schema, "documents"), sql.Identifier(schema, "chunks")))
        if connection.execute("SELECT 1 FROM documents WHERE id = 1").fetchone() is None:
            raise ValueError("Insertion benchmark requires documents.id = 1 for chunks.document_id")
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
            "query": QUERY, "insertion_query": INSERT_QUERY, "started_at": started,
            "postgresql_version": connection.execute("SELECT version()").fetchone()[0],
            "schema": schema, "runs_per_variant": 3, "time_unit": "ms",
            "metric": "Client elapsed time for execute and fetchone (perf_counter), including server execution and round trip",
            "methodology": {
                "variant_order": ["no_index", "gin", "gist"],
                "warmup_runs": 1, "cache_reset": False,
                "explain_options": "FORMAT JSON (plan only; does not execute the query)",
                "analyze_before_benchmark": True,
                "planner_forced": False, "index_build_time_included": False,
                "hash_and_count_checked": "Every warm-up and measured run, across all variants",
                "original_indexes_restored_by_rollback": True,
                "insertion_metric": "Client elapsed time for INSERT execute (perf_counter), including server execution and round trip",
                "insertion_setup_and_rollback_included": False,
                "insertion_conflicts": "Temporarily delete conflicting chunk keys; restore by rollback after each run",
            },
            "tables": tables, "settings": settings, "original_vector_indexes": original,
            "variants": {},
        }
        expected_result = None
        for variant in result["methodology"]["variant_order"]:
            # Reuse original GIN indexes if available; undo each variant's DDL.
            with connection.transaction(force_rollback=True):
                print(f"Preparing {variant}...", flush=True)
                indexes = configure_indexes(connection, schema, variant, original)
                plan = connection.execute(EXPLAIN + QUERY, prepare=False).fetchone()[0][0]
                runs, counts, hashes = [], [], []
                for run in range(4):
                    label = "warm-up" if run == 0 else f"run {run}/3"
                    print(f"Starting {variant} {label}...", flush=True)
                    before = perf_counter()
                    query_result = connection.execute(QUERY, prepare=False).fetchone()
                    duration = (perf_counter() - before) * 1000
                    if expected_result is None:
                        expected_result = query_result
                    if query_result != expected_result:
                        raise ValueError(
                            f"Hash/count mismatch in {variant} {label}: "
                            f"expected {expected_result!r}, got {query_result!r}")
                    result_hash, count = query_result
                    if run == 0:
                        warmup = {"hash": result_hash, "count": count}
                        print(f"{variant} warm-up complete ({count} IDs)", flush=True)
                        continue
                    runs.append(duration)
                    counts.append(count)
                    hashes.append(result_hash)
                    print(f"{variant} {label}: {duration:.3f} ms ({count} IDs)", flush=True)
                result["variants"][variant] = {
                    "indexes": indexes,
                    "total_index_bytes": sum(index["size_bytes"] for index in indexes),
                    "warmup": warmup, "execution_times_ms": runs,
                    "mean_ms": mean(runs), "median_ms": median(runs),
                    "result_rows_per_run": counts, "result_hashes_per_run": hashes,
                    "explain": plan,
                    "insertion": benchmark_insertion(connection, variant),
                }
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


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
