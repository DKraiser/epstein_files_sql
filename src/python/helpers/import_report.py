"""Summarize Journal JSONL without importing database or Parquet dependencies.

Run from any directory: python3 src/python/import_report.py
Only committed layer summaries supply row counts. The completed run's repeated
summaries are checked, never added. Diagnostic counts are field events, not rows.
Missing/empty parse inputs are not normally journaled by layers.parsed(), so
this tool cannot count all missing source values from the journal alone.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from shared.dataset_passport import PROJECT_DATASET_ROOT
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COUNTERS = {
    "rows_read": "n_read", "rows_accepted": "n_accepted",
    "rows_duplicates": "n_duplicate", "rows_quarantined": "n_quarantined",
}
DATE_COLUMNS = {"date", "event_date", "event_end_date", "transaction_date",
                "statement_date", "flight_departure", "doc_date"}
TIMESTAMP_COLUMNS = {"created_at", "started_at", "last_heartbeat", "completed_at",
                     "first_seen_at", "processed_at"}
JSON_COLUMNS = {"email_fields", "aliases", "search_terms", "sources", "metadata",
                "also_appears_as"}
ERROR_KEYS = ("malformed_date", "partial_date", "malformed_json",
              "malformed_timestamp", "partial_timestamp", "unresolved_fk",
              "invalid_hash", "unknown_model", "other_parse")


def error_category(record):
    if record["kind"] == "match":
        return "unresolved_fk"
    if record["kind"] != "parse":
        return None
    column = record["column"]
    status = record.get(column + "_status")
    if column in DATE_COLUMNS:
        return "partial_date" if status == "partial" else "malformed_date"
    if column in TIMESTAMP_COLUMNS:
        return "partial_timestamp" if status == "partial" else "malformed_timestamp"
    if column in JSON_COLUMNS:
        return "malformed_json"
    if column in {"pdf_sha256", "output_sha256"}:
        return "invalid_hash"
    if column in {"model", "model_used", "extraction_model"}:
        return "unknown_model"
    return "other_parse"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def valid_counts(summary, label):
    for key in COUNTERS.values():
        require(type(summary.get(key)) is int and summary[key] >= 0,
                f"Invalid {key} in {label}")
    require(summary["n_read"] == sum(summary[key] for key in
            ("n_accepted", "n_duplicate", "n_quarantined")),
            f"Unbalanced row accounting in {label}")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze(log_path, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_files = {key: value for key, value in manifest.items()
                    if isinstance(value, dict) and key.endswith(".parquet")}
    expected = defaultdict(dict)
    for name, item in source_files.items():
        require(type(item.get("lines")) is int and item["lines"] >= 0,
                f"Invalid manifest row count: {name}")
        expected[name.removeprefix("data/").rsplit("/", 1)[0]][name] = item["lines"]
    summaries, active, diagnostics = {}, set(), defaultdict(Counter)
    errors, reasons, breakdown = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    started = completed = None
    log_digest = hashlib.sha256()
    with log_path.open("rb") as stream:
        for number, line in enumerate(stream, 1):
            log_digest.update(line)
            try:
                record = json.loads(line)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError(f"Invalid journal JSON at line {number}") from exc
            kind = record["kind"]
            if kind == "run":
                if record["status"] == "started":
                    require(started is None, "Expected exactly one run per journal")
                    started = record
                elif record["status"] == "completed":
                    require(completed is None, "Multiple completion markers")
                    completed = record
                else:
                    raise ValueError(f"Run did not complete: {record['status']}")
                continue
            layer = record["layer"]
            if kind == "layer":
                status = record["status"]
                if status == "started":
                    require(layer not in active and layer not in summaries,
                            f"Repeated layer attempt: {layer}")
                    active.add(layer)
                elif status == "committed":
                    require(layer in active, f"Commit without start: {layer}")
                    active.remove(layer)
                    summaries[layer] = {k: v for k, v in record.items()
                                        if k not in {"kind", "layer", "status"}}
                else:
                    raise ValueError(f"Layer {layer} was {status}; no complete report possible")
                continue
            require(layer in active, f"Diagnostic outside active layer at line {number}")
            diagnostics[layer][kind] += 1
            category = error_category(record)
            if category:
                errors[layer][category] += 1
                column = record.get("column")
                breakdown[layer][(kind, column, record.get(str(column) + "_status"))] += 1
            if kind == "quarantine":
                reasons[layer][record["message"]] += 1
    require(started is not None and completed is not None and not active,
            "Journal is incomplete")
    require(completed["layers"] == summaries, "Final run summaries differ from layer commits")
    require(set(expected) == set(summaries), "Manifest and journal layer coverage differ")
    report = {}
    for layer, summary in summaries.items():
        valid_counts(summary, layer)
        files = summary["files"]
        names = [item["source_file"] for item in files]
        require(len(names) == len(set(names)) and set(names) == set(expected[layer]),
                f"Shard coverage differs for {layer}")
        for item in files:
            valid_counts(item, item["source_file"])
            require(item["n_read"] == expected[layer][item["source_file"]],
                    f"Manifest mismatch: {item['source_file']}")
        for key in COUNTERS.values():
            require(sum(item[key] for item in files) == summary[key],
                    f"Shard totals differ for {layer}: {key}")
        for kind, key in (("quarantine", "n_quarantined"), ("duplicate", "n_duplicate")):
            require(diagnostics[layer][kind] == summary[key], f"{kind} journal mismatch: {layer}")
        require(summary["target_rows"] == summary["existing_rows"] + summary["n_accepted"],
                f"Target row accounting differs for {layer}")
        report[layer.replace("/", "_")] = {
            **{key: summary[value] for key, value in COUNTERS.items()},
            "errors": {key: errors[layer][key] for key in ERROR_KEYS},
            "manifest_rows": sum(expected[layer].values()),
            "manifest_difference": summary["n_read"] - sum(expected[layer].values()),
            "manifest_matches": True, "source_shards": len(files),
            "existing_rows": summary["existing_rows"], "target_rows": summary["target_rows"],
            "model_links_added": summary["model_links_added"], "model_links": summary["model_links"],
            "diagnostic_counts": dict(sorted(diagnostics[layer].items())),
            "parse_and_match_details": [
                {"kind": kind, "column": column, "status": status, "count": count}
                for (kind, column, status), count in sorted(breakdown[layer].items(), key=lambda x: str(x[0]))],
            "quarantine_reasons": dict(sorted(reasons[layer].items())),
        }
    
    return report


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--manifest", type=Path, default= PROJECT_DATASET_ROOT / "source_manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "observations" / "import_report.json")
    args = parser.parse_args()
    report = analyze(args.log, args.manifest)
    require(len({p.resolve() for p in (args.log, args.manifest, args.output)}) == 3,
            "Input and output paths must be distinct")
    write_json(args.output, report)


if __name__ == "__main__":
    main()
