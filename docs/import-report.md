# Import report

Analyzed run: `logs/20261006T142505176655Z.jsonl`. Source manifest: `data/source_manifest.json`. Machine-readable results: [import_report.json](import_report.json).

The journal records a **completed** import from **2026-10-06 14:25:05.176822+00:00** to **2026-10-06 18:42:50.691218+00:00** (UTC). All **13 source layers / 56 Parquet shards** match the manifest. **15,725,373 rows were read, 15,725,299 accepted, 74 quarantined, and 0 classified as duplicates.**

## Row counts and manifest comparison

Counts come from `kind=layer, status=committed` records. The repeated summaries in the final `kind=run, status=completed` record are checked for equality and are not added again. SQL table names replace `/` with `_`, so `provenance/runs` is reported as `provenance_runs`.

“Accepted” means newly inserted rows in this run. “Duplicates” means rows whose normalized values equal an already accepted row; conflicting unique keys would be quarantined. Every layer has `existing_rows = 0`, so its target row count equals its accepted count.

| Table | Shards | Manifest rows | Read | Accepted | Quarantined | Duplicates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `documents` | 15 | 1,424,673 | 1,424,673 | 1,424,662 | 11 | 0 |
| `persons` | 1 | 1,614 | 1,614 | 1,614 | 0 | 0 |
| `kg_entities` | 1 | 467 | 467 | 467 | 0 | 0 |
| `derived_events` | 1 | 3,038 | 3,038 | 3,038 | 0 | 0 |
| `provenance_runs` | 1 | 123 | 123 | 123 | 0 | 0 |
| `chunks` | 11 | 2,193,090 | 2,193,090 | 2,193,027 | 63 | 0 |
| `entities` | 18 | 10,629,198 | 10,629,198 | 10,629,198 | 0 | 0 |
| `kg_relationships` | 1 | 2,198 | 2,198 | 2,198 | 0 | 0 |
| `event_participants` | 1 | 5,751 | 5,751 | 5,751 | 0 | 0 |
| `event_sources` | 1 | 21,910 | 21,910 | 21,910 | 0 | 0 |
| `financial_transactions` | 1 | 49,770 | 49,770 | 49,770 | 0 | 0 |
| `curated_docs` | 1 | 5,766 | 5,766 | 5,766 | 0 | 0 |
| `provenance_files` | 3 | 1,387,775 | 1,387,775 | 1,387,775 | 0 | 0 |
| **Total** | **56** | **15,725,373** | **15,725,373** | **15,725,299** | **74** | **0** |

Each table and each shard satisfies:

```text
rows_read = rows_accepted + rows_quarantined + rows_duplicates
15,725,373 = 15,725,299 + 74 + 0
```
## Import errors and diagnostics

Counts below are diagnostic **field events**, not necessarily rejected rows or distinct affected rows. `failed` denotes a parsing failure; `partial` denotes insufficient information for a complete date or timestamp. These categories are separate in the JSON report.

| Category | Count | Details |
| --- | ---: | --- |
| Malformed dates (`failed`) | 3,004 | `documents.date`: 2,790; `curated_docs.doc_date`: 214 |
| Partial dates | 30,503 | `documents.date`: 30,362; `curated_docs.doc_date`: 141 |
| Malformed JSON | 0 | No failed JSON parsing diagnostics |
| Malformed timestamps | 0 | No failed timestamp parsing diagnostics |
| Partial timestamps | 4,431 | `provenance_runs.completed_at`: 3; `provenance_files.first_seen_at`: 138; `provenance_files.processed_at`: 4,290 |
| Unresolved references | 17,203 | Required: 63; optional: 17,140 |
| Invalid SHA-256 fields | 0 | No failed hash parsing diagnostics |
| Unknown model tokens | 0 | No unknown-model parsing diagnostics |

Raw date/JSON/timestamp notation and explicit parse status are preserved by the importer. Parse diagnostics alone do not quarantine a row. Partial timestamps are not automatically malformed: timezone-aware targets require a timezone, and the parser does not invent one. For unzoned `completed_at`, the importer can also retain local wall-clock time separately.

### Unresolved references

| Table / source field | Count | Outcome |
| --- | ---: | --- |
| `chunks.document_id` | 63 | Required reference: row quarantined |
| `entities.document_id` | 473 | Optional reference: row retained with unresolved status and NULL target FK |
| `event_sources.file_key` | 16,651 | Optional document reference: row retained with unresolved status and NULL target FK |
| `provenance_files.file_key` | 16 | Optional document reference: row retained with unresolved status and NULL target FK |

An unresolved source reference is distinct from a database FK violation. Optional unresolved references use NULL target FKs; required unresolved chunk references are rejected before insertion.

### Quarantines and search-vector diagnostics

- **11 documents**: `PostgreSQL text fields cannot contain NUL (0x00) bytes`.
- **63 chunks**: required `document_id` references did not resolve. Exact parent IDs and counts appear under `chunks.quarantine_reasons` in the JSON.
- **49 accepted documents**: full text exceeded the 1 MiB search-vector input cutoff. The importer retained full text and stored an empty search vector. These are intentional search-index omissions, not quarantines.

The journal stores the complete original source record for each quarantine or duplicate, with source file, zero-based source row, and source identifier where available.

## Integrity checks

### Checks performed by the reporting script

[src/python/import_report.py](src/python/import_report.py) verified all of the following against this journal and manifest:

1. A single completed run, no active or rolled-back layers, and equality of final run summaries with committed layer records.
2. Exact layer and shard coverage: all 13 layers and 56 shards, with no missing or repeated shards.
3. Per-shard `n_read` equals manifest `lines`; per-shard counters sum to the committed layer counters.
4. Balanced row accounting at both shard and layer levels.
5. Quarantine and duplicate diagnostic totals equal the corresponding committed counters.
6. `target_rows = existing_rows + rows_accepted` for every table.

### Checks evidenced by import completion

In [src/python/importer/main.py](src/python/importer/main.py), the completion marker is written only after final count and FK verification returns. The journal reports **61 validated foreign-key constraints**. The verification implementation in [src/python/importer/verification.py](src/python/importer/verification.py) checks:

- Stored batch values equal transformed accepted/duplicate source values, including JSON NULL versus SQL NULL.
- Document/chunk search vectors agree with the configured PostgreSQL conversion and size cutoff.
- Provenance model bridge pairs equal the parsed model lists.
- Source-table and bridge-table totals equal expected totals.
- Mandatory FKs exist; all discovered FKs are validated and enforced; replication mode is `origin`; there are no orphan records for non-NULL FKs.
- Primary/unique indexes are valid and ready.

The committed bridge totals are **123** `provenance_run_models` links and **1,388,114** `provenance_file_models` links. These derived links are additional target rows and are excluded from source-row totals.

## Reproducibility evidence

From the project root, using Python 3 and no third-party packages:

```bash
python3 src/python/import_report.py
```



