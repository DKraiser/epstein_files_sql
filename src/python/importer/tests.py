"""Parsing tests and PostgreSQL tests using disposable schemas/Parquet files.

Database component tests do not depend on the task DDL. The complete-pipeline
test executes schema.sql and seed.sql unchanged, and reports a skip if that
external setup is invalid. Run that test again after correcting the SQL.
"""

from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import polars as pl
import psycopg
from psycopg import sql

from ..shared import dataset_passport
from ..shared.importer_constants import SCHEMA_FILE
from . import dates, layers, main
from .journal import Journal
from .literals import Model, ParseStatus, MatchStatus
from .loading import Counts, load_layer
from .lookups import CATEGORIES
from .parsing import amount, json_value, parse_date, parse_hash, parse_json, parse_models

HERE = Path(__file__).parent


class ParsingTests(unittest.TestCase):
    def test_null_empty_invalid_and_partial_dates(self):
        for raw, status in ((None, ParseStatus.NULL), ("", ParseStatus.EMPTY),
                            ("  ", ParseStatus.EMPTY), ("not a date", ParseStatus.FAILED),
                            ("2025-02-30", ParseStatus.FAILED), ("2006", ParseStatus.PARTIAL),
                            ("04/05", ParseStatus.PARTIAL), ("Q1 2000", ParseStatus.PARTIAL)):
            with self.subTest(raw=raw):
                self.assertEqual(dates.parse(raw), (None, status))

    def test_date_formats_and_ordinal_words(self):
        for raw in ("2000-02-13", "02/13/2000", "February 13th, 2000", "13 Feb 2000"):
            with self.subTest(raw=raw):
                self.assertEqual(parse_date(raw), (date(2000, 2, 13), ParseStatus.SUCCESS, None))

    def test_complete_numeric_dates_use_american_month_day_order(self):
        for raw, expected in (("04/05/2000", date(2000, 4, 5)), ("4/5/00", date(2000, 4, 5)),
                              ("04-05-00", date(2000, 4, 5)), ("04.05.2000", date(2000, 4, 5)),
                              ("4,5,00", date(2000, 4, 5)), ("4 5 2000", date(2000, 4, 5)),
                              ("06-04-'09", date(2009, 6, 4)), ("12/31/99", date(1999, 12, 31)),
                              ("02/29/00", date(2000, 2, 29)), ("040500", date(2000, 4, 5)),
                              ("04052000", date(2000, 4, 5)), ("20000405", date(2000, 4, 5)),
                              ("2000/04/05", date(2000, 4, 5)), ("2000.04.05", date(2000, 4, 5))):
            with self.subTest(raw=raw):
                self.assertEqual(dates.parse(raw), (datetime.combine(expected, datetime.min.time()), ParseStatus.SUCCESS))
                self.assertEqual(parse_date(raw), (expected, ParseStatus.SUCCESS, None))
        # An invalid American date cannot become valid by swapping month/day.
        for raw in ("13/02/2000", "02/30/2000", "02/29/01", "00/05/2000"):
            with self.subTest(raw=raw):
                self.assertEqual(dates.parse(raw), (None, ParseStatus.FAILED))

    def test_timestamps_do_not_invent_time_or_timezone(self):
        self.assertEqual(parse_date("2000-02-13", "timestamp"), (None, ParseStatus.PARTIAL, None))
        local = datetime(2000, 2, 13, 15, 1, 2)
        self.assertEqual(parse_date("2000-02-13T15:01:02", "timestamptz"),
                         (None, ParseStatus.PARTIAL, local))
        value, status, local = parse_date("2000-02-13T15:01:02.123456+02:00", "timestamptz")
        self.assertEqual(status, ParseStatus.SUCCESS)
        self.assertEqual(value.microsecond, 123456)
        self.assertEqual(value.utcoffset().total_seconds(), 7200)
        self.assertIsNone(local)

    def test_all_date_conversion_calls_required_parser(self):
        parse_date.cache_clear()
        with patch.object(dates, "parse", return_value=(None, ParseStatus.FAILED)) as parser:
            self.assertEqual(parse_date("probe"), (None, ParseStatus.FAILED, None))
            parser.assert_called_once_with("probe")
        parse_date.cache_clear()

    def test_json_missing_invalid_shape_and_unrepresentable_strings(self):
        for raw, shape, status in ((None, None, ParseStatus.NULL), ("", None, ParseStatus.EMPTY),
                                   ("{", None, ParseStatus.FAILED), ("{}", list, ParseStatus.FAILED),
                                   ("NaN", None, ParseStatus.FAILED),
                                   ('"\\u0000"', None, ParseStatus.FAILED),
                                   ('"\\ud800"', None, ParseStatus.FAILED)):
            with self.subTest(raw=raw):
                self.assertEqual(parse_json(raw, shape), (None, status))

    def test_json_null_and_decimal_precision_are_preserved(self):
        raw = '{"number":0.12345678901234567890123456789,"value":null}'
        value, status = parse_json(raw, dict)
        self.assertEqual(status, ParseStatus.SUCCESS)
        self.assertEqual(value.obj, raw)
        self.assertEqual(json_value(raw)["number"], Decimal("0.12345678901234567890123456789"))
        value, status = parse_json("null")
        self.assertIsNotNone(value)  # JSON null is not SQL NULL.
        self.assertEqual(status, ParseStatus.SUCCESS)

    def test_csv_models_keep_known_tokens_and_report_unknown_tokens(self):
        known, status, unknown = parse_models(" gpt-5-nano,deepseek-chat,gpt-5-nano,unlisted ")
        self.assertEqual(known, [Model.GPT_5_NANO, Model.DEEPSEEK_CHAT, Model.GPT_5_NANO])
        self.assertEqual(status, ParseStatus.PARTIAL)
        self.assertEqual(unknown, ["unlisted"])
        self.assertEqual(parse_models("unlisted"), ([], ParseStatus.FAILED, ["unlisted"]))
        self.assertEqual(parse_models(None), ([], ParseStatus.NULL, []))

    def test_sha256_validation(self):
        self.assertEqual(parse_hash("AB" * 32), (bytes.fromhex("ab" * 32), ParseStatus.SUCCESS))
        self.assertEqual(parse_hash("ab"), (None, ParseStatus.FAILED))
        self.assertEqual(parse_hash(None), (None, ParseStatus.NULL))

    def test_numeric_values_keep_sign_and_reject_nonfinite(self):
        self.assertEqual(amount(-0.123456789), Decimal("-0.123456789"))
        self.assertEqual(amount(None), None)
        for value in (float("nan"), float("inf"), "nonsense"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                amount(value)

    def test_required_and_optional_references(self):
        messages = []
        parents = {"documents": {1: 1}}
        log = lambda *message: messages.append(message)
        self.assertEqual(layers.reference(parents, "documents", 1, "document_id", log), 1)
        self.assertIsNone(layers.reference(parents, "documents", 999, "document_id", log))
        with self.assertRaises(layers.Rejected):
            layers.reference(parents, "documents", 999, "document_id", log, True)
        self.assertEqual(len(messages), 2)

    def test_document_type_case_and_source_record_are_preserved(self):
        messages = []
        row = {"document_type": "eMAIL"}
        layers.category(row, "document_type", "document_type", "enum_document_types",
                        {"enum_document_types": {"Email": 7}}, lambda *args: messages.append(args), str.capitalize)
        self.assertEqual(row, {"document_type": 7})
        self.assertEqual(messages[0][3:], ("eMAIL", "Email", "success"))

    def test_missing_document_ocr_source_resolves_to_flash_lite(self):
        messages = []
        source = {"dataset": "test", "document_type": None, "ocr_source": None,
                  "date": "04/05/00", "created_at": "2000-04-05T12:00:00", "email_fields": None}
        lookups = {"enum_datasets": {"test": 1}, "enum_document_types": {},
                   "enum_ocr_sources": {Model.GEMINI_2_5_FLASH_LITE.value: 37}}
        row, links = layers.documents(source, lookups, {}, lambda *args: messages.append(args))
        # OCR lookup IDs are independent of Model.id. The default must resolve
        # through enum_ocr_sources and keep the original NULL in the journal.
        self.assertEqual(row["ocr_source"], 37)
        self.assertIsNone(source["ocr_source"])
        self.assertEqual(row["date_parsed"], date(2000, 4, 5))
        self.assertEqual(row["date_status"], ParseStatus.SUCCESS.id)
        conversion = next(message for message in messages if message[1] == "ocr_source")
        self.assertEqual(conversion[3:], (None, Model.GEMINI_2_5_FLASH_LITE.value, "success"))
        self.assertEqual(links, [])

    def test_explicit_document_ocr_sources_are_preserved(self):
        source = {"dataset": "test", "document_type": None, "date": None,
                  "created_at": "2000-04-05T12:00:00", "email_fields": None}
        for value in (Model.GEMINI_2_5_FLASH.value, ""):
            with self.subTest(value=value):
                lookups = {"enum_datasets": {"test": 1}, "enum_document_types": {},
                           "enum_ocr_sources": {value: 38, Model.GEMINI_2_5_FLASH_LITE.value: 37}}
                row, _ = layers.documents(dict(source, ocr_source=value), lookups, {}, lambda *args: None)
                self.assertEqual(row["ocr_source"], 38)

    def test_accounting_cannot_silently_lose_rows(self):
        Counts(5, 2, 2, 1).check()
        with self.assertRaises(ValueError):
            Counts(5, 2, 1, 1).check()

    def test_journal_retains_unstorable_original_data(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            journal = Journal(Path(directory))
            original = {"text": "original\x00text", "date": date(2000, 2, 13), "amount": float("nan")}
            journal.for_row({"source_file": "sample.parquet", "source_row": 4, "record": original})(
                "quarantine", None, "Cannot insert")
            journal.close()
            record = json.loads(journal.path.read_text().splitlines()[-1])
            self.assertEqual(record["source_record"]["text"], original["text"])
            self.assertEqual(record["source_row"], 4)
            self.assertEqual(record["source_record"]["amount"], {"nonfinite_float": "nan"})


class DatabaseComponentTests(unittest.TestCase):
    """Exercise real PostgreSQL COPY/savepoints independently of broken task SQL."""

    def setUp(self):
        self.connection = psycopg.connect(main.connection_info(), autocommit=True)
        self.schema = "importer_component_" + uuid4().hex[:12]
        self.connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema)))
        self.connection.execute("CREATE TABLE documents (id BIGINT PRIMARY KEY)")
        self.connection.execute("INSERT INTO documents VALUES (1)")
        self.connection.execute("""CREATE TABLE chunks (id BIGINT PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES documents(id), chunk_index INTEGER,
            token_count INTEGER, char_start INTEGER, char_end INTEGER, content TEXT,
            UNIQUE(document_id, chunk_index))""")
        self.directory = tempfile.TemporaryDirectory(dir=HERE)
        self.root = Path(self.directory.name)
        self.journal = Journal(self.root)

    def tearDown(self):
        self.journal.close()
        self.connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
        self.connection.close()
        self.directory.cleanup()

    def fixture(self, rows):
        path = self.root / "chunks.parquet"
        pl.DataFrame(rows).write_parquet(path)
        return [path]

    def load(self, paths, transform=layers.chunks):
        return load_layer(self.connection, "chunks", transform, paths, {},
                          {"documents": {1: 1}}, self.journal, self.root, batch_size=2)

    def test_duplicates_conflicts_missing_parents_and_nul_accounting(self):
        row = {"id": 1, "document_id": 1, "chunk_index": 0, "token_count": 1,
               "char_start": 0, "char_end": 1, "content": "a"}
        paths = self.fixture([row, dict(row), dict(row, content="conflict"),
                              dict(row, id=2, document_id=999),
                              dict(row, id=3, chunk_index=1, content="a\x00b"),
                              dict(row, id=4, chunk_index=2, content="valid")])
        result = self.load(paths)
        self.assertEqual([result[field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [6, 2, 3, 1])
        self.assertEqual(self.connection.execute("SELECT id FROM chunks ORDER BY id").fetchall(), [(1,), (4,)])
        records = [json.loads(line) for line in self.journal.path.read_text().splitlines()]
        self.assertEqual(sum(record["kind"] == "quarantine" for record in records), 3)
        self.assertEqual(records[-1]["status"], "committed")

    def test_existing_rows_and_new_rows_are_counted_separately(self):
        self.connection.execute("INSERT INTO chunks(id, document_id, chunk_index, content) VALUES(1, 1, 0, 'existing')")
        existing = {"id": 1, "document_id": 1, "chunk_index": 0, "content": "existing"}
        new = dict(existing, id=2, chunk_index=1, content="new")
        paths = self.fixture([existing, new, dict(new)])
        result = self.load(paths)
        self.assertEqual([result[field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [3, 1, 0, 2])
        self.assertEqual(result["existing_rows"], 1)
        self.assertEqual(result["target_rows"], 2)
        repeated = self.load(paths)
        self.assertEqual(repeated["n_accepted"], 0)
        self.assertEqual(repeated["n_duplicate"], 3)
        self.assertEqual(repeated["existing_rows"], 2)
        self.assertEqual(repeated["target_rows"], 2)

    def test_duplicate_model_links_are_verified_and_failure_rolls_back_new_rows(self):
        # An existing parent's raw values match, but one parsed model link is
        # missing. It must not pass verification just because it is a duplicate.
        self.connection.execute("CREATE TABLE provenance_runs(run_id TEXT PRIMARY KEY, model_raw TEXT, model_status SMALLINT)")
        self.connection.execute("""CREATE TABLE provenance_run_models(
            run_id TEXT REFERENCES provenance_runs(run_id), model_id SMALLINT,
            PRIMARY KEY(run_id, model_id))""")
        self.connection.execute("INSERT INTO provenance_runs VALUES('existing', 'gpt-5-nano,deepseek-chat', 1)")
        self.connection.execute("INSERT INTO provenance_run_models VALUES('existing', %s)", (Model.GPT_5_NANO.id,))
        records = [{"run_id": run_id, "model_raw": "gpt-5-nano,deepseek-chat", "model_status": 1}
                   for run_id in ("new", "existing")]
        path = self.root / "runs.parquet"
        pl.DataFrame(records).write_parquet(path)
        def transform(source, lookups, parents, log):
            return dict(source), [(source["run_id"], model.id) for model in (Model.GPT_5_NANO, Model.DEEPSEEK_CHAT)]
        with self.assertRaisesRegex(ValueError, "provenance_run_models links differ"):
            load_layer(self.connection, "provenance/runs", transform, [path], {}, {}, self.journal, self.root)
        # The new run and both of its links roll back; earlier committed data
        # remains available for inspection rather than being silently repaired.
        self.assertEqual(self.connection.execute("SELECT run_id FROM provenance_runs").fetchall(), [("existing",)])
        self.assertEqual(self.connection.execute("SELECT run_id, model_id FROM provenance_run_models").fetchall(),
                         [("existing", Model.GPT_5_NANO.id)])

    def test_interruption_rolls_back_entire_layer_after_completed_batches(self):
        paths = self.fixture([{"id": value, "document_id": 1, "content": str(value)} for value in range(1, 6)])
        visited = 0
        def interrupted(source, lookups, parents, log):
            nonlocal visited
            visited += 1
            if visited == 4:
                raise KeyboardInterrupt()
            return layers.chunks(source, lookups, parents, log)
        with self.assertRaises(KeyboardInterrupt):
            self.load(paths, interrupted)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM chunks").fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM documents").fetchone()[0], 1)
        self.assertEqual(json.loads(self.journal.path.read_text().splitlines()[-1])["status"], "rolled_back")
        # A normal retry reads the source from the beginning and can finish.
        repeated = self.load(paths)
        self.assertEqual(repeated["n_accepted"], 5)
        self.assertEqual(repeated["target_rows"], 5)

    def test_failed_readback_rolls_back_layer(self):
        paths = self.fixture([{"id": 1, "document_id": 1, "content": "valid"}])
        with patch("python.importer.loading.verify_batch", side_effect=ValueError("Readback differs")):
            with self.assertRaisesRegex(ValueError, "Readback differs"):
                self.load(paths)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM chunks").fetchone()[0], 0)

    def test_setup_failure_restores_preexisting_working_tables(self):
        # A seed failure follows a successful destructive schema statement.
        # The setup transaction must restore the original table and row.
        schema_file, seed_file = self.root / "schema.sql", self.root / "seed.sql"
        schema_file.write_text("DROP TABLE chunks; DROP TABLE documents; CREATE TABLE documents(id BIGINT NOT NULL);")
        seed_file.write_text("INSERT INTO documents VALUES(NULL);")
        with patch.object(main, "SCHEMA_FILE", schema_file), patch.object(main, "SEED_FILE", seed_file):
            with self.assertRaises(psycopg.errors.NotNullViolation):
                main.rebuild(self.connection, self.schema)
        self.assertEqual(self.connection.execute("SELECT id FROM documents").fetchall(), [(1,)])
        self.assertEqual(self.connection.execute("SELECT count(*) FROM chunks").fetchone()[0], 0)


class SourceContractTests(unittest.TestCase):
    def test_actual_source_samples_match_every_target_column(self):
        """Check 25 real rows per layer; this does not assert their FKs exist."""
        samples = {layer: pl.scan_parquet(paths[0]).head(25).collect().to_dicts()
                   for layer, paths in dataset_passport.LOCAL_FILES_PATHS.items()}
        lookups = {}
        for layer, field, table, _, convert in CATEGORIES:
            labels = set()
            for row in samples[layer]:
                label = convert(row[field]) if convert else row[field]
                if label is not None:
                    labels.add(label)
            mapping = lookups.setdefault(table, {})
            for label in sorted(labels):
                mapping.setdefault(label, len(mapping) + 1)
        parents = {table: {} for table in ("documents", "file_keys", "kg_entities", "derived_events", "provenance_runs")}
        for records in samples.values():
            for row in records:
                for field, table in (("document_id", "documents"), ("file_key", "file_keys"),
                                    ("source_id", "kg_entities"), ("target_id", "kg_entities"),
                                    ("event_id", "derived_events"), ("run_id", "provenance_runs")):
                    if row.get(field) is not None:
                        parents[table][row[field]] = 1 if table == "file_keys" else row[field]
        ddl = SCHEMA_FILE.read_text()
        for layer, transform in layers.LAYERS:
            table = layer.replace("/", "_")
            # Both ordinary CREATE TABLE and the idempotent IF NOT EXISTS form
            # define the same columns. Allow whitespace and explain a miss.
            definition = re.search(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
                                   + re.escape(table) + r"\s*\((.*?)\n\s*\);", ddl, re.S | re.I)
            self.assertIsNotNone(definition, f"No CREATE TABLE definition found for {table} in {SCHEMA_FILE}")
            body = definition.group(1)
            columns = {match[1] for line in body.splitlines()
                       if (match := re.match(r"\s*([a-z_][a-z_0-9]*)\s+", line))}
            for index, original in enumerate(samples[layer]):
                with self.subTest(layer=layer, row=index):
                    before = dict(original)
                    source = dict(original)
                    if layer == "provenance/files":
                        source.update(id=index + 1, source_file="test.parquet", source_row=index)
                    result, _ = transform(source, lookups, parents, lambda *args: None)
                    self.assertEqual(set(result), columns)
                    self.assertEqual(original, before)


class DatasetIntegrationTests(unittest.TestCase):
    """All 13 layers, model bridges, and a repeat import that retains prior rows."""

    @classmethod
    def setUpClass(cls):
        cls.connection = psycopg.connect(main.connection_info(), autocommit=True)
        cls.schema = "importer_integration_" + uuid4().hex[:12]
        cls.addClassCleanup(cls.cleanup_database)
        try:
            main.rebuild(cls.connection, cls.schema)
        except psycopg.Error as error:
            raise unittest.SkipTest(f"Supplied schema/seed block complete-pipeline testing: {error}") from error
        cls.directory = tempfile.TemporaryDirectory(dir=HERE)
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)

    @classmethod
    def cleanup_database(cls):
        cls.connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(cls.schema)))
        cls.connection.close()

    def fixtures(self):
        # Start with actual source schemas, then force small, coherent IDs and
        # deliberate bad values. No fixture writes outside importer/.
        frames = {layer: pl.scan_parquet(paths[0]).head(1).collect()
                  for layer, paths in dataset_passport.LOCAL_FILES_PATHS.items()}
        rows = {layer: frame.row(0, named=True) for layer, frame in frames.items()}
        docs = dict(rows["documents"], id=1, file_key="doc-one", document_type="eMAIL", date="04/05/00", ocr_source=None,
                    full_text="one", char_count=3, created_at="2000-02-13T15:01:02", email_fields="null")
        second = dict(docs, id=2, file_key="doc-two", document_type="EMAIL", date="12/31/1999",
                      ocr_source=Model.GEMINI_2_5_FLASH.value, email_fields="{")
        rows["documents"] = [docs, second, dict(docs), dict(docs, id=3, file_key="doc-nul", full_text="a\x00b")]
        rows["persons"] = [dict(rows["persons"], id=1, aliases='["Alias"]', search_terms="[]", sources="[")]
        entity = dict(rows["kg_entities"], id=1, metadata='{"number":0.12345678901234567890123456789}')
        rows["kg_entities"] = [entity, dict(entity, id=2, metadata="{")]
        rows["derived_events"] = [dict(rows["derived_events"], id=1, event_date="2006", amount=-0.123456789)]
        rows["provenance/runs"] = [dict(rows["provenance/runs"], run_id="run-test", status="completed",
            started_at="2000-02-13T15:01:02Z", completed_at="2000-02-13T16:01:02", last_heartbeat=None,
            model="gpt-5-nano, deepseek-chat, gpt-5-nano, unlisted")]
        chunk = dict(rows["chunks"], id=1, document_id=1, chunk_index=0, content="chunk")
        rows["chunks"] = [chunk, dict(chunk), dict(chunk, content="conflict"),
                          dict(chunk, id=2, document_id=999), dict(chunk, id=3, document_id=2)]
        entity = dict(rows["entities"], id=1, document_id=1)
        rows["entities"] = [entity, dict(entity, id=2, document_id=999)]
        rows["kg_relationships"] = [dict(rows["kg_relationships"], id=1, source_id=1, target_id=2, metadata="{}")]
        rows["event_participants"] = [dict(rows["event_participants"], id=1, event_id=1)]
        evidence = dict(rows["event_sources"], id=1, event_id=1, file_key="doc-one")
        rows["event_sources"] = [evidence, dict(evidence, id=2, file_key="unmatched")]
        rows["financial_transactions"] = [dict(rows["financial_transactions"], id=1, file_key="doc-one",
            amount=-0.123456789, extraction_model="unlisted", transaction_date="04/05/2000")]
        rows["curated_docs"] = [dict(rows["curated_docs"], id=1, file_key="doc-one", status="gold", tier="HIGH",
                                   also_appears_as="[", doc_date="2000-02-13")]
        file = dict(rows["provenance/files"], file_key="doc-one", run_id="run-test", status="success",
                    model_used="gpt-5-nano, deepseek-chat", pdf_sha256="AB" * 32, output_sha256="bad",
                    first_seen_at="2000-02-13T15:01:02Z", processed_at="2000-02-13T16:01:02")
        rows["provenance/files"] = [file, dict(file, file_key="unmatched", run_id=None, model_used="unlisted")]
        paths = {}
        for layer, records in rows.items():
            path = self.root / (layer.replace("/", "_") + ".parquet")
            pl.DataFrame(records, schema=frames[layer].schema).write_parquet(path)
            paths[layer] = [path]
        return paths

    def snapshot(self):
        tables = self.connection.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename",
                                         (self.schema,)).fetchall()
        return {table: self.connection.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(
            sql.Identifier(table))).fetchall() for (table,) in tables}

    def test_complete_pipeline_and_repeatability(self):
        paths = self.fixtures()
        journal = Journal(self.root)
        self.addCleanup(journal.close)
        reports, foreign_keys = main.import_dataset(self.connection, paths, self.root, journal)
        self.assertEqual(len(reports), 13)
        self.assertGreater(foreign_keys, 50)
        self.assertEqual([reports["documents"][field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [4, 2, 1, 1])
        self.assertEqual([reports["chunks"][field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [5, 2, 2, 1])
        self.assertEqual(reports["provenance/runs"]["model_links"], 2)
        self.assertEqual(reports["provenance/files"]["model_links"], 2)
        self.assertEqual(self.connection.execute("SELECT type FROM enum_document_types").fetchall(), [("Email",)])
        self.assertEqual(self.connection.execute("SELECT document_match_status FROM entities WHERE id=2").fetchone()[0],
                         MatchStatus.UNRESOLVED.id)
        self.assertEqual(self.connection.execute("SELECT metadata_parsed->>'number' FROM kg_entities WHERE id=1").fetchone()[0],
                         "0.12345678901234567890123456789")
        self.assertEqual(self.connection.execute("SELECT email_fields_parsed::text FROM documents WHERE id=1").fetchone()[0], "null")
        self.assertEqual(self.connection.execute("SELECT completed_at_local_parsed FROM provenance_runs").fetchone()[0],
                         datetime(2000, 2, 13, 16, 1, 2))
        first = self.snapshot()
        main.rebuild(self.connection, self.schema)
        self.assertEqual(first, self.snapshot())  # Setup must preserve committed data.
        second, second_fk = main.import_dataset(self.connection, paths, self.root, journal)
        for layer, original in reports.items():
            with self.subTest(layer=layer):
                repeated = second[layer]
                # A repeat has the same source and stored totals, but previously
                # accepted rows are now duplicates rather than new inserts.
                self.assertEqual(repeated["n_read"], original["n_read"])
                self.assertEqual(repeated["n_accepted"], 0)
                self.assertEqual(repeated["n_quarantined"], original["n_quarantined"])
                self.assertEqual(repeated["n_duplicate"], original["n_duplicate"] + original["n_accepted"])
                self.assertEqual(repeated["existing_rows"], original["target_rows"])
                self.assertEqual(repeated["target_rows"], original["target_rows"])
                self.assertEqual(repeated["model_links_added"], 0)
                self.assertEqual(repeated["model_links"], original["model_links"])
        self.assertEqual(foreign_keys, second_fk)
        self.assertEqual(first, self.snapshot())


class ImporterRegressionTests(unittest.TestCase):
    """Check the OCR/date fixes through the real pipeline in a fresh schema."""

    def test_ocr_defaults_and_american_dates_in_postgresql(self):
        connection = psycopg.connect(main.connection_info(), autocommit=True)
        schema = "importer_regression_" + uuid4().hex[:12]
        def cleanup():
            connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connection.close()
        self.addCleanup(cleanup)
        main.rebuild(connection, schema)
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            self.root = Path(directory)
            paths = DatasetIntegrationTests.fixtures(self)
            journal = Journal(self.root)
            try:
                reports, foreign_keys = main.import_dataset(connection, paths, self.root, journal)
            finally:
                journal.close()
        rows = connection.execute("""SELECT d.id, o.source, d.date_raw, d.date_parsed, d.date_status
            FROM documents d JOIN enum_ocr_sources o ON o.id=d.ocr_source ORDER BY d.id""").fetchall()
        self.assertEqual(rows, [(1, Model.GEMINI_2_5_FLASH_LITE.value, "04/05/00", date(2000, 4, 5), ParseStatus.SUCCESS.id),
                               (2, Model.GEMINI_2_5_FLASH.value, "12/31/1999", date(1999, 12, 31), ParseStatus.SUCCESS.id)])
        self.assertEqual(connection.execute("SELECT transaction_date_parsed, transaction_date_status FROM financial_transactions").fetchone(),
                         (date(2000, 4, 5), ParseStatus.SUCCESS.id))
        self.assertEqual(len(reports), 13)
        self.assertGreater(foreign_keys, 50)
