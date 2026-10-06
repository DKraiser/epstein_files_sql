"""Profile the frozen Parquet layers without loading the text corpus at once.
"""

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import polars as pl

from python.shared import dataset_passport

LAYERS = (
    "documents", "entities", "persons", "kg_entities", "kg_relationships",
    "derived_events", "event_participants", "event_sources",
    "financial_transactions", "curated_docs", "provenance/runs",
    "provenance/files",
)
# Keep these field lists explicit so the report only computes expensive
# cardinality and format details for fields that inform the schema decisions.
CATEGORIES = {
    "documents": ("dataset", "document_type", "ocr_source"),
    "entities": ("entity_type",),
    "persons": ("category",),
    "kg_entities": ("entity_type",),
    "kg_relationships": ("relationship_type",),
    "derived_events": ("track", "event_type", "currency", "confidence"),
    "event_participants": ("role",),
    "financial_transactions": ("dataset", "currency", "merchant_category", "card_type", "extraction_model"),
    "curated_docs": ("subject", "status", "tier", "category"),
    "provenance/runs": ("status", "model"),
    "provenance/files": ("status", "model_used"),
}
# Each tuple describes a source-side relationship to check. These checks report
# observed coverage; they do not by themselves establish semantic validity.
REFERENCES = (
    ("entities", "document_id", "documents", "id"),
    ("event_participants", "event_id", "derived_events", "id"),
    ("event_sources", "event_id", "derived_events", "id"),
    ("event_sources", "file_key", "documents", "file_key"),
    ("financial_transactions", "file_key", "documents", "file_key"),
    ("curated_docs", "file_key", "documents", "file_key"),
    ("provenance/files", "run_id", "provenance/runs", "run_id"),
    ("provenance/files", "file_key", "documents", "file_key"),
    ("kg_relationships", "source_id", "kg_entities", "id"),
    ("kg_relationships", "target_id", "kg_entities", "id"),
)
JSON_FIELDS = {
    "documents": ("email_fields",),
    "persons": ("aliases", "search_terms", "sources"),
    "kg_entities": ("metadata",),
    "kg_relationships": ("metadata",),
    "curated_docs": ("also_appears_as",),
}
DATE_FIELDS = {
    "derived_events": ("event_date", "event_end_date"),
    "financial_transactions": ("transaction_date", "statement_date", "flight_departure"),
    "curated_docs": ("doc_date",),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(dataset_passport.PROJECT_ROOT / "observations" / "data_profile.json"))
    args = parser.parse_args()

    scans = {}
    results = {"layers": {}, "references": {}, "formats": {}}

    for layer in LAYERS:
        # Lazy scans avoid loading every Parquet shard into memory at once.
        paths = dataset_passport.LOCAL_FILES_PATHS[layer]
        if not paths:
            raise FileNotFoundError(f"No required shards for {layer}")
        
        scan = pl.scan_parquet([str(path) for path in paths])
        scans[layer] = scan
        schema = scan.collect_schema()
        expr = [pl.len().alias("rows")]

        # Gather null/empty counts and simple size/range bounds in one
        # aggregation per layer.
        for name, dtype in schema.items():
            expr.append(pl.col(name).null_count().alias(f"{name}__null"))
            if dtype == pl.String:
                expr.extend((
                    (pl.col(name) == "").sum().alias(f"{name}__empty"),
                    pl.col(name).str.len_chars().max().alias(f"{name}__max_chars"),
                ))
            elif dtype.is_numeric():
                expr.extend((pl.col(name).min().alias(f"{name}__min"),
                             pl.col(name).max().alias(f"{name}__max")))
        
        row = scan.select(expr).collect().to_dicts()[0]
        fields = {}

        for name, dtype in schema.items():
            prefix = f"{name}__"
            fields[name] = {"type": str(dtype), **{k.removeprefix(prefix): v for k, v in row.items() if k.startswith(prefix)}}
        
        item = {"shards": len(paths), "compressed_bytes": sum(path.stat().st_size for path in paths),
                "rows": row["rows"], "fields": fields}
        
        for key in ("id", "file_key", "run_id"):
            if key in schema:
                item[f"distinct_{key}"] = scan.select(pl.col(key).n_unique()).collect().item()
        
        item["categories"] = {}
        
        for name in CATEGORIES.get(layer, ()):
            # Keep frequent labels for review while recording the full
            # distinct count, including NULL when present.
            counts = scan.group_by(name).len().sort("len", descending=True).collect()
            item["categories"][name] = {"distinct": counts.height, "top": counts.head(30).to_dicts()}
        
        results["layers"][layer] = item

    for source_layer, source_field, parent_layer, parent_field in REFERENCES:
        # Exclude NULL child references: they are missing links, not unmatched
        # values. The anti-join finds non-NULL values absent from the parent.
        child = scans[source_layer].select(source_field).filter(pl.col(source_field).is_not_null())
        parent = scans[parent_layer].select(pl.col(parent_field).alias(source_field))
        missing = child.join(parent, on=source_field, how="anti")
        
        # Count affected rows and distinct missing keys so repeated bad keys
        # are not mistaken for many different unresolved references.
        rows, values = missing.select(pl.len(), pl.col(source_field).n_unique()).collect().row(0)
        results["references"][f"{source_layer}.{source_field}"] = {
            "target": f"{parent_layer}.{parent_field}", "nonnull_rows": child.select(pl.len()).collect().item(),
            "unmatched_rows": rows, "unmatched_values": values,
        }

    results["candidate_keys"] = {}
    
    # These are empirical uniqueness checks for this snapshot, not guarantees
    # that the source enforces them over time.
    for layer, fields in (("persons", ("slug",)),
                          ("event_sources", ("event_id", "file_key")),
                          ("event_participants", ("event_id", "person_name", "role")),
                          ("curated_docs", ("subject", "file_key"))):
        results["candidate_keys"][f"{layer}.{'+'.join(fields)}"] = scans[layer].select(pl.struct(list(fields)).n_unique()).collect().item()

    for layer, fields in JSON_FIELDS.items():
        for field in fields:
            counts = Counter()
            
            # Count top-level JSON types, retaining invalid JSON as its own
            # result instead of silently skipping it.
            for raw in scans[layer].select(field).filter(pl.col(field).is_not_null()).collect().get_column(field):
                try:
                    counts[type(json.loads(raw)).__name__] += 1
                except (ValueError, TypeError):
                    counts["invalid"] += 1
            
            results["formats"][f"{layer}.{field}.json"] = dict(counts)

    for layer, fields in DATE_FIELDS.items():
        for field in fields:
            counts = Counter()
            
            # This strict ISO-shape/calendar check is not a permissive date
            # parser; human-readable forms are reported separately.
            for raw in scans[layer].select(field).filter(pl.col(field).is_not_null()).collect().get_column(field):
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                    try:
                        date.fromisoformat(raw)
                        counts["valid_iso_date"] += 1
                    except ValueError:
                        counts["invalid_iso_date"] += 1
                
                else:
                    counts["other_notation"] += 1
            
            results["formats"][f"{layer}.{field}.date"] = dict(counts)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, default=str) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
