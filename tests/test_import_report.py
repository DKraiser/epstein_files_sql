"""Report accounting must come from commits and reject incomplete evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("import_report", Path(__file__).resolve().parents[1] / "src/python/import_report.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.log = root / "run.jsonl"
        self.manifest = root / "manifest.json"
        self.source = "data/documents/part.parquet"
        self.manifest.write_text(json.dumps({self.source: {"lines": 3}}))
        counts = {"n_read": 3, "n_accepted": 1, "n_quarantined": 1, "n_duplicate": 1}
        self.summary = {**counts, "existing_rows": 0, "target_rows": 1,
                        "model_links_added": 0, "model_links": 0,
                        "files": [{"source_file": self.source, **counts}]}
        self.records = [
            {"kind": "run", "status": "started", "started_at": "start"},
            {"kind": "layer", "layer": "documents", "status": "started"},
            {"kind": "parse", "layer": "documents", "column": "date", "date_status": "partial"},
            {"kind": "quarantine", "layer": "documents", "message": "bad text"},
            {"kind": "duplicate", "layer": "documents"},
            {"kind": "layer", "layer": "documents", "status": "committed", **self.summary},
            {"kind": "run", "status": "completed", "finished_at": "finish",
             "layers": {"documents": self.summary}, "validated_foreign_keys": 1},
        ]

    def analyze(self):
        self.log.write_text("".join(json.dumps(row) + "\n" for row in self.records))
        return module.analyze(self.log, self.manifest)

    def test_completion_summary_is_not_counted_twice(self):
        report, audit = self.analyze()
        self.assertEqual(report["documents"]["rows_read"], 3)
        self.assertEqual(report["documents"]["rows_duplicates"], 1)
        self.assertEqual(report["documents"]["errors"]["partial_date"], 1)
        self.assertEqual(report["documents"]["errors"]["malformed_date"], 0)
        self.assertTrue(all(audit["checks"].values()))

    def test_manifest_mismatch_is_rejected(self):
        self.manifest.write_text(json.dumps({self.source: {"lines": 4}}))
        with self.assertRaisesRegex(ValueError, "Manifest mismatch"):
            self.analyze()

    def test_missing_completion_is_rejected(self):
        self.records.pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.analyze()

    def test_missing_quarantine_record_is_rejected(self):
        self.records = [r for r in self.records if r["kind"] != "quarantine"]
        with self.assertRaisesRegex(ValueError, "quarantine journal mismatch"):
            self.analyze()

    def test_malformed_journal_is_rejected(self):
        self.log.write_text('{broken}\n')
        with self.assertRaisesRegex(ValueError, "line 1"):
            module.analyze(self.log, self.manifest)

    def test_rollback_is_rejected(self):
        self.records[5]["status"] = "rolled_back"
        with self.assertRaisesRegex(ValueError, "rolled_back"):
            self.analyze()


if __name__ == "__main__":
    unittest.main()
