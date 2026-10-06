"""Database integration tests, isolated in a disposable schema.

BENCHMARK_TEST_DATABASE=1 src/.venv/bin/python -m unittest discover -s tests -p test_benchmark.py
"""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql

spec = importlib.util.spec_from_file_location(
    "benchmark", Path(__file__).resolve().parents[1] / "src/python/benchmark.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipUnless(os.getenv("BENCHMARK_TEST_DATABASE") == "1", "requires local test database")
class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.connection = psycopg.connect(**module.connection_info(), autocommit=True)
        self.addCleanup(self.connection.close)
        self.schema = "benchmark_test_" + uuid.uuid4().hex
        self.connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.addCleanup(lambda: self.connection.execute(
            sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema))))
        with self.connection.transaction():
            self.connection.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(self.schema)))
            self.connection.execute("CREATE TABLE documents (id bigint PRIMARY KEY, full_text_searchvec tsvector)")
            self.connection.execute("CREATE TABLE chunks (id bigint PRIMARY KEY, document_id bigint, content_searchvec tsvector)")
            self.connection.execute("INSERT INTO documents VALUES (1, to_tsvector('english', 'air')), (2, to_tsvector('english', 'water')), (3, NULL)")
            self.connection.execute("INSERT INTO chunks VALUES (1, 1, to_tsvector('english', 'air')), (2, 2, to_tsvector('english', 'air')), (3, 3, NULL)")
            self.connection.execute("CREATE INDEX idx_documents_full_text_searchvec_gin ON documents USING gin (full_text_searchvec)")
            self.connection.execute("CREATE INDEX custom_chunks_search ON chunks USING gin ((coalesce(content_searchvec, ''::tsvector)))")
        self.original = module.target_indexes(self.connection, self.schema)

    def test_measurements_isolate_indexes_and_restore_originals(self):
        result = module.benchmark(self.connection, self.schema)
        self.assertEqual(self.original, module.target_indexes(self.connection, self.schema))
        self.assertEqual(result["variants"]["no_index"]["indexes"], [])
        for variant, measurements in result["variants"].items():
            self.assertEqual(measurements["result_rows_per_run"], [2, 2, 2])
            self.assertEqual(len(measurements["execution_times_ms"]), 3)
            self.assertIn("Plan", measurements["explain"])
            if variant != "no_index":
                self.assertEqual(len(measurements["indexes"]), 2)
                self.assertEqual({index["method"] for index in measurements["indexes"]}, {variant})
        with tempfile.TemporaryDirectory() as directory:
            json_path, report_path = Path(directory) / "benchmark.json", Path(directory) / "benchmark.md"
            json_path.write_text(module.json.dumps(result))
            module.write_report(json_path, report_path)
            self.assertIn("Every run returned 2 document IDs", report_path.read_text())
        # Independent SELECT checks deduplication and ordering on the fixture.
        with self.connection.transaction():
            self.connection.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(self.schema)))
            self.assertEqual(self.connection.execute(module.QUERY).fetchall(), [(1,), (2,)])

    def test_exception_after_ddl_restores_originals(self):
        configure = module.configure_indexes

        def fail_after_index_changes(connection, schema, variant, original):
            configure(connection, schema, variant, original)
            raise RuntimeError("interrupted after index changes")

        with patch.object(module, "configure_indexes", side_effect=fail_after_index_changes):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                module.benchmark(self.connection, self.schema)
        self.assertEqual(self.original, module.target_indexes(self.connection, self.schema))


if __name__ == "__main__":
    unittest.main()
