# Data profile

Source: local `data/data/` Parquet shards from revision `133ef9f0a539fafc270cde8fa8638dc38d89968d` (the 56 `*-of-*` files). Counts below are measured from Parquet with Polars 1.44.2. `NULL` counts are source nulls; `empty` means an exact zero-length string and excludes NULL. String maximums are characters. Each `id` distinct count includes the whole layer, not just one shard. No personal text values are printed.

Reproduce the layer statistics and reference checks with `python src/python/data_profile/layers.py --data-root data/data --output observations/layers_profile.json` in an environment with Polars installed. The `documents` date parsing work already started in `src/python/data_profile/documents.py`; the source statistics below supplement it. The `chunks` layer is left as previously analyzed.

## Overview

| Source layer | Rows | Shards | Compressed bytes | Source ID uniqueness | Main schema decision |
|---|---:|---:|---:|---|---|
| `documents` | 1,424,673 | 15 | 634,913,564 | 1,424,673 distinct `id` | Keep source ID/key; preserve date and email JSON notation. |
| `entities` | 10,629,198 | 18 | 61,566,244 | 10,629,198 distinct `id` | Keep raw document ID; resolved FK is optional. |
| `persons` | 1,614 | 1 | 65,538 | 1,614 distinct `id` | JSON arrays; category lookup. |
| `kg_entities` | 467 | 1 | 11,549 | 467 distinct `id` | Type lookup and JSON object. |
| `kg_relationships` | 2,198 | 1 | 31,375 | 2,198 distinct `id` | Both endpoints required FKs; type lookup. |
| `derived_events` | 3,038 | 1 | 291,804 | 3,038 distinct `id` | DATE for ISO dates; raw time text; decimal amount. |
| `event_participants` | 5,751 | 1 | 47,358 | 5,751 distinct `id` | Required event FK; name remains text. |
| `event_sources` | 21,910 | 1 | 78,696 | 21,910 distinct `id` | Required event FK; optional resolved document FK. |
| `financial_transactions` | 49,770 | 1 | 1,224,697 | 49,770 distinct `id` | Required resolved document FK; decimal amount. |
| `curated_docs` | 5,766 | 1 | 1,629,169 | 5,766 distinct `id` | Required resolved document FK; preserve mixed date. |
| `provenance/runs` | 123 | 1 | 15,785 | 123 distinct `run_id` | Offset aware times; flag missing timezone. |
| `provenance/files` | 1,387,775 | 3 | 102,579,922 | 1,387,767 distinct `file_key` (duplicates) | Surrogate row ID plus source position; file_key repeats. |

## Column statistics

Type is the Parquet type. `Range` is numeric minimum–maximum; `max chars` is shown for strings. A dash means not applicable.

### `documents`

1,424,673 rows in 15 shards.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 1–1528459 |
| `file_key` | `String` | 0 | 0 | max 118 chars |
| `dataset` | `String` | 0 | 0 | max 25 chars |
| `full_text` | `String` | 0 | 511 | max 13,312,184 chars |
| `document_type` | `String` | 564,974 | 0 | max 124 chars |
| `date` | `String` | 637,074 | 0 | max 66 chars |
| `is_photo` | `Boolean` | 0 | — | — |
| `has_handwriting` | `Boolean` | 56,820 | — | — |
| `has_stamps` | `Boolean` | 56,820 | — | — |
| `ocr_source` | `String` | 884,769 | 0 | max 19 chars |
| `additional_notes` | `String` | 554,401 | 1,327 | max 35,754 chars |
| `page_number` | `String` | 1,055,932 | 0 | max 22 chars |
| `document_number` | `String` | 1,352,329 | 0 | max 16,278 chars |
| `char_count` | `Int32` | 0 | — | 0–13312184 |
| `created_at` | `String` | 0 | 0 | max 19 chars |
| `email_fields` | `String` | 1,424,038 | 0 | max 663 chars |

Selected cardinalities: `dataset` 51 non-NULL labels (52 including NULL); `document_type` 6,180 non-NULL labels (6,181 including NULL); `ocr_source` 2 non-NULL labels (3 including NULL).
`ocr_source` values: `tesseract-community` 532,944, `olmocr` 6,960.

### `entities`

10,629,198 rows in 18 shards.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 1–11928200 |
| `document_id` | `Int64` | 0 | — | 1–1528459 |
| `entity_type` | `String` | 0 | 0 | max 16 chars |
| `value` | `String` | 0 | 0 | max 3,499 chars |
| `normalized_value` | `String` | 10,629,198 | 0 | — |

Selected cardinalities: `entity_type` 8 distinct (including NULL).
`entity_type` values: `reference_number` 3,757,727, `date` 2,586,803, `person` 2,098,576, `organization` 1,341,192, `location` 811,958, `email_address` 13,165, `phone_number` 11,343, `monetary_amount` 8,434.

### `persons`

1,614 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 1–1614 |
| `canonical_name` | `String` | 0 | 0 | max 53 chars |
| `slug` | `String` | 0 | 0 | max 52 chars |
| `category` | `String` | 0 | 0 | max 12 chars |
| `aliases` | `String` | 0 | 0 | max 64 chars |
| `search_terms` | `String` | 0 | 0 | max 92 chars |
| `sources` | `String` | 0 | 0 | max 56 chars |
| `notes` | `String` | 1,614 | 0 | — |

Selected cardinalities: `category` 17 distinct (including NULL).
`category` values: `associate` 747, `other` 338, `business` 174, `celebrity` 85, `academic` 61, `politician` 54, `legal` 44, `socialite` 34, `staff` 28, `political` 25, `royalty` 9, `financial` 4, `perpetrator` 3, `enabler` 3, `intelligence` 2, `media` 2, `victim` 1.

### `kg_entities`

467 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 1–476 |
| `name` | `String` | 0 | 0 | max 53 chars |
| `entity_type` | `String` | 0 | 0 | max 13 chars |
| `description` | `String` | 467 | 0 | — |
| `metadata` | `String` | 0 | 0 | max 343 chars |

Selected cardinalities: `entity_type` 6 distinct (including NULL).
`entity_type` values: `person` 432, `shell_company` 12, `organization` 9, `property` 7, `aircraft` 4, `location` 3.

### `kg_relationships`

2,198 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 11–6241 |
| `source_id` | `Int64` | 0 | — | 1–476 |
| `target_id` | `Int64` | 0 | — | 1–476 |
| `relationship_type` | `String` | 0 | 0 | max 17 chars |
| `weight` | `Float64` | 0 | — | 1.0–816.0 |
| `evidence` | `String` | 2,198 | 0 | — |
| `metadata` | `String` | 0 | 0 | max 450 chars |

Selected cardinalities: `relationship_type` 10 distinct (including NULL).
`relationship_type` values: `traveled_with` 1,517, `associated_with` 625, `owned_by` 23, `victim_of` 11, `communicated_with` 9, `employed_by` 7, `represented_by` 3, `recruited_by` 1, `paid_by` 1, `related_to` 1.

### `derived_events`

3,038 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 5455–8492 |
| `event_date` | `String` | 26 | 0 | max 10 chars |
| `event_end_date` | `String` | 2,973 | 0 | max 10 chars |
| `event_type` | `String` | 0 | 0 | max 16 chars |
| `track` | `String` | 0 | 0 | max 9 chars |
| `headline` | `String` | 0 | 0 | max 200 chars |
| `location` | `String` | 1,007 | 0 | max 62 chars |
| `amount` | `Float64` | 2,700 | — | 10.0–875000000.0 |
| `currency` | `String` | 0 | 0 | max 3 chars |
| `payer` | `String` | 3,038 | 0 | — |
| `payee` | `String` | 3,036 | 0 | max 46 chars |
| `route_from` | `String` | 2,766 | 0 | max 46 chars |
| `route_to` | `String` | 2,766 | 0 | max 62 chars |
| `aircraft` | `String` | 3,038 | 0 | — |
| `time_of_day` | `String` | 1,361 | 0 | max 7 chars |
| `confidence` | `String` | 0 | 0 | max 9 chars |
| `narrative` | `String` | 7 | 0 | max 6,762 chars |

Selected cardinalities: `track` 3 distinct (including NULL); `event_type` 9 distinct (including NULL); `currency` 1 distinct (including NULL); `confidence` 2 distinct (including NULL); `time_of_day` 303 distinct (including NULL).
`track` values: `calendar` 2,365, `financial` 379, `travel` 294.
`event_type` values: `meeting` 1,633, `flight` 741, `transaction` 361, `phone_call` 124, `dinner` 113, `appointment` 30, `gift` 18, `ground_transport` 13, `hotel` 5.
`currency` values: `USD` 3,038.
`confidence` values: `confirmed` 2,896, `tentative` 142.

### `event_participants`

5,751 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 8574–14324 |
| `event_id` | `Int64` | 0 | — | 5455–8492 |
| `person_name` | `String` | 0 | 0 | max 59 chars |
| `role` | `String` | 0 | 0 | max 11 chars |

Selected cardinalities: `role` 4 distinct (including NULL).
`role` values: `attendee` 3,524, `participant` 1,918, `passenger` 283, `recipient` 26.

### `event_sources`

21,910 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 9098–31007 |
| `event_id` | `Int64` | 0 | — | 5455–8490 |
| `file_key` | `String` | 0 | 0 | max 12 chars |

### `financial_transactions`

49,770 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 1–72518 |
| `file_key` | `String` | 0 | 0 | max 27 chars |
| `dataset` | `String` | 0 | 0 | max 16 chars |
| `transaction_date` | `String` | 269 | 0 | max 10 chars |
| `amount` | `Float64` | 551 | — | -1953829000.0–1961600000.0 |
| `currency` | `String` | 0 | 0 | max 3 chars |
| `merchant_name` | `String` | 295 | 0 | max 614 chars |
| `merchant_raw` | `String` | 23,954 | 1 | max 292 chars |
| `merchant_category` | `String` | 61 | 0 | max 18 chars |
| `location` | `String` | 42,979 | 0 | max 60 chars |
| `cardholder` | `String` | 7,590 | 0 | max 100 chars |
| `description` | `String` | 25,905 | 0 | max 614 chars |
| `card_type` | `String` | 48,722 | 0 | max 42 chars |
| `account_digits` | `String` | 38,994 | 0 | max 8 chars |
| `statement_date` | `String` | 6,782 | 0 | max 10 chars |
| `flight_from` | `String` | 49,702 | 0 | max 31 chars |
| `flight_to` | `String` | 49,703 | 0 | max 38 chars |
| `flight_carrier` | `String` | 49,695 | 0 | max 6 chars |
| `flight_departure` | `String` | 49,702 | 0 | max 10 chars |
| `flight_ticket` | `String` | 49,700 | 0 | max 14 chars |
| `flight_passenger` | `String` | 49,753 | 0 | max 20 chars |
| `source_page` | `Int32` | 49,770 | — | — |
| `extraction_model` | `String` | 0 | 0 | max 13 chars |
| `extraction_confidence` | `Float64` | 49,770 | — | — |

Selected cardinalities: `dataset` 9 distinct (including NULL); `currency` 1 distinct (including NULL); `merchant_category` 54 distinct (including NULL); `card_type` 22 distinct (including NULL); `extraction_model` 1 distinct (including NULL).
`dataset` values: `DataSet10` 48,008, `DataSet11` 548, `internet_archive` 490, `DataSet8` 301, `USAvJE` 251, `Tier2` 93, `DataSet4` 72, `_unknown` 6, `DataSet6` 1.
`currency` values: `USD` 49,770.
`extraction_model` values: `deepseek-chat` 49,770.

### `curated_docs`

5,766 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `id` | `Int64` | 0 | — | 1–31898 |
| `file_key` | `String` | 0 | 0 | max 74 chars |
| `subject` | `String` | 0 | 0 | max 7 chars |
| `status` | `String` | 0 | 0 | max 4 chars |
| `tier` | `String` | 0 | 0 | max 10 chars |
| `category` | `String` | 0 | 0 | max 75 chars |
| `doc_date` | `String` | 165 | 0 | max 41 chars |
| `doc_from` | `String` | 681 | 0 | max 106 chars |
| `doc_to` | `String` | 961 | 0 | max 100 chars |
| `headline` | `String` | 8 | 0 | max 458 chars |
| `key_quote` | `String` | 138 | 0 | max 912 chars |
| `detail` | `String` | 40 | 0 | max 3,557 chars |
| `thread_value` | `String` | 783 | 0 | max 742 chars |
| `also_appears_as` | `String` | 4,928 | 0 | max 352 chars |

Selected cardinalities: `subject` 5 distinct (including NULL); `status` 1 distinct (including NULL); `tier` 5 distinct (including NULL); `category` 1,804 distinct (including NULL).
`subject` values: `gates` 2,069, `hoffman` 1,526, `clinton` 765, `summers` 739, `black` 667.
`status` values: `gold` 5,766.
`tier` values: `HIGH` 1,692, `NUCLEAR` 1,525, `CRITICAL` 1,153, `SUPPORTING` 949, `MEDIUM` 447.

### `provenance/runs`

123 rows in 1 shard.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `run_id` | `String` | 0 | 0 | max 54 chars |
| `started_at` | `String` | 0 | 0 | max 32 chars |
| `completed_at` | `String` | 0 | 0 | max 32 chars |
| `status` | `String` | 0 | 0 | max 11 chars |
| `input_dir` | `String` | 0 | 0 | max 47 chars |
| `output_name` | `String` | 0 | 0 | max 20 chars |
| `model` | `String` | 0 | 0 | max 21 chars |
| `dpi` | `Int32` | 0 | — | 0–150 |
| `workers` | `Int32` | 0 | — | 0–100 |
| `rpm` | `Int32` | 0 | — | 0–2000 |
| `git_commit` | `String` | 11 | 0 | max 8 chars |
| `hostname` | `String` | 1 | 0 | max 7 chars |
| `total_files` | `Int32` | 0 | — | 1–531279 |
| `success_count` | `Int32` | 0 | — | 0–531279 |
| `fail_count` | `Int32` | 0 | — | 0–1265 |
| `input_tokens` | `Int64` | 0 | — | 0–209642601 |
| `output_tokens` | `Int64` | 0 | — | 0–403570427 |
| `cost_usd` | `Float64` | 0 | — | 0.0–182.3924309 |
| `last_heartbeat` | `String` | 100 | 0 | max 32 chars |

Selected cardinalities: `status` 3 distinct (including NULL); `model` 2 distinct (including NULL).
`status` values: `completed` 66, `crashed` 43, `interrupted` 14.
`model` values: `gemini-2.5-flash-lite` 113, `tesseract-community` 10.

### `provenance/files`

1,387,775 rows in 3 shards.

| Source field | Parquet type | NULL | Empty | Size / range |
|---|---|---:|---:|---|
| `file_key` | `String` | 0 | 0 | max 25 chars |
| `output_name` | `String` | 0 | 0 | max 20 chars |
| `pdf_path` | `String` | 0 | 0 | max 85 chars |
| `pdf_sha256` | `String` | 538,933 | 0 | max 64 chars |
| `pdf_size_bytes` | `Int64` | 538,933 | — | 0–764000776 |
| `status` | `String` | 0 | 0 | max 7 chars |
| `output_path` | `String` | 2 | 0 | max 59 chars |
| `output_sha256` | `String` | 2 | 0 | max 64 chars |
| `first_seen_at` | `String` | 0 | 0 | max 32 chars |
| `processed_at` | `String` | 0 | 0 | max 32 chars |
| `run_id` | `String` | 63,676 | 0 | max 54 chars |
| `input_tokens` | `Int64` | 602,786 | — | 0–509354 |
| `output_tokens` | `Int64` | 602,786 | — | 0–1734483 |
| `api_latency_ms` | `Int64` | 602,786 | — | 0–6801858 |
| `attempts` | `Int32` | 0 | — | 0–7 |
| `error_message` | `String` | 1,383,206 | 0 | max 195 chars |
| `model_used` | `String` | 0 | 0 | max 65 chars |
| `validation_score` | `Int32` | 650,620 | — | 9–15 |

Selected cardinalities: `status` 2 distinct (including NULL); `model_used` 11 distinct (including NULL).
`status` values: `success` 1,387,307, `failed` 468.
`model_used` values: `gemini-2.5-flash-lite` 855,667, `tesseract-community` 531,279, `grok-2-vision-latest` 285, `gemini-2.5-flash-lite,gemini-3-flash-preview` 245, `gemini-2.5-flash` 166, `gemini-2.5-flash,gemini-2.5-flash-lite` 50, `gemini-3-flash-preview` 34, `gpt-5-nano` 20, `gemini-2.5-flash-lite,gemini-3-flash-preview,grok-2-vision-latest` 18, `gemini-2.5-flash-lite,grok-2-vision-latest` 8, `gpt-4o-mini` 3.

## Candidate keys, duplicates, and references

- The source `id` column is non-NULL and unique in each profiled ID-bearing layer; `provenance/runs.run_id` is also non-NULL and unique. `documents.file_key` is unique across 1,424,673 rows. `chunks` was excluded from this profiling pass, so its earlier mapping is retained without a new candidate-key audit. Preserve source IDs with their gaps.
- Additional unique values or minimal combinations observed in this frozen revision: `persons.canonical_name`; `kg_entities.name`; `(event_sources.event_id, file_key)`; `(event_participants.event_id, person_name)`; `(curated_docs.subject, file_key)`. These are empirical candidate keys for this snapshot; source IDs remain the intended stable primary keys.
- `persons.slug` has 1,608 distinct values in 1,614 rows, so it is not a key. `kg_entities.name` alone is unique; adding `entity_type` is redundant for uniqueness in this revision.
- `provenance/files.file_key` has 1,387,767 distinct values in 1,387,775 rows: eight keys occur twice. The 16 rows in those pairs are distinct processing records from different runs. `file_key` cannot be unique. `(source_file, source_row)` identifies the row in the pinned Parquet files and `provenance_files.id` is a local surrogate; the surrogate itself can change on rebuild.

| Reference from source | Non-NULL rows | Unmatched rows | Distinct unmatched values | Target rule |
|---|---:|---:|---:|---|
| `entities.document_id` → `documents.id` | 10,629,198 | 78 | 13 | nullable resolved FK + raw ID |
| `event_participants.event_id` → `derived_events.id` | 5,751 | 0 | 0 | required FK |
| `event_sources.event_id` → `derived_events.id` | 21,910 | 0 | 0 | required FK |
| `event_sources.file_key` → `documents.file_key` | 21,910 | 16,651 | 346 | nullable resolved document FK + raw key |
| `financial_transactions.file_key` → `documents.file_key` | 49,770 | 0 | 0 | required resolved document FK + raw key |
| `curated_docs.file_key` → `documents.file_key` | 5,766 | 0 | 0 | required resolved document FK + raw key |
| `provenance/files.run_id` → `provenance/runs.run_id` | 1,324,099 | 0 | 0 | nullable FK |
| `provenance/files.file_key` → `documents.file_key` | 1,387,775 | 5 | 5 | nullable resolved document FK + raw key |
| `kg_relationships.source_id` → `kg_entities.id` | 2,198 | 0 | 0 | required FK |
| `kg_relationships.target_id` → `kg_entities.id` | 2,198 | 0 | 0 | required FK |

`entities.document_id` has 78 unresolved mentions across 13 raw IDs. A same-named ID is not enough to assert a document match. `event_sources.file_key` has 16,651 unmatched rows across 346 keys; evidence keys need not be documents in this layer. `provenance/files.file_key` has five unmatched rows, while all non-NULL run IDs resolve. Of 123 run IDs, 112 have canonical UUID shape and 11 are descriptive non-UUID strings; keep `run_id` as TEXT. Participant names are strings, not verified `persons.id` matches. FK `ON DELETE RESTRICT` preserves existing evidence links.

## Formats and conversion decisions

- `documents.date` has 787,599 non-NULL strings; only 20,131 have the exact `YYYY-MM-DD` shape, and 1,209 contain only a four-digit year. Keep the raw string and record date precision; `created_at` parses under `%Y-%m-%d %H:%M:%S` for all 1,424,673 rows but has no timezone.
- Source `persons.aliases`, `search_terms`, and `sources` are valid JSON arrays in all 1,614 rows. `kg_entities.metadata` (467) and `kg_relationships.metadata` (2,198) are valid JSON objects. `curated_docs.also_appears_as` has 838 non-NULL valid JSON arrays. `documents.email_fields` has 635 non-NULL valid JSON values: 631 objects and four arrays. Keep the raw email string alongside JSONB so SQL NULL, JSON null, absent object keys, and invalid JSON can be distinguished at import.
- All non-NULL `derived_events.event_date` (3,012), `event_end_date` (65), `financial_transactions.transaction_date` (49,501), `statement_date` (42,988), and `flight_departure` (68) are valid `YYYY-MM-DD` dates. `curated_docs.doc_date` has 4,343 ISO-shaped strings, ten of which contain zero day/month and are invalid calendar dates; 1,258 other strings include prose, partial dates, and ranges. Of the 4,343 ISO-shaped strings, 4,333 are valid dates. Preserve its raw notation and assign a precision/status during import.
- `derived_events.time_of_day` has 1,597 `h:mmam/pm` values and 80 other non-NULL forms, including bare hours and 24-hour times; retain raw text rather than inventing a full time.
- Upstream `runs.started_at`, `last_heartbeat`, and `files.first_seen_at`/`processed_at` have offset-bearing timestamps. Three `runs.completed_at` values have no offset, so retain the raw string and mark `timezone_missing` rather than guessing a zone.
- `financial_transactions.amount` has 551 NULLs and both signs, from −1,953,829,000 to 1,961,600,000. Values include up to five decimal places in the source Float64 string form; `NUMERIC` must have no forced two-decimal scale. `derived_events.amount` has 2,700 NULLs and ranges from 10 to 875,000,000. Source Float64 cannot recover precision that was already lost upstream; conversion should use `Decimal(str(value))`. Both currency columns contain only `USD` here, but retain currency on each row and group by it in sums.
- Every non-NULL provenance SHA-256 value has exactly 64 hexadecimal characters (zero malformed hashes observed); decode valid hex to 32 bytes for `BYTEA`, while retaining raw text.
- `provenance/runs.model` contains two names. `provenance/files.model_used` contains 11 distinct strings, some comma-separated; splitting on commas and trimming yields seven individual names in those two layers. `financial_transactions.extraction_model` adds `deepseek-chat`, for eight names in the shared model lookup. The raw combined strings remain available; ordered bridge rows preserve model order.
- `financial_transactions.source_page` and `extraction_confidence`, `persons.notes`, `kg_entities.description`, `kg_relationships.evidence`, and `derived_events.payer`/`aircraft` are wholly NULL in this revision. Their columns remain because they are source fields and may be populated in another revision.
- `documents.document_type` has 6,180 non-NULL exact string labels (6,181 values if NULL is treated as a distinct category). The first shard has 2,981 non-NULL labels, which likely explains the earlier ~3,000 count; the full path list in `src/python/defines.py` includes all 15 shards. Exact matching is case-sensitive: `Email` and `email` are distinct. Trimming and lowercasing would still leave 5,982 values and would alter source labels, so the schema uses exact lookup labels instead of collapsing them. There are 3,070 labels occurring once. Its lookup is a relational dictionary, not a closed PostgreSQL ENUM. `curated_docs.category` has 1,804 values and stays text. Small observed vocabularies (entity type, person category, KG type/relation, event type/track/confidence, participant role, curated subject/tier) use lookup tables whose contents are derived from this frozen revision, not hard-coded semantic assertions.

## Scope of this profile

These are source measurements and schema design decisions. Parsing states are lookup FKs: `SUCCESS` for a full parse, `PARTIAL` when source precision or components are incomplete, `MISSING` for SQL NULL, `EMPTY` for a zero-length string, and `FAILED` for a non-empty value that fails validation. Every parsed-field status uses this shared lookup, including JSON, date/time, hash, and model-list fields. Counts by parse outcome are not claimed until the importer runs. Target import acceptance, quarantine, duplicate accounting, and validated data FK counts require the completed importer and a full database run; they are not inferred from the Parquet profile.
