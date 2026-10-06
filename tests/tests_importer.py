"""Tests for parsing, loading, source columns, and the complete import pipeline.

Run from the repository root with:
    PYTHONPATH=src src/.venv/bin/python -m unittest python.importer.tests -v

ParsingTests calls Python functions directly, without PostgreSQL.
DatabaseComponentTests uses small tables to isolate loader/transaction behavior.
SourceContractTests reads real Parquet samples and schema.sql without a database.
DatasetIntegrationTests imports small fixtures for every layer using the actual
schema.sql/seed.sql. ImporterRegressionTests checks the OCR/date fixes the same way.

Database tests use the configured PostgreSQL server, but create uniquely named
disposable schemas. Temporary Parquet files and journals stay under importer/.
The complete-pipeline setup reports a skip if the supplied SQL cannot execute;
such a skip does not demonstrate that the complete import works.

unittest discovers methods whose names start with test_. assertEqual compares
actual and expected values; assertRaises checks that an operation fails as
intended. subTest identifies which case failed while continuing other cases.
patch temporarily replaces a function or constant and restores it afterward.
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

from python.shared import dataset_passport
from python.shared.importer_constants import SCHEMA_FILE
from python.shared.text_search_constants import SEARCH_VECTOR_COLUMNS, TEXT_SEARCH_CONFIG, FULL_TEXT_SEARCH_MAX_BYTES
from python.importer import dates, layers, main
from python.importer.journal import Journal
from python.importer.literals import Model, ParseStatus, MatchStatus
from python.importer.loading import Counts, PreparedRow, load_layer
from python.importer.lookups import CATEGORIES
from python.importer.parsing import amount, json_value, parse_date, parse_hash, parse_json, parse_models
from python.importer.verification import verify_batch

# Keep test-generated files beside this module, inside the allowed importer tree.
HERE = Path(__file__).parent


class ParsingTests(unittest.TestCase):
    """Check conversion rules and diagnostics independently of database writes."""

    def test_null_empty_invalid_and_partial_dates(self):
        """Distinguish missing, empty, invalid and incomplete date inputs.

        None is a missing source value; blank strings are empty. Impossible dates
        fail. A year, month/day without a year, or quarter lacks enough information
        for a complete date, so the parser must not invent missing components.
        """
        for raw, status in ((None, ParseStatus.NULL), ("", ParseStatus.EMPTY),
                            ("  ", ParseStatus.EMPTY), ("not a date", ParseStatus.FAILED),
                            ("2025-02-30", ParseStatus.FAILED), ("2006", ParseStatus.PARTIAL),
                            ("04/05", ParseStatus.PARTIAL), ("Q1 2000", ParseStatus.PARTIAL)):
            with self.subTest(raw=raw):
                # All these cases have no complete datetime, but their status
                # must explain why. Checking only the None value would miss that.
                self.assertEqual(dates.parse(raw), (None, status))

    def test_date_formats_and_ordinal_words(self):
        """Accept different written forms of the same complete calendar date.

        ISO, American numeric, named-month and '13th' notation should all become
        February 13, 2000, with SUCCESS rather than PARTIAL or FAILED.
        """
        for raw in ("2000-02-13", "02/13/2000", "February 13th, 2000", "13 Feb 2000"):
            with self.subTest(raw=raw):
                # parse_date returns (parsed value, status, optional local time).
                # A DATE result needs no separate local timestamp, hence None.
                self.assertEqual(parse_date(raw), (date(2000, 2, 13), ParseStatus.SUCCESS, None))

    def test_complete_numeric_dates_use_american_month_day_order(self):
        """Use month/day/year for numeric dates and reject impossible dates.

        April 5 is deliberately ambiguous in '04/05': treating it as May 4 would
        fail this test. Cases also cover separators, short years, leap years,
        compact digits and supported year-first notation.
        """
        for raw, expected in (("04/05/2000", date(2000, 4, 5)), ("4/5/00", date(2000, 4, 5)),
                              ("04-05-00", date(2000, 4, 5)), ("04.05.2000", date(2000, 4, 5)),
                              ("4,5,00", date(2000, 4, 5)), ("4 5 2000", date(2000, 4, 5)),
                              ("06-04-'09", date(2009, 6, 4)), ("12/31/99", date(1999, 12, 31)),
                              ("02/29/00", date(2000, 2, 29)), ("040500", date(2000, 4, 5)),
                              ("04052000", date(2000, 4, 5)), ("20000405", date(2000, 4, 5)),
                              ("2000/04/05", date(2000, 4, 5)), ("2000.04.05", date(2000, 4, 5))):
            with self.subTest(raw=raw):
                # The underlying parser returns a datetime at midnight for a
                # calendar date; the import wrapper extracts a Python date for SQL.
                self.assertEqual(dates.parse(raw), (datetime.combine(expected, datetime.min.time()), ParseStatus.SUCCESS))
                self.assertEqual(parse_date(raw), (expected, ParseStatus.SUCCESS, None))
        # An invalid American date cannot become valid by swapping month/day.
        for raw in ("13/02/2000", "02/30/2000", "02/29/01", "00/05/2000"):
            with self.subTest(raw=raw):
                self.assertEqual(dates.parse(raw), (None, ParseStatus.FAILED))

    def test_timestamps_do_not_invent_time_or_timezone(self):
        """Preserve the distinction between a date, local time and zoned time.

        Date-only input is insufficient for TIMESTAMP. An unzoned datetime is
        insufficient for TIMESTAMPTZ, but its local wall-clock value is retained.
        An explicit offset must survive parsing, including fractional seconds.
        """
        self.assertEqual(parse_date("2000-02-13", "timestamp"), (None, ParseStatus.PARTIAL, None))
        local = datetime(2000, 2, 13, 15, 1, 2)
        self.assertEqual(parse_date("2000-02-13T15:01:02", "timestamptz"),
                         (None, ParseStatus.PARTIAL, local))
        value, status, local = parse_date("2000-02-13T15:01:02.123456+02:00", "timestamptz")
        self.assertEqual(status, ParseStatus.SUCCESS)
        self.assertEqual(value.microsecond, 123456)
        self.assertEqual(value.utcoffset().total_seconds(), 7200)  # +02:00 = 2 hours.
        self.assertIsNone(local)

    def test_all_date_conversion_calls_required_parser(self):
        """Ensure the wrapper delegates a fresh input to dates.parse().

        Replace the parser with a controlled result and inspect its call. Clear
        the wrapper's cache before and after so cached values cannot bypass the
        replacement or leak the mocked result into another test.
        """
        parse_date.cache_clear()
        with patch.object(dates, "parse", return_value=(None, ParseStatus.FAILED)) as parser:
            self.assertEqual(parse_date("probe"), (None, ParseStatus.FAILED, None))
            parser.assert_called_once_with("probe")
        parse_date.cache_clear()

    def test_json_missing_invalid_shape_and_unrepresentable_strings(self):
        """Reject JSON that is invalid or cannot be stored as PostgreSQL JSONB.

        Besides malformed syntax, test an object where a list is required, NaN,
        an escaped NUL and an unpaired Unicode surrogate. The last two are valid
        escape notation but do not represent strings PostgreSQL JSONB can store.
        """
        for raw, shape, status in ((None, None, ParseStatus.NULL), ("", None, ParseStatus.EMPTY),
                                   ("{", None, ParseStatus.FAILED), ("{}", list, ParseStatus.FAILED),
                                   ("NaN", None, ParseStatus.FAILED),
                                   ('"\\u0000"', None, ParseStatus.FAILED),
                                   ('"\\ud800"', None, ParseStatus.FAILED)):
            with self.subTest(raw=raw):
                # A failed parse yields no SQL JSON value, with a diagnostic
                # status distinct from a genuinely missing or empty source value.
                self.assertEqual(parse_json(raw, shape), (None, status))

    def test_json_null_and_decimal_precision_are_preserved(self):
        """Keep exact JSON numeric digits and distinguish JSON null from SQL NULL.

        The Jsonb adapter holds the validated original text, avoiding a float
        conversion that could round the long fraction. JSON literal null must
        still have an adapter; Python None would instead become SQL NULL.
        """
        raw = '{"number":0.12345678901234567890123456789,"value":null}'
        value, status = parse_json(raw, dict)
        self.assertEqual(status, ParseStatus.SUCCESS)
        self.assertEqual(value.obj, raw)  # The adapter carries the original JSON text.
        self.assertEqual(json_value(raw)["number"], Decimal("0.12345678901234567890123456789"))
        value, status = parse_json("null")
        self.assertIsNotNone(value)  # JSON null is not SQL NULL.
        self.assertEqual(status, ParseStatus.SUCCESS)

    def test_csv_models_keep_known_tokens_and_report_unknown_tokens(self):
        """Parse model lists without silently losing unknown or repeated tokens.

        Whitespace is stripped, known models retain source order and repetitions,
        and unknown names are returned separately. A mixed list is PARTIAL; a
        wholly unknown list is FAILED; a missing source list has NULL status.
        """
        known, status, unknown = parse_models(" gpt-5-nano,deepseek-chat,gpt-5-nano,unlisted ")
        self.assertEqual(known, [Model.GPT_5_NANO, Model.DEEPSEEK_CHAT, Model.GPT_5_NANO])
        self.assertEqual(status, ParseStatus.PARTIAL)
        self.assertEqual(unknown, ["unlisted"])
        self.assertEqual(parse_models("unlisted"), ([], ParseStatus.FAILED, ["unlisted"]))
        self.assertEqual(parse_models(None), ([], ParseStatus.NULL, []))

    def test_sha256_validation(self):
        """Convert a 64-character hexadecimal SHA-256 value into 32 bytes.

        Uppercase hex is valid. A short hex string is invalid even though its
        characters are hexadecimal, and None remains a missing hash.
        """
        self.assertEqual(parse_hash("AB" * 32), (bytes.fromhex("ab" * 32), ParseStatus.SUCCESS))
        self.assertEqual(parse_hash("ab"), (None, ParseStatus.FAILED))
        self.assertEqual(parse_hash(None), (None, ParseStatus.NULL))

    def test_numeric_values_keep_sign_and_reject_nonfinite(self):
        """Preserve negative amounts and reject values unsuitable for the importer.

        The expected Decimal uses the input's decimal spelling. NaN, infinity
        and nonnumeric text must raise ValueError so the loader can quarantine
        the source row instead of accepting an unusable amount.
        """
        self.assertEqual(amount(-0.123456789), Decimal("-0.123456789"))
        self.assertEqual(amount(None), None)
        for value in (float("nan"), float("inf"), "nonsense"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                amount(value)

    def test_required_and_optional_references(self):
        """Resolve known parent keys and treat missing parents by requirement.

        An optional unresolved reference returns None; a required one raises
        Rejected. Both failures must be logged, while a successful lookup must
        not add a matching-error diagnostic.
        """
        messages = []
        parents = {"documents": {1: 1}}  # Only document 1 has been accepted.
        log = lambda *message: messages.append(message)
        self.assertEqual(layers.reference(parents, "documents", 1, "document_id", log), 1)
        self.assertIsNone(layers.reference(parents, "documents", 999, "document_id", log))
        with self.assertRaises(layers.Rejected):
            layers.reference(parents, "documents", 999, "document_id", log, True)
        self.assertEqual(len(messages), 2)  # One diagnostic for each lookup of 999.

    def test_document_type_case_and_source_record_are_preserved(self):
        """Match a capitalized document-type label and journal its original case.

        The target row stores lookup ID 7, not the text label. The diagnostic
        retains 'eMAIL' as raw and 'Email' as parsed, documenting the conversion
        even though this category column does not store a raw/parsed/status trio.
        """
        messages = []
        row = {"document_type": "eMAIL"}
        layers.category(row, "document_type", "document_type", "enum_document_types",
                        {"enum_document_types": {"Email": 7}}, lambda *args: messages.append(args), str.capitalize)
        self.assertEqual(row, {"document_type": 7})
        # The first three callback arguments describe kind, column and message;
        # the remaining three carry the raw value, parsed label and status.
        self.assertEqual(messages[0][3:], ("eMAIL", "Email", "success"))

    def test_missing_document_ocr_source_resolves_to_flash_lite(self):
        """Interpret source NULL OCR as Gemini Flash Lite without altering raw data.

        Give the OCR label an arbitrary lookup ID to expose accidental use of
        Model.id. Also check the document's American date and ensure this layer
        returns no provenance model-link pairs.
        """
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
        """Apply the OCR default only to None, leaving explicit labels intact.

        Test both another model name and an explicit empty string. Each maps to
        its own lookup ID 38; neither should be replaced with Flash Lite ID 37.
        The no-op log callback lets this test focus only on the mapped value.
        """
        source = {"dataset": "test", "document_type": None, "date": None,
                  "created_at": "2000-04-05T12:00:00", "email_fields": None}
        for value in (Model.GEMINI_2_5_FLASH.value, ""):
            with self.subTest(value=value):
                lookups = {"enum_datasets": {"test": 1}, "enum_document_types": {},
                           "enum_ocr_sources": {value: 38, Model.GEMINI_2_5_FLASH_LITE.value: 37}}
                row, _ = layers.documents(dict(source, ocr_source=value), lookups, {}, lambda *args: None)
                self.assertEqual(row["ocr_source"], 38)

    def test_accounting_cannot_silently_lose_rows(self):
        """Require every read row to be accepted, quarantined or a duplicate.

        The first set balances: 5 = 2 + 2 + 1. The second accounts for only four
        of five read rows, so Counts.check() must raise rather than permit commit.
        """
        Counts(5, 2, 2, 1).check()
        with self.assertRaises(ValueError):
            Counts(5, 2, 1, 1).check()

    def test_journal_retains_unstorable_original_data(self):
        """Keep rejected source data recoverable even when PostgreSQL rejects it.

        Write a quarantine entry containing NUL text, a date and NaN, then read
        the actual JSONL file. Text must round-trip exactly, source position must
        remain available, and NaN must use the journal's explicit JSON-safe tag.
        """
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            journal = Journal(Path(directory))
            original = {"text": "original\x00text", "date": date(2000, 2, 13), "amount": float("nan")}
            journal.for_row({"source_file": "sample.parquet", "source_row": 4, "record": original})(
                "quarantine", None, "Cannot insert")
            journal.close()  # Flush/close the file before reading its final line.
            record = json.loads(journal.path.read_text().splitlines()[-1])
            self.assertEqual(record["source_record"]["text"], original["text"])
            self.assertEqual(record["source_row"], 4)
            self.assertEqual(record["source_record"]["amount"], {"nonfinite_float": "nan"})


class DatabaseComponentTests(unittest.TestCase):
    """Exercise PostgreSQL COPY, savepoints and verification with minimal tables.

    unittest calls setUp before each test and tearDown afterward, including after
    an assertion failure. Each test therefore starts with one committed parent
    document and an empty chunks table in its own schema.
    """

    def setUp(self):
        """Create this test's connection, isolated tables, files and journal."""
        # Autocommit lets setup statements commit immediately. load_layer still
        # opens an explicit transaction, so its rollback behavior remains real.
        self.connection = psycopg.connect(main.connection_info(), autocommit=True)
        self.schema = "importer_component_" + uuid4().hex[:12]
        # A unique schema avoids collisions with other tests or imported tables.
        # search_path directs the loader's unqualified SQL into that schema.
        self.connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema)))
        self.connection.execute("""CREATE TABLE documents (id BIGINT PRIMARY KEY,
            full_text TEXT, full_text_searchvec TSVECTOR, email_fields_parsed JSONB)""")
        self.connection.execute("INSERT INTO documents(id) VALUES (1)")
        # Keep only the columns/constraints needed to exercise the chunk loader:
        # a primary key, required document FK, and unique document/chunk position.
        self.connection.execute("""CREATE TABLE chunks (id BIGINT PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES documents(id), chunk_index INTEGER,
            token_count INTEGER, char_start INTEGER, char_end INTEGER, content TEXT, content_searchvec TSVECTOR,
            UNIQUE(document_id, chunk_index))""")
        self.directory = tempfile.TemporaryDirectory(dir=HERE)
        self.root = Path(self.directory.name)
        self.journal = Journal(self.root)

    def tearDown(self):
        """Remove only this test's journal, schema, connection and fixtures."""
        self.journal.close()
        # CASCADE removes tables/FKs inside the disposable schema. The schema's
        # UUID-based name, rather than IMPORT_SCHEMA, is the cleanup target.
        self.connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
        self.connection.close()
        self.directory.cleanup()

    def fixture(self, rows):
        """Serialize supplied rows to a real Parquet shard for load_layer().

        Returning a one-element path list matches the loader's shard interface;
        it still runs its usual streaming reads and source-count verification.
        """
        path = self.root / "chunks.parquet"
        pl.DataFrame(rows).write_parquet(path)
        return [path]

    def load(self, paths, transform=layers.chunks):
        """Load chunk fixtures with only document 1 available as a parent.

        A batch size of two forces these small fixtures through multiple batches.
        Tests may supply a replacement transform to interrupt processing midway.
        The empty lookup map suffices because chunks has no enum conversions.
        """
        return load_layer(self.connection, "chunks", transform, paths, {},
                          {"documents": {1: 1}}, self.journal, self.root, batch_size=2)

    def test_duplicates_conflicts_missing_parents_and_nul_accounting(self):
        """Classify six source rows and prove the database/journal match the counts.

        This covers transform-time rejection, SQL rejection and exact duplicates
        together. A bad COPY batch must not prevent its valid rows from being
        accepted through the loader's individual-insert fallback.
        """
        row = {"id": 1, "document_id": 1, "chunk_index": 0, "token_count": 1,
               "char_start": 0, "char_end": 1, "content": "a"}
        # In source order: valid id 1; identical id 1; conflicting id 1;
        # missing parent 999; PostgreSQL-incompatible NUL text; valid id 4.
        paths = self.fixture([row, dict(row), dict(row, content="conflict"),
                              dict(row, id=2, document_id=999),
                              dict(row, id=3, chunk_index=1, content="a\x00b"),
                              dict(row, id=4, chunk_index=2, content="valid")])
        result = self.load(paths)
        # Outcomes: 6 read = 2 accepted (ids 1,4) + 3 quarantined + 1 duplicate.
        self.assertEqual([result[field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [6, 2, 3, 1])
        # Counters alone could be wrong even if they balance. Inspect committed
        # rows and durable journal entries as independent evidence of the outcome.
        self.assertEqual(self.connection.execute("SELECT id FROM chunks ORDER BY id").fetchall(), [(1,), (4,)])
        records = [json.loads(line) for line in self.journal.path.read_text().splitlines()]
        self.assertEqual(sum(record["kind"] == "quarantine" for record in records), 3)
        self.assertEqual(records[-1]["status"], "committed")

    def test_existing_rows_and_new_rows_are_counted_separately(self):
        """Include previously committed rows in totals without counting them as new.

        Start with one stored chunk. Import its duplicate and two copies of a new
        chunk, then repeat the same import. This reproduces the bug where final
        counts used only new accepts and incorrectly expected an empty table.
        """
        self.connection.execute("INSERT INTO chunks(id, document_id, chunk_index, content) VALUES(1, 1, 0, 'existing')")
        existing = {"id": 1, "document_id": 1, "chunk_index": 0, "content": "existing"}
        new = dict(existing, id=2, chunk_index=1, content="new")
        paths = self.fixture([existing, new, dict(new)])
        result = self.load(paths)
        # First import: old row is a duplicate, new row is accepted once, and its
        # second occurrence is a duplicate. Baseline 1 + accepted 1 = stored 2.
        self.assertEqual([result[field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [3, 1, 0, 2])
        self.assertEqual(result["existing_rows"], 1)
        self.assertEqual(result["target_rows"], 2)
        # The preexisting row had no vector. An identical duplicate fills it
        # while retaining the row's duplicate classification and stored total.
        self.assertEqual(self.connection.execute("SELECT content_searchvec::text FROM chunks WHERE id=1").fetchone()[0],
                         "'exist':1")
        repeated = self.load(paths)
        # Second import: all three source rows match existing rows. The baseline
        # is now 2, so zero new accepts still means the expected table total is 2.
        self.assertEqual(repeated["n_accepted"], 0)
        self.assertEqual(repeated["n_duplicate"], 3)
        self.assertEqual(repeated["existing_rows"], 2)
        self.assertEqual(repeated["target_rows"], 2)

    def test_document_and_chunk_search_vectors_and_repeatability(self):
        """Generate English vectors, repair old vectors and avoid redundant writes.

        Run the same checks for both configured text columns. First import tests
        SQL conversion; second import repairs deliberately damaged vectors; third
        import checks that already-correct vectors leave row versions unchanged.
        """
        # Exercise COPY, duplicate backfill and nullable/empty chunk text. Set a
        # different session default to prove the importer explicitly uses English.
        self.connection.execute("SET default_text_search_config = 'pg_catalog.simple'")
        for table, (text_column, vector_column) in SEARCH_VECTOR_COLUMNS.items():
            with self.subTest(table=table):
                texts = ["The cats are running.", "", None] if table == "chunks" else ["The cats are running.", ""]
                records = [{"id": index + 2, text_column: text} for index, text in enumerate(texts)]
                # IDs start at 2 to leave the setup's document 1 intact. Chunks
                # need that parent FK; document comparison needs its JSON field.
                if table == "chunks":
                    for row in records:
                        row["document_id"] = 1
                else:
                    for row in records:
                        row["email_fields_parsed"] = None
                path = self.root / (table + ".parquet")
                pl.DataFrame(records).write_parquet(path)
                def transform(source, lookups, parents, log):
                    # Values are already in target-column form. An identity
                    # transform isolates SQL vector generation from parsing.
                    return dict(source), []
                result = load_layer(self.connection, table, transform, [path], {}, {}, self.journal, self.root)
                self.assertEqual(result["n_accepted"], len(records))
                query = sql.SQL("SELECT {}, {}::text FROM {} WHERE id >= 2 ORDER BY id").format(
                    sql.Identifier(text_column), sql.Identifier(vector_column), sql.Identifier(table))
                # English removes 'The'/'are' and stems cats/running to cat/run,
                # retaining their original positions 2 and 4. Original text stays
                # unchanged. Empty text yields an empty vector, NULL yields NULL.
                expected = [(texts[0], "'cat':2 'run':4"), ("", "")]
                if table == "chunks":
                    expected.append((None, None))
                self.assertEqual(self.connection.execute(query).fetchall(), expected)

                # Simulate data loaded before this feature, plus a stale vector.
                self.connection.execute(sql.SQL("UPDATE {} SET {} = NULL WHERE id = 2").format(
                    sql.Identifier(table), sql.Identifier(vector_column)))
                self.connection.execute(sql.SQL("UPDATE {} SET {} = 'stale'::tsvector WHERE id = 3").format(
                    sql.Identifier(table), sql.Identifier(vector_column)))
                repeated = load_layer(self.connection, table, transform, [path], {}, {}, self.journal, self.root)
                self.assertEqual(repeated["n_accepted"], 0)
                self.assertEqual(repeated["n_duplicate"], len(records))
                self.assertEqual(self.connection.execute(query).fetchall(), expected)
                # A further rerun preserves both values and PostgreSQL row
                # versions: correct vectors do not cause unnecessary UPDATEs.
                version_query = sql.SQL("SELECT id, xmin::text FROM {} ORDER BY id").format(sql.Identifier(table))
                # xmin identifies the transaction that created the stored row
                # version. A redundant UPDATE would create a new version even
                # if the visible text/vector values remained equal.
                versions = self.connection.execute(version_query).fetchall()
                load_layer(self.connection, table, transform, [path], {}, {}, self.journal, self.root)
                self.assertEqual(self.connection.execute(version_query).fetchall(), versions)

    def test_document_search_limit_uses_bytes_and_preserves_text_on_rerun(self):
        """Keep documents above 1 MiB while omitting only their search vectors.

        Test just below, exactly at and just above the cutoff, plus UTF-8 text
        whose byte length exceeds the limit despite fewer than 1 MiB characters.
        The boundary strings use spaces after 'cat', keeping their expected vector
        simple. A rerun must repair stale vectors without duplicating any document.
        """
        limit = FULL_TEXT_SEARCH_MAX_BYTES
        exact = "cat" + " " * (limit - 3)
        texts = [exact[:-1], exact, exact + " ", "cat" + "é" * (limit // 2)]
        records = [{"id": index + 2, "full_text": text, "email_fields_parsed": None}
                   for index, text in enumerate(texts)]
        path = self.root / "documents.parquet"
        pl.DataFrame(records).write_parquet(path)

        def transform(source, lookups, parents, log):
            # Values already match the minimal document table's columns. Keep
            # parsing out of this test so it checks the loader's SQL size policy.
            return dict(source), []

        def load_documents():
            return load_layer(self.connection, "documents", transform, [path], {}, {}, self.journal, self.root)

        result = load_documents()
        self.assertEqual([result[field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [4, 4, 0, 0])
        query = ("SELECT full_text, octet_length(full_text), full_text_searchvec::text "
                 "FROM documents WHERE id >= 2 ORDER BY id")
        expected = [(text, len(text.encode("utf-8")), "'cat':1" if index < 2 else "")
                    for index, text in enumerate(texts)]
        self.assertEqual(self.connection.execute(query).fetchall(), expected)
        # This case catches a mistaken len(text) cutoff instead of byte size.
        self.assertLess(len(texts[-1]), limit)
        self.assertGreater(len(texts[-1].encode("utf-8")), limit)

        # Diagnostics explain both deliberate omissions. The original text is
        # still stored and all four rows remain accepted, never quarantined.
        self.journal.stream.flush()
        journal = [json.loads(line) for line in self.journal.path.read_text().splitlines()]
        skipped = [record for record in journal if record["kind"] == "search_vector_skipped"]
        self.assertEqual([record["source_id"] for record in skipped], [4, 5])

        # An oversized document with a nonempty vector violates the policy even
        # if that vector would otherwise be a valid PostgreSQL tsvector value.
        self.connection.execute("UPDATE documents SET full_text_searchvec = 'stale'::tsvector WHERE id >= 2")
        with self.assertRaisesRegex(ValueError, "documents search vectors differ"):
            verify_batch(self.connection, "documents", [PreparedRow(records[2], [], {})])
        repeated = load_documents()
        self.assertEqual(repeated["n_accepted"], 0)
        self.assertEqual(repeated["n_duplicate"], 4)
        self.assertEqual(self.connection.execute(query).fetchall(), expected)

        # The new cutoff applies only to document full text. Even an oversized
        # chunk still follows its existing conversion rule and indexes 'cat'.
        chunk_path = self.fixture([{"id": 1, "document_id": 1, "content": texts[2]}])
        self.assertEqual(self.load(chunk_path)["n_accepted"], 1)
        self.assertEqual(self.connection.execute("SELECT content_searchvec::text FROM chunks WHERE id=1").fetchone()[0],
                         "'cat':1")

    def test_incorrect_vector_is_detected_and_duplicate_backfill_rolls_back(self):
        """Reject an incorrect vector and undo a repair if layer verification fails.

        The source text matches the existing chunk, but its vector is wrong.
        Check the real verifier first, then force a verification failure during
        loading to prove the duplicate's vector UPDATE remains transactional.
        """
        self.connection.execute("INSERT INTO chunks(id, document_id, content, content_searchvec) "
                                "VALUES(1, 1, 'running cats', 'wrong'::tsvector)")
        row = {"id": 1, "document_id": 1, "content": "running cats"}
        # PreparedRow carries source-derived columns, model links and a location.
        # Direct verification needs no links or journal location for this chunk.
        entry = PreparedRow(row, [], {})
        with self.assertRaisesRegex(ValueError, "chunks search vectors differ"):
            verify_batch(self.connection, "chunks", [entry])
        # Even a repair to an existing duplicate belongs to the active layer.
        # Failure after that UPDATE restores its previous committed vector.
        paths = self.fixture([row])
        with patch("python.importer.loading.verify_batch", side_effect=ValueError("Readback differs")):
            with self.assertRaisesRegex(ValueError, "Readback differs"):
                self.load(paths)
        self.assertEqual(self.connection.execute("SELECT content_searchvec::text FROM chunks WHERE id=1").fetchone()[0],
                         "'wrong'")

    def test_duplicate_model_links_are_verified_and_failure_rolls_back_new_rows(self):
        """Detect incomplete model bridges even when the parent row is identical.

        Both fixture runs require two model links. The stored 'existing' run has
        only one. Verification must fail and undo the newly inserted run/links,
        while preserving the earlier incomplete data for inspection.
        """
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
        # Put 'new' first so the test can prove verification rolls back writes
        # already made before encountering the existing parent's missing link.
        path = self.root / "runs.parquet"
        pl.DataFrame(records).write_parquet(path)
        def transform(source, lookups, parents, log):
            # Model parsing is tested separately. Supply its expected two pairs
            # here to isolate bridge insertion and bridge readback verification.
            return dict(source), [(source["run_id"], model.id) for model in (Model.GPT_5_NANO, Model.DEEPSEEK_CHAT)]
        with self.assertRaisesRegex(ValueError, "provenance_run_models links differ"):
            load_layer(self.connection, "provenance/runs", transform, [path], {}, {}, self.journal, self.root)
        # The new run and both of its links roll back; earlier committed data
        # remains available for inspection rather than being silently repaired.
        self.assertEqual(self.connection.execute("SELECT run_id FROM provenance_runs").fetchall(), [("existing",)])
        self.assertEqual(self.connection.execute("SELECT run_id, model_id FROM provenance_run_models").fetchall(),
                         [("existing", Model.GPT_5_NANO.id)])

    def test_interruption_rolls_back_entire_layer_after_completed_batches(self):
        """Simulate Ctrl+C after a successful batch and retry the same source.

        With batches of two, rows 1 and 2 have already been written when the
        fourth transformation raises KeyboardInterrupt. They must still roll
        back because a completed batch savepoint is not a committed layer.
        """
        paths = self.fixture([{"id": value, "document_id": 1, "content": str(value)} for value in range(1, 6)])
        visited = 0
        def interrupted(source, lookups, parents, log):
            nonlocal visited
            # This closure counts visits across batches in the same load call.
            # Throw at visit 4 before invoking the normal transform for that row.
            visited += 1
            if visited == 4:
                raise KeyboardInterrupt()
            return layers.chunks(source, lookups, parents, log)
        with self.assertRaises(KeyboardInterrupt):
            self.load(paths, interrupted)
        # The active chunk layer disappears; the parent from setUp was committed
        # earlier and survives. The final journal marker must report rollback.
        self.assertEqual(self.connection.execute("SELECT count(*) FROM chunks").fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM documents").fetchone()[0], 1)
        self.assertEqual(json.loads(self.journal.path.read_text().splitlines()[-1])["status"], "rolled_back")
        # A normal retry reads the source from the beginning and can finish.
        repeated = self.load(paths)
        self.assertEqual(repeated["n_accepted"], 5)
        self.assertEqual(repeated["target_rows"], 5)

    def test_failed_readback_rolls_back_layer(self):
        """Undo an otherwise valid insert when post-write verification fails.

        Replace only the verifier, allowing the real COPY/vector writes to run.
        A ValueError during readback must propagate and leave no committed chunk,
        rather than accepting data whose stored values could not be verified.
        """
        paths = self.fixture([{"id": 1, "document_id": 1, "content": "valid"}])
        with patch("python.importer.loading.verify_batch", side_effect=ValueError("Readback differs")):
            with self.assertRaisesRegex(ValueError, "Readback differs"):
                self.load(paths)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM chunks").fetchone()[0], 0)

    def test_setup_failure_restores_preexisting_working_tables(self):
        """Prove schema setup and seeding belong to one atomic transaction.

        Substitute temporary SQL files: setup drops the test tables and recreates
        documents, then seed deliberately violates NOT NULL. Rolling back setup
        must restore the original tables and their previously committed row.
        """
        # A seed failure follows a successful destructive schema statement.
        # The setup transaction must restore the original table and row.
        schema_file, seed_file = self.root / "schema.sql", self.root / "seed.sql"
        schema_file.write_text("DROP TABLE chunks; DROP TABLE documents; CREATE TABLE documents(id BIGINT NOT NULL);")
        seed_file.write_text("INSERT INTO documents VALUES(NULL);")
        # Only module constants are temporarily redirected; the repository's SQL
        # files and the user's working schema are never the destructive target.
        with patch.object(main, "SCHEMA_FILE", schema_file), patch.object(main, "SEED_FILE", seed_file):
            with self.assertRaises(psycopg.errors.NotNullViolation):
                main.rebuild(self.connection, self.schema)
        self.assertEqual(self.connection.execute("SELECT id FROM documents").fetchall(), [(1,)])
        self.assertEqual(self.connection.execute("SELECT count(*) FROM chunks").fetchone()[0], 0)


class SourceContractTests(unittest.TestCase):
    """Check that real source shapes still match the importer's SQL column contract."""

    def test_actual_source_samples_match_every_target_column(self):
        """Transform 25 real rows per layer and compare column names with the DDL.

        Synthetic lookup/parent maps permit transformations without PostgreSQL.
        This catches missing or unexpected target fields and mutation of source
        dictionaries; it does not establish that references exist in the complete
        dataset, that values satisfy SQL constraints, or that every row imports.
        """
        # Read only the first shard/sample for each layer, keeping this a small
        # contract check rather than a full-corpus import or expensive scan.
        samples = {layer: pl.scan_parquet(paths[0]).head(25).collect().to_dicts()
                   for layer, paths in dataset_passport.LOCAL_FILES_PATHS.items()}
        lookups = {}
        # Reproduce the loader's category normalization, including NULL OCR's
        # default, but assign arbitrary local IDs. Some enum tables receive
        # categories from more than one layer, so retain their existing mapping.
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
        # Pretend every sampled reference resolves. File keys need an integer
        # document ID; direct ID references can map to themselves. These maps
        # isolate column construction from the actual dataset's FK coverage.
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
            # Extract the first identifier on each column-definition line from
            # the current DDL layout. This is a targeted check, not a general SQL
            # parser; table-level UNIQUE/PRIMARY KEY lines are not column names.
            columns = {match[1] for line in body.splitlines()
                       if (match := re.match(r"\s*([a-z_][a-z_0-9]*)\s+", line))}
            for index, original in enumerate(samples[layer]):
                with self.subTest(layer=layer, row=index):
                    before = dict(original)
                    source = dict(original)
                    if layer == "provenance/files":
                        # This source has no ID; the loader normally supplies a
                        # stable ordinal and shard/row location before transforming.
                        source.update(id=index + 1, source_file="test.parquet", source_row=index)
                    result, _ = transform(source, lookups, parents, lambda *args: None)
                    # Search vectors are derived by SQL after COPY, so they
                    # supplement the Python transform rather than source data.
                    derived = {SEARCH_VECTOR_COLUMNS[table][1]} if table in SEARCH_VECTOR_COLUMNS else set()
                    self.assertEqual(set(result) | derived, columns)
                    # Retaining the untouched source matters for quarantine and
                    # diagnostics, so transformations must operate on copies.
                    self.assertEqual(original, before)


class DatasetIntegrationTests(unittest.TestCase):
    """Test all 13 layers together with the actual task schema and seed data.

    Unlike the component tests, these fixtures exercise real enum tables, all
    declared foreign keys, layer ordering, parsing and provenance model bridges.
    Small source files include successful, partial, duplicate and rejected rows.
    """

    @classmethod
    def setUpClass(cls):
        """Set up one disposable schema and fixture directory for this class.

        unittest calls this once before the class's tests. Registered class
        cleanups also run if setup is skipped after the connection is created.
        """
        cls.connection = psycopg.connect(main.connection_info(), autocommit=True)
        cls.schema = "importer_integration_" + uuid4().hex[:12]
        cls.addClassCleanup(cls.cleanup_database)
        try:
            # Execute the repository SQL without patching it. If that SQL is
            # invalid, report a skip explicitly instead of testing invented DDL.
            main.rebuild(cls.connection, cls.schema)
        except psycopg.Error as error:
            raise unittest.SkipTest(f"Supplied schema/seed block complete-pipeline testing: {error}") from error
        cls.directory = tempfile.TemporaryDirectory(dir=HERE)
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)

    @classmethod
    def cleanup_database(cls):
        """Remove this class's disposable schema and close its connection."""
        cls.connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(cls.schema)))
        cls.connection.close()

    def fixtures(self):
        """Build small Parquet files with real source types and controlled values.

        Starting from one real row retains fields not relevant to each scenario.
        Override IDs and parent keys to make the accepted rows mutually coherent,
        then introduce specific errors whose expected outcomes are asserted below.
        The regression test also reuses this helper with its own root directory.
        """
        # Start with actual source schemas, then force small, coherent IDs and
        # deliberate bad values. No fixture writes outside importer/.
        frames = {layer: pl.scan_parquet(paths[0]).head(1).collect()
                  for layer, paths in dataset_passport.LOCAL_FILES_PATHS.items()}
        rows = {layer: frame.row(0, named=True) for layer, frame in frames.items()}
        # Documents: two distinct valid SQL rows, one exact duplicate and one
        # NUL-containing row rejected by PostgreSQL. Invalid email JSON in the
        # second document marks that field FAILED without rejecting the document.
        # Mixed-case document types converge to Email; OCR NULL takes the default.
        docs = dict(rows["documents"], id=1, file_key="doc-one", document_type="eMAIL", date="04/05/00", ocr_source=None,
                    full_text="one", char_count=3, created_at="2000-02-13T15:01:02", email_fields="null")
        second = dict(docs, id=2, file_key="doc-two", document_type="EMAIL", date="12/31/1999",
                      ocr_source=Model.GEMINI_2_5_FLASH.value, email_fields="{")
        rows["documents"] = [docs, second, dict(docs), dict(docs, id=3, file_key="doc-nul", full_text="a\x00b")]
        # Persons: valid list fields alongside malformed sources JSON. The raw
        # invalid value must survive with a failed status instead of being lost.
        rows["persons"] = [dict(rows["persons"], id=1, aliases='["Alias"]', search_terms="[]", sources="[")]
        # Two KG parents permit a valid relationship below. One metadata object
        # contains many decimal digits; the other's malformed JSON tests raw/status.
        entity = dict(rows["kg_entities"], id=1, metadata='{"number":0.12345678901234567890123456789}')
        rows["kg_entities"] = [entity, dict(entity, id=2, metadata="{")]
        # A year alone is only a partial event date. Negative amounts remain valid.
        rows["derived_events"] = [dict(rows["derived_events"], id=1, event_date="2006", amount=-0.123456789)]
        # The run starts with an explicit zone but completes in local time. Its
        # repeated known model must create one bridge pair per distinct model;
        # the unknown token makes model parsing PARTIAL and is journaled.
        rows["provenance/runs"] = [dict(rows["provenance/runs"], run_id="run-test", status="completed",
            started_at="2000-02-13T15:01:02Z", completed_at="2000-02-13T16:01:02", last_heartbeat=None,
            model="gpt-5-nano, deepseek-chat, gpt-5-nano, unlisted")]
        chunk = dict(rows["chunks"], id=1, document_id=1, chunk_index=0, content="chunk")
        # Chunks: accept ids 1/3, classify an exact repeat as duplicate, quarantine
        # a conflicting primary key and a required reference to missing document 999.
        rows["chunks"] = [chunk, dict(chunk), dict(chunk, content="conflict"),
                          dict(chunk, id=2, document_id=999), dict(chunk, id=3, document_id=2)]
        entity = dict(rows["entities"], id=1, document_id=1)
        # Entity document references are optional: retain the second entity with
        # an unresolved status rather than quarantine it like the missing-parent chunk.
        rows["entities"] = [entity, dict(entity, id=2, document_id=999)]
        # Relationships/participants exercise required references to parents
        # accepted in earlier layers: KG entities 1/2 and event 1 respectively.
        rows["kg_relationships"] = [dict(rows["kg_relationships"], id=1, source_id=1, target_id=2, metadata="{}")]
        rows["event_participants"] = [dict(rows["event_participants"], id=1, event_id=1)]
        evidence = dict(rows["event_sources"], id=1, event_id=1, file_key="doc-one")
        # Event-source document matching is optional: an unmatched file key stays
        # as source evidence with an unresolved document rather than losing the row.
        rows["event_sources"] = [evidence, dict(evidence, id=2, file_key="unmatched")]
        # Financial dates use American order. Unknown extraction models receive
        # a failed field status while preserving the transaction and raw model.
        rows["financial_transactions"] = [dict(rows["financial_transactions"], id=1, file_key="doc-one",
            amount=-0.123456789, extraction_model="unlisted", transaction_date="04/05/2000")]
        # Curated rows resolve a required document, normalize HIGH to its enum,
        # and retain malformed list JSON with a failed parsing status.
        rows["curated_docs"] = [dict(rows["curated_docs"], id=1, file_key="doc-one", status="gold", tier="HIGH",
                                   also_appears_as="[", doc_date="2000-02-13")]
        # Provenance files cover known model bridges, valid/invalid hashes, zoned
        # and unzoned timestamps, and optional unresolved document/run references.
        # The second row has no run ID; it does not claim a missing required run.
        file = dict(rows["provenance/files"], file_key="doc-one", run_id="run-test", status="success",
                    model_used="gpt-5-nano, deepseek-chat", pdf_sha256="AB" * 32, output_sha256="bad",
                    first_seen_at="2000-02-13T15:01:02Z", processed_at="2000-02-13T16:01:02")
        rows["provenance/files"] = [file, dict(file, file_key="unmatched", run_id=None, model_used="unlisted")]
        paths = {}
        for layer, records in rows.items():
            # Reuse each real Polars schema so None and numeric types match the
            # actual Parquet contract rather than arbitrary inferred fixture types.
            path = self.root / (layer.replace("/", "_") + ".parquet")
            pl.DataFrame(records, schema=frames[layer].schema).write_parquet(path)
            paths[layer] = [path]
        return paths

    def snapshot(self):
        """Capture every table's rows, including enums, bridges and search vectors.

        Restrict table discovery to this test schema. Ordering by each table's
        first column makes comparisons repeatable for this fixture/DDL layout.
        """
        tables = self.connection.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename",
                                         (self.schema,)).fetchall()
        return {table: self.connection.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(
            sql.Identifier(table))).fetchall() for (table,) in tables}

    def test_complete_pipeline_and_repeatability(self):
        """Import every layer, verify representative values, then import again.

        First assert accounting and stored parsing/matching results. Next prove
        setup preserves data and rerunning reclassifies accepted rows as duplicates
        without adding rows or model links. Compare complete table snapshots so
        equal counts cannot hide changed values, enum IDs or bridge pairs.
        """
        paths = self.fixtures()
        journal = Journal(self.root)
        self.addCleanup(journal.close)
        reports, foreign_keys = main.import_dataset(self.connection, paths, self.root, journal)
        # All layers must be reported. The FK threshold catches a schema that
        # accidentally omits many relationships; import_dataset also validates
        # the declared FKs and checks for orphan rows, not just their number.
        self.assertEqual(len(reports), 13)
        self.assertGreater(foreign_keys, 50)
        # Fixture accounting: documents 4 = 2 accepted + 1 quarantined + 1 duplicate;
        # chunks 5 = 2 accepted + 2 quarantined + 1 duplicate.
        self.assertEqual([reports["documents"][field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [4, 2, 1, 1])
        self.assertEqual([reports["chunks"][field] for field in ("n_read", "n_accepted", "n_quarantined", "n_duplicate")],
                         [5, 2, 2, 1])
        self.assertEqual(reports["provenance/runs"]["model_links"], 2)
        self.assertEqual(reports["provenance/files"]["model_links"], 2)
        # Check actual stored values across several independent conversion rules:
        # capitalization, optional document matching, precise JSON numbers, JSON
        # null distinct from SQL NULL, and retention of unzoned completion time.
        self.assertEqual(self.connection.execute("SELECT type FROM enum_document_types").fetchall(), [("Email",)])
        self.assertEqual(self.connection.execute("SELECT document_match_status FROM entities WHERE id=2").fetchone()[0],
                         MatchStatus.UNRESOLVED.id)
        self.assertEqual(self.connection.execute("SELECT metadata_parsed->>'number' FROM kg_entities WHERE id=1").fetchone()[0],
                         "0.12345678901234567890123456789")
        self.assertEqual(self.connection.execute("SELECT email_fields_parsed::text FROM documents WHERE id=1").fetchone()[0], "null")
        self.assertEqual(self.connection.execute("SELECT completed_at_local_parsed FROM provenance_runs").fetchone()[0],
                         datetime(2000, 2, 13, 16, 1, 2))
        for table, (text_column, vector_column) in SEARCH_VECTOR_COLUMNS.items():
            # IS DISTINCT FROM is null-safe. Zero mismatches proves every stored
            # fixture vector agrees with English conversion of its original text.
            self.assertEqual(self.connection.execute(sql.SQL(
                "SELECT count(*) FROM {} WHERE {} IS DISTINCT FROM "
                "pg_catalog.to_tsvector(%s::pg_catalog.regconfig, {})").format(
                    sql.Identifier(table), sql.Identifier(vector_column), sql.Identifier(text_column)),
                (TEXT_SEARCH_CONFIG,)).fetchone()[0], 0)
        first = self.snapshot()
        # rebuild() is the legacy name for setup; current IF NOT EXISTS/seed
        # conflict handling must leave already committed table contents intact.
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
                # Invalid source rows fail again; previously accepted rows join
                # the original duplicates. Baseline/stored totals stay the same.
                self.assertEqual(repeated["n_quarantined"], original["n_quarantined"])
                self.assertEqual(repeated["n_duplicate"], original["n_duplicate"] + original["n_accepted"])
                self.assertEqual(repeated["existing_rows"], original["target_rows"])
                self.assertEqual(repeated["target_rows"], original["target_rows"])
                self.assertEqual(repeated["model_links_added"], 0)
                self.assertEqual(repeated["model_links"], original["model_links"])
        # Counts alone do not establish idempotency. Preserve every stored value
        # and bridge pair, and keep the same verified FK coverage after the rerun.
        self.assertEqual(foreign_keys, second_fk)
        self.assertEqual(first, self.snapshot())


class ImporterRegressionTests(unittest.TestCase):
    """Check the OCR/date fixes through the real pipeline in a fresh schema."""

    def test_ocr_defaults_and_american_dates_in_postgresql(self):
        """Check the OCR/date fixes after real writes into the actual task schema.

        Reuse the all-layer fixtures in a separate disposable schema. Inspect
        resolved OCR labels through their FK, original/parsed date values and
        parsing statuses; a Python-only test would not prove SQL persistence.
        """
        connection = psycopg.connect(main.connection_info(), autocommit=True)
        schema = "importer_regression_" + uuid4().hex[:12]
        def cleanup():
            # Registered cleanup runs after success or an assertion/setup error
            # occurring after registration, and targets only this unique schema.
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
                # Closing the journal also happens if import_dataset raises.
                journal.close()
        rows = connection.execute("""SELECT d.id, o.source, d.date_raw, d.date_parsed, d.date_status
            FROM documents d JOIN enum_ocr_sources o ON o.id=d.ocr_source ORDER BY d.id""").fetchall()
        # Resolve through enum_ocr_sources rather than assuming fixed lookup IDs:
        # document 1 gets Flash Lite from raw NULL; document 2 keeps explicit Flash.
        # Both dates must retain source notation and a complete successful value.
        self.assertEqual(rows, [(1, Model.GEMINI_2_5_FLASH_LITE.value, "04/05/00", date(2000, 4, 5), ParseStatus.SUCCESS.id),
                               (2, Model.GEMINI_2_5_FLASH.value, "12/31/1999", date(1999, 12, 31), ParseStatus.SUCCESS.id)])
        # The date rule is shared by other layers, so financial April 5 must also
        # be stored correctly. Finally confirm all layers and broad FK coverage.
        self.assertEqual(connection.execute("SELECT transaction_date_parsed, transaction_date_status FROM financial_transactions").fetchone(),
                         (date(2000, 4, 5), ParseStatus.SUCCESS.id))
        self.assertEqual(len(reports), 13)
        self.assertGreater(foreign_keys, 50)
