"""Benchmark Q3-Q6: one warm-up and three measured runs per index variant.

Run from the project root:
    PYTHONPATH=src src/.venv/bin/python -m python.helpers.ai_confirmation

Prints a comparison table; --output optionally saves timings and JSON plans.
Medians exclude warm-up, planning, setup, index builds and result transfer.
Also tests inserting one copied row, rolling back each insertion separately.
The insertion timing excludes rollback/commit and includes FK/index work.
Q4 compares the same temporary-table query without/with GiST. Constraint
indexes remain; other indexes are removed temporarily. All DDL rolls back.
The benchmark holds table locks, so run it against an idle database.
"""

import argparse
import json
from pathlib import Path
import re
from statistics import median
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Json, Jsonb

from python.helpers.benchmark import connection_info
from python.shared import PROJECT_ROOT
from python.shared.importer_constants import IMPORT_SCHEMA


TABLES = {
    3: ('kg_entities', 'kg_relationships', 'enum_kg_entity_types', 'enum_relationship_types'),
    4: ('financial_transactions',),
    5: ('provenance_files', 'provenance_file_models', 'enum_models'),
    6: ('documents', 'enum_parse_statuses'),
}
INSERT_TARGETS = {
    3: ('kg_relationships', 'TRUE'),
    4: ('q4_index_items', 'TRUE'),
    5: ('provenance_files', 'processed_at_parsed IS NOT NULL'),
    6: ('documents', 'email_fields_status = 1'),
}


def sections(source):
    """Read this project's -- Qn: sections, excluding commented alternatives."""
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    parts = re.split(r'^\s*--\s*Q(\d+)\s*:[^\n]*\n', source, flags=re.M)
    return {int(parts[i]): re.sub(r'^\s*--[^\n]*', '', parts[i + 1], flags=re.M).strip()
            for i in range(1, len(parts), 2)}


def query_spec(source):
    """Separate Q4's setup batch from its search; other queries need no setup."""
    source = re.sub(r'^\s*(?:BEGIN|COMMIT|ROLLBACK)\s*;\s*$', '', source, flags=re.M | re.I)
    if re.search(r'CREATE\s+TEMP(?:ORARY)?\s+TABLE', source, flags=re.I):
        setup, query = source.split('WITH RECURSIVE', 1)
        return setup.strip(), 'WITH RECURSIVE ' + query.strip().rstrip(';')
    return '', source.strip().rstrip(';')


def inventory(connection, schema, tables):
    return connection.execute('''
        SELECT ic.relname, pg_get_indexdef(i.indexrelid),
               EXISTS (SELECT 1 FROM pg_constraint WHERE conindid = i.indexrelid)
        FROM pg_index i
        JOIN pg_class t ON t.oid = i.indrelid
        JOIN pg_namespace ns ON ns.oid = t.relnamespace
        JOIN pg_class ic ON ic.oid = i.indexrelid
        WHERE ns.nspname = %s AND t.relname = ANY(%s)
        ORDER BY ic.relname
    ''', (schema, list(tables))).fetchall()


def plan_summary(node):
    label = ('Parallel ' if node.get('Parallel Aware') else '') + node['Node Type']
    if 'Relation Name' in node:
        label += ' on ' + node['Relation Name']
    if 'Index Name' in node:
        label += ' using ' + node['Index Name']
    labels = [label]
    for child in node.get('Plans', []):
        labels.extend(plan_summary(child))
    return list(dict.fromkeys(labels))


def result_signature(rows, number):
    """Compare full results, ignoring outer order and Q5's model-array order."""
    values = []
    for row in rows:
        row = list(row)
        if number == 5 and row[1] is not None:
            row[1] = sorted(row[1])
        values.append(json.dumps(row, default=str))
    return sorted(values)


def measure(connection, number, query, variant):
    plans = []
    for run in range(4):
        plan = connection.execute(
            'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + query,
            prepare=False).fetchone()[0][0]
        plans.append(plan)
        label = 'warm-up' if run == 0 else f'run {run}/3'
        print(f"Q{number} {variant} {label}: {plan['Execution Time']:.3f} ms", flush=True)
    runs = plans[1:]
    middle = sorted(runs, key=lambda p: p['Execution Time'])[1]
    rows = connection.execute(query, prepare=False).fetchall()
    if any(int(p['Plan']['Actual Rows']) != len(rows) for p in plans):
        raise ValueError(f'Q{number}: result counts changed during benchmark')
    return {
        'warmup': plans[0], 'runs': runs,
        'median_ms': median(p['Execution Time'] for p in runs),
        'plan': middle, 'row_count': len(rows),
    }, result_signature(rows, number)


def insertion_sample(connection, number):
    """Copy a qualifying existing row, using explicit IDs to avoid sequences."""
    table, predicate = INSERT_TARGETS[number]
    cursor = connection.execute(sql.SQL('SELECT * FROM {} WHERE {} ORDER BY id LIMIT 1').format(
        sql.Identifier(table), sql.SQL(predicate)))
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f'Q{number}: no qualifying row to copy from {table}')
    columns = [column.name for column in cursor.description]
    values = list(row)
    values[columns.index('id')] = connection.execute(
        sql.SQL('SELECT max(id) + 1 FROM {}').format(sql.Identifier(table))).fetchone()[0]
    marker = 'ai_confirmation_' + uuid4().hex
    for name in ('file_key', 'source_file'):
        if name in columns:
            values[columns.index(name)] = marker
    for position, column in enumerate(cursor.description):
        if values[position] is not None and column.type_code in (114, 3802):
            values[position] = (Json if column.type_code == 114 else Jsonb)(values[position])
    query = sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING id').format(
        sql.Identifier(table), sql.SQL(', ').join(map(sql.Identifier, columns)),
        sql.SQL(', ').join(sql.Placeholder() for _ in columns))
    return query, values


def measure_insertion(connection, number, sample, variant):
    """Execute one INSERT per run inside a rollback-only savepoint."""
    query, values = sample
    plans = []
    for run in range(4):
        with connection.transaction(force_rollback=True):
            plan = connection.execute(
                sql.SQL('EXPLAIN (ANALYZE, BUFFERS, WAL, FORMAT JSON) ') + query,
                values, prepare=False).fetchone()[0][0]
            if int(plan['Plan']['Actual Rows']) != 1:
                raise ValueError(f'Q{number}: expected exactly one inserted row')
        plans.append(plan)
        label = 'warm-up' if run == 0 else f'run {run}/3'
        print(f"Q{number} {variant} insertion {label}: {plan['Execution Time']:.3f} ms", flush=True)
    runs = plans[1:]
    return {
        'table': INSERT_TARGETS[number][0], 'warmup': plans[0], 'runs': runs,
        'median_ms': median(p['Execution Time'] for p in runs),
        'plan': sorted(runs, key=lambda p: p['Execution Time'])[1],
    }


def benchmark(connection, schema=IMPORT_SCHEMA):
    queries = sections((PROJECT_ROOT / 'src/sql/queries.sql').read_text())
    indexes = sections((PROJECT_ROOT / 'src/sql/proposed_indexes.sql').read_text())
    results = {}
    for number, tables in TABLES.items():
        setup, query = query_spec(queries[number])
        original = inventory(connection, schema, tables)
        with connection.transaction(force_rollback=True):
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            connection.execute("SET LOCAL lock_timeout = '5s'")
            connection.execute(sql.SQL('SET LOCAL search_path TO {}, pg_catalog').format(
                sql.Identifier(schema)))
            connection.execute(sql.SQL('LOCK TABLE {} IN ACCESS EXCLUSIVE MODE').format(
                sql.SQL(', ').join(sql.Identifier(schema, t) for t in sorted(tables))))
            for name, definition, protected in original:
                if not protected:
                    connection.execute(sql.SQL('DROP INDEX {}').format(sql.Identifier(schema, name)))
            if setup:
                connection.execute(setup, prepare=False)
            if number == 4:
                connection.execute('ANALYZE q4_index_items')
            sample = insertion_sample(connection, number)
            baseline, baseline_rows = measure(connection, number, query, 'no index')
            baseline['insertion'] = measure_insertion(connection, number, sample, 'no index')
            connection.execute(indexes[number], prepare=False)
            indexed, indexed_rows = measure(connection, number, query, 'index')
            indexed['insertion'] = measure_insertion(connection, number, sample, 'index')
            if baseline_rows != indexed_rows:
                raise ValueError(f'Q{number}: results differ between index variants')
        if inventory(connection, schema, tables) != original:
            raise ValueError(f'Q{number}: original indexes were not restored')
        results[number] = {'no_index': baseline, 'index': indexed}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', default=IMPORT_SCHEMA)
    parser.add_argument('--output', type=Path, help='Optional JSON output file')
    args = parser.parse_args()
    config = connection_info()
    config['application_name'] = 'ai_confirmation'
    with psycopg.connect(**config, autocommit=True) as connection:
        connection.execute("SET statement_timeout = '120s'")
        results = benchmark(connection, args.schema)
    print('\n| query | no index median time | plan | index median time | plan |')
    print('| --- | ---: | --- | ---: | --- |')
    for number, variants in results.items():
        cells = [f'Q{number}']
        for variant in ('no_index', 'index'):
            entry = variants[variant]
            cells.extend([f"{entry['median_ms']:.3f} ms",
                          '; '.join(plan_summary(entry['plan']['Plan']))])
        print('| ' + ' | '.join(cells) + ' |')
    print('\n| query | insertion table | no index median insert time | index median insert time |')
    print('| --- | --- | ---: | ---: |')
    for number, variants in results.items():
        baseline = variants['no_index']['insertion']
        indexed = variants['index']['insertion']
        print(f"| Q{number} | {baseline['table']} | {baseline['median_ms']:.3f} ms "
              f"| {indexed['median_ms']:.3f} ms |")
    print('\nInsertion times include server FK/index work; exclude setup, planning, rollback and commit.')
    print('\nFull results match; all original indexes were restored.')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + '\n')
        print(f'Saved {args.output}')


if __name__ == '__main__':
    main()
