# Data mapping

Source: the pinned Parquet revision recorded in `data/source_manifest.json`. Target: [`src/sql/schema.sql`](../src/sql/schema.sql). Every source field is represented, including fields that are NULL throughout this revision. Raw columns preserve source notation where parsing is applied; parsed columns hold typed values; every parsing status is a FK to `enum_parse_statuses`. Lookup conversions use exact source labels.

For parse status values: `success` = full parse; `partial` = useful value but incomplete precision; `null` = source SQL NULL; `empty` = exact empty string; `failed` = non-empty value failed parsing/validation. Invalid JSON and hashes retain their raw strings and are logged or quarantined by the importer. `success` parsing of the JSON text `null` stores JSONB null; SQL NULL remains distinct.

Every ordinary source ID is retained as a source ID. `provenance_files.id` is a local surrogate; `(source_file, source_row)` identifies its row in the pinned input. Relationships use `ON DELETE RESTRICT`, except the model bridge rows, which cascade with their parent run/file.

## Per-field mapping

### `documents` → `documents`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `file_key` (`String`) | `file_key` `TEXT` | Preserve source value and SQL NULL as provided. |
| `dataset` (`String`) | `dataset` `SMALLINT` | Exact source label maps to `enum_datasets`; source spelling is unchanged. |
| `full_text` (`String`) | `full_text` `TEXT` | Preserve source value and SQL NULL as provided. |
| `document_type` (`String`) | `document_type` `SMALLINT` | Exact source label maps to `enum_document_types`; NULL remains NULL. |
| `date` (`String`) | `date_raw` `TEXT`, `date_parsed` `DATE`, `date_status` `SMALLINT` | Keep exact notation. Reuse the explicit deterministic formats in `src/python/data_profile/documents.py`; complete unambiguous dates parse, partial/ambiguous values stay raw with PARTIAL, malformed non-empty values get FAILED, NULL gets MISSING. |
| `is_photo` (`Boolean`) | `is_photo` `BOOLEAN` | Preserve source value and SQL NULL as provided. |
| `has_handwriting` (`Boolean`) | `has_handwriting` `BOOLEAN` | Preserve source value and SQL NULL as provided. |
| `has_stamps` (`Boolean`) | `has_stamps` `BOOLEAN` | Preserve source value and SQL NULL as provided. |
| `ocr_source` (`String`) | `ocr_source` `SMALLINT` | Exact source label maps to `enum_ocr_sources`; NULL remains NULL and is not inferred as Gemini. |
| `additional_notes` (`String`) | `additional_notes` `TEXT` | Preserve source value and SQL NULL as provided. |
| `page_number` (`String`) | `page_number` `TEXT` | Preserve source value and SQL NULL as provided. |
| `document_number` (`String`) | `document_number` `TEXT` | Preserve source value and SQL NULL as provided. |
| `char_count` (`Int32`) | `char_count` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `created_at` (`String`) | `created_at_raw` `TEXT`, `created_at_parsed` `TIMESTAMP WITHOUT TIME ZONE`, `created_at_status` `SMALLINT` | Parse `%Y-%m-%d %H:%M:%S` to timestamp without timezone; source has no offset. Current revision parses all rows. |
| `email_fields` (`String`) | `email_fields_raw` `TEXT`, `email_fields_parsed` `JSONB`, `email_fields_status` `SMALLINT` | Keep exact JSON text; parse with strict JSON parsing to JSONB. JSON `null` is SUCCESS; SQL NULL is MISSING; empty text EMPTY; invalid JSON FAILED. |

### `chunks` → `chunks` (existing mapping retained)

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve source chunk ID as primary key. |
| `document_id` (`Int64`) | `document_id` `BIGINT` | Required FK to `documents.id`; preserve the source ID. |
| `chunk_index` (`Int32`) | `chunk_index` `INTEGER` | Preserve source order. |
| `content` (`String`) | `content` `TEXT` | Preserve text exactly; not treated as a parsed field. |
| `token_count` (`Int32`) | `token_count` `INTEGER` | Preserve source count. |
| `char_start` (`Int32`) | `char_start` `INTEGER` | Preserve source offset. |
| `char_end` (`Int32`) | `char_end` `INTEGER` | Preserve source offset. |


### `entities` → `entities`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `document_id` (`Int64`) | `document_id_raw` `BIGINT`, `document_id` `BIGINT`, `document_match_status` `SMALLINT` | Preserve source ID in its own column; set document FK only for a validated exact source-ID match. 78 are unresolved in this revision. |
| `entity_type` (`String`) | `entity_type_id` `SMALLINT` | Exact source label maps to `enum_entity_types`; no case folding. |
| `value` (`String`) | `value_raw` `TEXT` | Preserve extracted mention exactly; do not normalize it into an asserted identity. |
| `normalized_value` (`String`) | `normalized_value_raw` `TEXT`, `normalized_value_parsed` `TEXT`, `normalization_rule` `TEXT` | Preserve the source column (entirely NULL here). No local normalization is currently applied, so parsed value and rule remain NULL. |

### `persons` → `persons`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `canonical_name` (`String`) | `canonical_name` `TEXT` | Preserve source value and SQL NULL as provided. |
| `slug` (`String`) | `slug` `TEXT` | Preserve source value and SQL NULL as provided. |
| `category` (`String`) | `category_id` `SMALLINT` | Exact source label maps to `enum_person_categories`. |
| `aliases` (`String`) | `aliases_raw` `TEXT`, `aliases_parsed` `JSONB`, `aliases_status` `SMALLINT` | Preserve JSON text; strict parse to JSONB array. SUCCESS on valid array; MISSING/EMPTY/FAILED distinguish source conditions. |
| `search_terms` (`String`) | `search_terms_raw` `TEXT`, `search_terms_parsed` `JSONB`, `search_terms_status` `SMALLINT` | Preserve JSON text; strict parse to JSONB array. SUCCESS on valid array; MISSING/EMPTY/FAILED distinguish source conditions. |
| `sources` (`String`) | `sources_raw` `TEXT`, `sources_parsed` `JSONB`, `sources_status` `SMALLINT` | Preserve JSON text; strict parse to JSONB array. SUCCESS on valid array; MISSING/EMPTY/FAILED distinguish source conditions. |
| `notes` (`String`) | `notes` `TEXT` | Preserve source value and SQL NULL as provided. |

### `kg_entities` → `kg_entities`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `name` (`String`) | `name` `TEXT` | Preserve source value and SQL NULL as provided. |
| `entity_type` (`String`) | `entity_type_id` `SMALLINT` | Exact source label maps to `enum_kg_entity_types`. |
| `description` (`String`) | `description` `TEXT` | Preserve source value and SQL NULL as provided. |
| `metadata` (`String`) | `metadata_raw` `TEXT`, `metadata_parsed` `JSONB`, `metadata_status` `SMALLINT` | Preserve JSON text; strict parse to JSONB object; keep raw even when parse fails. |

### `kg_relationships` → `kg_relationships`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `source_id` (`Int64`) | `source_id` `BIGINT` | Source KG ID; required FK to `kg_entities.id`. |
| `target_id` (`Int64`) | `target_id` `BIGINT` | Source KG ID; required FK to `kg_entities.id`. |
| `relationship_type` (`String`) | `relationship_type_id` `SMALLINT` | Exact source label maps to `enum_relationship_types`. |
| `weight` (`Float64`) | `weight` `DOUBLE PRECISION` | Preserve source value and SQL NULL as provided. |
| `evidence` (`String`) | `evidence` `TEXT` | Preserve source value and SQL NULL as provided. |
| `metadata` (`String`) | `metadata_raw` `TEXT`, `metadata_parsed` `JSONB`, `metadata_status` `SMALLINT` | Preserve JSON text; strict parse to JSONB object; keep raw even when parse fails. |

### `derived_events` → `derived_events`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `event_date` (`String`) | `event_date_raw` `TEXT`, `event_date_parsed` `DATE`, `event_date_status` `SMALLINT` | Strict `%Y-%m-%d` date parse; all non-NULL values in the current revision are valid. |
| `event_end_date` (`String`) | `event_end_date_raw` `TEXT`, `event_end_date_parsed` `DATE`, `event_end_date_status` `SMALLINT` | Strict `%Y-%m-%d` date parse; all non-NULL values in the current revision are valid. |
| `event_type` (`String`) | `event_type_id` `SMALLINT` | Exact source label maps to `enum_event_types`. |
| `track` (`String`) | `track_id` `SMALLINT` | Exact source label maps to `enum_event_tracks`. |
| `headline` (`String`) | `headline` `TEXT` | Preserve source value and SQL NULL as provided. |
| `location` (`String`) | `location` `TEXT` | Preserve source value and SQL NULL as provided. |
| `amount` (`Float64`) | `amount` `NUMERIC` | Preserve source value and SQL NULL as provided. |
| `currency` (`String`) | `currency` `TEXT` | Preserve source value and SQL NULL as provided. |
| `payer` (`String`) | `payer` `TEXT` | Preserve source value and SQL NULL as provided. |
| `payee` (`String`) | `payee` `TEXT` | Preserve source value and SQL NULL as provided. |
| `route_from` (`String`) | `route_from` `TEXT` | Preserve source value and SQL NULL as provided. |
| `route_to` (`String`) | `route_to` `TEXT` | Preserve source value and SQL NULL as provided. |
| `aircraft` (`String`) | `aircraft` `TEXT` | Preserve source value and SQL NULL as provided. |
| `time_of_day` (`String`) | `time_of_day_raw` `TEXT` | Preserve source value and SQL NULL as provided. |
| `confidence` (`String`) | `confidence_id` `SMALLINT` | Exact source category (`confirmed`/`tentative`) maps to `enum_event_confidences`; it is not a numeric probability. |
| `narrative` (`String`) | `narrative` `TEXT` | Preserve source value and SQL NULL as provided. |

### `event_participants` → `event_participants`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `event_id` (`Int64`) | `event_id` `BIGINT` | Required FK to `derived_events.id`. |
| `person_name` (`String`) | `person_name` `TEXT` | Preserve source value and SQL NULL as provided. |
| `role` (`String`) | `role_id` `SMALLINT` | Exact source label maps to `enum_participant_roles`. |

### `event_sources` → `event_sources`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `event_id` (`Int64`) | `event_id` `BIGINT` | Required FK to `derived_events.id`. |
| `file_key` (`String`) | `file_key` `TEXT`, `document_id` `BIGINT`, `document_match_status` `SMALLINT` | Retain raw source key; optional document FK only when exact key resolves. Do not treat every evidence key as a document. |

### `financial_transactions` → `financial_transactions`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `file_key` (`String`) | `file_key` `TEXT`, `document_id` `BIGINT` | Retain source key and its required resolved document FK; all keys resolve in this revision. |
| `dataset` (`String`) | `dataset_id` `SMALLINT` | Exact source label maps to `enum_datasets`. |
| `transaction_date` (`String`) | `transaction_date_raw` `TEXT`, `transaction_date_parsed` `DATE`, `transaction_date_status` `SMALLINT` | Strict `%Y-%m-%d` date parse; all non-NULL values in this revision are valid. NULL stays MISSING; malformed future values are FAILED. |
| `amount` (`Float64`) | `amount` `NUMERIC` | Convert Float64 with `Decimal(str(value))`; no forced two-decimal rounding. Preserve NULL, sign, and available decimal digits. |
| `currency` (`String`) | `currency` `TEXT` | Preserve source value and SQL NULL as provided. |
| `merchant_name` (`String`) | `merchant_name` `TEXT` | Preserve source value and SQL NULL as provided. |
| `merchant_raw` (`String`) | `merchant_raw` `TEXT` | Preserve source value and SQL NULL as provided. |
| `merchant_category` (`String`) | `merchant_category` `TEXT` | Preserve source value and SQL NULL as provided. |
| `location` (`String`) | `location` `TEXT` | Preserve source value and SQL NULL as provided. |
| `cardholder` (`String`) | `cardholder` `TEXT` | Preserve source value and SQL NULL as provided. |
| `description` (`String`) | `description` `TEXT` | Preserve source value and SQL NULL as provided. |
| `card_type` (`String`) | `card_type` `TEXT` | Preserve source value and SQL NULL as provided. |
| `account_digits` (`String`) | `account_digits` `TEXT` | Preserve source value and SQL NULL as provided. |
| `statement_date` (`String`) | `statement_date_raw` `TEXT`, `statement_date_parsed` `DATE`, `statement_date_status` `SMALLINT` | Strict `%Y-%m-%d` date parse; all non-NULL values in this revision are valid. NULL stays MISSING; malformed future values are FAILED. |
| `flight_from` (`String`) | `flight_from` `TEXT` | Preserve source value and SQL NULL as provided. |
| `flight_to` (`String`) | `flight_to` `TEXT` | Preserve source value and SQL NULL as provided. |
| `flight_carrier` (`String`) | `flight_carrier` `TEXT` | Preserve source value and SQL NULL as provided. |
| `flight_departure` (`String`) | `flight_departure_raw` `TEXT`, `flight_departure_parsed` `DATE`, `flight_departure_status` `SMALLINT` | Strict `%Y-%m-%d` date parse; all non-NULL values in this revision are valid. NULL stays MISSING; malformed future values are FAILED. |
| `flight_ticket` (`String`) | `flight_ticket` `TEXT` | Preserve source value and SQL NULL as provided. |
| `flight_passenger` (`String`) | `flight_passenger` `TEXT` | Preserve source value and SQL NULL as provided. |
| `source_page` (`Int32`) | `source_page` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `extraction_model` (`String`) | `extraction_model_raw` `TEXT`, `extraction_model_id` `SMALLINT`, `extraction_model_status` `SMALLINT` | Preserve original label; exact match to `enum_models`; status is SUCCESS for the observed `deepseek-chat` value. |
| `extraction_confidence` (`Float64`) | `extraction_confidence` `DOUBLE PRECISION` | Preserve source value and SQL NULL as provided. |

### `curated_docs` → `curated_docs`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `id` (`Int64`) | `id` `BIGINT` | Preserve original source ID as the primary key; gaps remain. |
| `file_key` (`String`) | `file_key` `TEXT`, `document_id` `BIGINT` | Retain source key and required resolved document FK; all keys resolve in this revision. |
| `subject` (`String`) | `subject_id` `SMALLINT` | Exact label maps to `enum_curated_subjects`. |
| `status` (`String`) | `curated_status` `SMALLINT` | Exact source label maps to `enum_curated_statuses`; current value is gold. |
| `tier` (`String`) | `tier_id` `SMALLINT` | Exact label maps to `enum_curated_tiers`. |
| `category` (`String`) | `category` `TEXT` | Preserve source value and SQL NULL as provided. |
| `doc_date` (`String`) | `doc_date_raw` `TEXT`, `doc_date_parsed` `DATE`, `doc_date_status` `SMALLINT` | Keep original date/range/prose. Rule `curated_doc_date_v1` reuses the full-day formats in `documents.py` after its explicit weekday/month spelling replacements. Ranges or year/month-only values are PARTIAL; invalid calendar values or unsupported non-empty strings are FAILED. |
| `doc_from` (`String`) | `doc_from` `TEXT` | Preserve source value and SQL NULL as provided. |
| `doc_to` (`String`) | `doc_to` `TEXT` | Preserve source value and SQL NULL as provided. |
| `headline` (`String`) | `headline` `TEXT` | Preserve source value and SQL NULL as provided. |
| `key_quote` (`String`) | `key_quote` `TEXT` | Preserve source value and SQL NULL as provided. |
| `detail` (`String`) | `detail` `TEXT` | Preserve source value and SQL NULL as provided. |
| `thread_value` (`String`) | `thread_value` `TEXT` | Preserve source value and SQL NULL as provided. |
| `also_appears_as` (`String`) | `also_appears_as_raw` `TEXT`, `also_appears_as_parsed` `JSONB`, `also_appears_as_status` `SMALLINT` | Keep exact source text; strict JSONB array parse; distinguish MISSING, EMPTY, FAILED, and successful JSON. |

### `provenance/runs` → `provenance_runs`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `run_id` (`String`) | `run_id` `TEXT` | Preserve source value and SQL NULL as provided. |
| `started_at` (`String`) | `started_at_raw` `TEXT`, `started_at_parsed` `TIMESTAMPTZ`, `started_at_status` `SMALLINT` | Parse ISO timestamp including its explicit offset to TIMESTAMPTZ; NULL is MISSING. |
| `completed_at` (`String`) | `completed_at_raw` `TEXT`, `completed_at_parsed` `TIMESTAMPTZ`, `completed_at_local_parsed` `TIMESTAMP WITHOUT TIME ZONE`, `completed_at_status` `SMALLINT` | Parse offset-bearing ISO timestamps to TIMESTAMPTZ. For the three values without offsets, preserve a wall-clock TIMESTAMP in `completed_at_local_parsed` and mark PARTIAL; never assign a timezone. |
| `status` (`String`) | `run_status` `SMALLINT` | Exact source value maps to `enum_run_statuses`. |
| `input_dir` (`String`) | `input_dir` `TEXT` | Preserve source value and SQL NULL as provided. |
| `output_name` (`String`) | `output_name` `TEXT` | Preserve source value and SQL NULL as provided. |
| `model` (`String`) | `model_raw` `TEXT`, `model_status` `SMALLINT`, rows in `provenance_run_models` (`model_id` FK) | Preserve exact source string; exact lookup in `enum_models`. Current values are single model names. |
| `dpi` (`Int32`) | `dpi` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `workers` (`Int32`) | `workers` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `rpm` (`Int32`) | `rpm` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `git_commit` (`String`) | `git_commit` `TEXT` | Preserve source value and SQL NULL as provided. |
| `hostname` (`String`) | `hostname` `TEXT` | Preserve source value and SQL NULL as provided. |
| `total_files` (`Int32`) | `total_files` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `success_count` (`Int32`) | `success_count` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `fail_count` (`Int32`) | `fail_count` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `input_tokens` (`Int64`) | `input_tokens` `BIGINT` | Preserve source value and SQL NULL as provided. |
| `output_tokens` (`Int64`) | `output_tokens` `BIGINT` | Preserve source value and SQL NULL as provided. |
| `cost_usd` (`Float64`) | `cost_usd` `NUMERIC` | Preserve source value and SQL NULL as provided. |
| `last_heartbeat` (`String`) | `last_heartbeat_raw` `TEXT`, `last_heartbeat_parsed` `TIMESTAMPTZ`, `last_heartbeat_status` `SMALLINT` | Parse ISO timestamp including its explicit offset to TIMESTAMPTZ; NULL is MISSING. |

### `provenance/files` → `provenance_files`

| Source field (Parquet type) | Target column(s) (PostgreSQL type) | Conversion / status rule |
|---|---|---|
| `file_key` (`String`) | `file_key` `TEXT`, `document_id` `BIGINT`, `document_match_status` `SMALLINT` | Preserve source key; optional exact match to document. Five values are unresolved in this revision. |
| `output_name` (`String`) | `output_name` `TEXT` | Preserve source value and SQL NULL as provided. |
| `pdf_path` (`String`) | `pdf_path` `TEXT` | Preserve source value and SQL NULL as provided. |
| `pdf_sha256` (`String`) | `pdf_sha256_raw` `TEXT`, `pdf_sha256_parsed` `BYTEA`, `pdf_sha256_status` `SMALLINT` | Keep lowercase/uppercase hex source text; exactly 64 hex characters decode with `bytes.fromhex` to 32-byte BYTEA. NULL is MISSING; malformed non-empty is FAILED. |
| `pdf_size_bytes` (`Int64`) | `pdf_size_bytes` `BIGINT` | Preserve source value and SQL NULL as provided. |
| `status` (`String`) | `file_status` `SMALLINT` | Exact source value maps to `enum_file_statuses`. |
| `output_path` (`String`) | `output_path` `TEXT` | Preserve source value and SQL NULL as provided. |
| `output_sha256` (`String`) | `output_sha256_raw` `TEXT`, `output_sha256_parsed` `BYTEA`, `output_sha256_status` `SMALLINT` | Same SHA-256 rule; 32-byte BYTEA after validated hex decoding. |
| `first_seen_at` (`String`) | `first_seen_at_raw` `TEXT`, `first_seen_at_parsed` `TIMESTAMPTZ`, `first_seen_at_status` `SMALLINT` | Parse ISO timestamp with explicit offset to TIMESTAMPTZ. |
| `processed_at` (`String`) | `processed_at_raw` `TEXT`, `processed_at_parsed` `TIMESTAMPTZ`, `processed_at_status` `SMALLINT` | Parse ISO timestamp with explicit offset to TIMESTAMPTZ. |
| `run_id` (`String`) | `run_id` `TEXT` | Preserve text exactly; optional FK to `provenance_runs.run_id` (source IDs include non-UUID strings). |
| `input_tokens` (`Int64`) | `input_tokens` `BIGINT` | Preserve source value and SQL NULL as provided. |
| `output_tokens` (`Int64`) | `output_tokens` `BIGINT` | Preserve source value and SQL NULL as provided. |
| `api_latency_ms` (`Int64`) | `api_latency_ms` `BIGINT` | Preserve source value and SQL NULL as provided. |
| `attempts` (`Int32`) | `attempts` `INTEGER` | Preserve source value and SQL NULL as provided. |
| `error_message` (`String`) | `error_message` `TEXT` | Preserve source value and SQL NULL as provided. |
| `model_used` (`String`) | `model_used_raw` `TEXT`, `model_used_status` `SMALLINT`, rows in `provenance_file_models` (`model_id` FK) | Preserve exact comma-separated source string; split on comma, trim surrounding whitespace, map each token exactly to `enum_models`. The observed individual names map to SUCCESS; an unrecognized token is logged and makes the list PARTIAL if other tokens resolve, otherwise FAILED. |
| `validation_score` (`Int32`) | `validation_score` `SMALLINT` | Preserve source value and SQL NULL as provided. |

## Derived status and relationship values

| Target column | Rule |
|---|---|
| `enum_parse_statuses` | Seed `SUCCESS`, `PARTIAL`, `MISSING`, `FAILED`, and `EMPTY`. Importer assigns a status for every parsed source field, including SQL NULL. |
| `document_match_status` | FK to `enum_match_statuses`: MATCHED only after validated resolution; otherwise UNRESOLVED while retaining the original source ID/key. |
| `run_status`, `file_status`, `curated_status` | Exact source workflow labels map to `enum_run_statuses`, `enum_file_statuses`, and `enum_curated_statuses`; these are separate from parse outcomes. |
| `entities.normalized_value_parsed`, `normalization_rule` | No local normalization is performed for this revision. Keep upstream `normalized_value_raw` (all NULL); parsed value and rule remain NULL. If a rule is added, record its name/version, such as a separately approved trim/case-fold rule. |
| `provenance_run_models` | One ordered model link for each model token in `provenance_runs.model_raw`. |
| `provenance_file_models` | Split `model_used_raw` on commas, trim each token, exact-match each mode. Raw combined source label remains stored. |
| `pdf_sha256_parsed`, `output_sha256_parsed` | Validate 64 hexadecimal characters, decode to exactly 32 bytes, store BYTEA. Keep exact source hex in corresponding `_raw` column. |
| Timezone-less run completion | Store as `completed_at_local_parsed` with PARTIAL. Do not populate `completed_at_parsed` or invent a timezone. |

No source field whose values are NULL/empty throughout this revision is dropped. This is a DDL and mapping specification; the importer still needs to populate category lookups, match rows, model bridge rows, and parse status values consistently.
