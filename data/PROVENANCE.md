# Data Provenance

Per-table documentation of data sources, extraction methods, and quality notes.

## documents

**1,424,673 rows.** One row per PDF file from the DOJ Epstein release.

- **856,028 files** processed with **Gemini 2.5 Flash Lite** ($0.10/$0.40 per 1M tokens). Full structured extraction: document type classification, date parsing, entity extraction, handwriting/stamp detection, photo description.
- **531,279 files** (DataSet 9) imported from the [rhowardstone/Epstein-research-data](https://github.com/rhowardstone/Epstein-research-data) community project using **Tesseract OCR**. Raw text only — no entity extraction or document classification. These have `ocr_source = 'tesseract-community'`.
- **1,377 files** originally Tesseract, upgraded to Gemini in v2 (604 from DS10, 773 from other datasets).
- **37,369 files** have `is_photo = true` (photos, stamps, blank pages).
- `email_fields` column (new in v2): JSON-encoded email metadata (from, to, cc, subject, date) for email-type documents.

Distinguish OCR source: `ocr_source IS NULL` = Gemini, `ocr_source = 'tesseract-community'` = community.

## entities

**10,629,198 rows.** Named entities extracted from documents.

- Gemini documents: entities come from the structured JSON extraction prompt (types: person, organization, location, date, reference_number, email_address, phone_number, monetary_amount).
- Community documents: entities from post-processing NER pipeline.
- Entity `normalized_value` provides cleaned/canonical forms where available.

## chunks

**2,193,090 rows.** Text chunks for RAG (retrieval-augmented generation).

- ~800 token target per chunk with overlap at sentence boundaries.
- `char_start` and `char_end` map back to the parent document's `full_text`.

## embeddings_chunk

**2,111,356 rows.** 768-dimensional float32 vectors from `gemini-embedding-001`.

- ~96% coverage (documents with malformed text excluded).
- Stored as `list<float32>` in Parquet.
- `source_text_hash` links to the chunk text that was embedded.

## persons

**1,614 rows.** Curated person registry with canonical names, aliases, and categories.

- Categories: perpetrator, victim, associate, other.
- `aliases` field: JSON array of known alternate names/spellings.
- `search_terms`: additional search patterns for entity resolution.
- Community-curated from multiple sources.

## kg_entities / kg_relationships

**467 entities, 2,198 relationships.** Knowledge graph connecting people, organizations, and locations.

- Relationship types: traveled_with, associated_with, employed_by, legal_representative, financial_connection, etc.
- `weight` indicates strength of connection (co-occurrence frequency).
- `evidence` field links to source document file_keys.

## recovered_redactions

**37,870 rows.** Text recovered from under redaction bars using ML reconstruction.

- `interest_score` (0-100) ranks significance of recovered content.
- `names_found` lists person names detected in recovered text.
- Experimental quality — treat as leads, not verified text.

## financial_transactions (NEW in v2)

**49,770 rows.** Credit card and bank transaction records extracted with DeepSeek.

- Source: DOJ-released credit card statements and bank records (DataSet 10/11).
- Extraction model: DeepSeek (per-page structured extraction).
- 31% of raw extractions quarantined for quality issues (hallucinated amounts, duplicate entries, garbled OCR). Only clean records included.
- Flight fields (flight_from, flight_to, flight_carrier, flight_passenger) populated for airline purchases.
- Key cardholders: JEFFREY E EPSTEIN, GHISLAINE MAXWELL, KARYNA SHULIAK, HBRK ASSOCIATES, TERRAMAR PROJECT.

## communication_records (NEW in v2)

**128 rows.** Phone call and cell-site/CDR records.

- Source: DOJ-released phone records.
- 99.8% of raw extractions quarantined (CDR data has very high hallucination rates). Only 128 high-confidence records included.
- Fields: call date/time, duration, direction, location, number called, provider.

## investigative_records (NEW in v2)

**143 rows.** Law enforcement reports, evidence recovery logs, and vehicle/property records.

- Source: FBI, PBSO, and other agency reports in DOJ release.
- 87% of raw extractions quarantined. Only 143 verified records included.
- Record types: law_enforcement_report, evidence_recovery_log, vehicle_property_record.

## derived_events (NEW in v2)

**3,038 events** with **5,751 participants** and **21,910 source document links.**

Three analysis tracks reconstruct Epstein's activities:

- **Calendar track**: Meetings, dinners, appointments from Lesley Groff's daily schedule emails (2011-2016).
- **Travel track**: Flights, hotel stays, ground transport from schedule transitions and AmEx bookings.
- **Financial track**: Gift exchanges, institutional donations, major purchases from bank statements and emails.

Each event links to source EFTA documents via `event_sources` and participants via `event_participants`.

## curated_docs (NEW in v2)

**5,766 gold documents** across 5 investigation subjects: Hoffman (1,526), Gates (2,069), Summers (739), Clinton (765), Black (667).

- Each document annotated with: tier (NUCLEAR/CRITICAL/HIGH/MEDIUM/SUPPORTING), category, date, sender, recipient, headline, key quote, investigative detail.
- `also_appears_as`: JSON array of duplicate EFTA file_keys for the same document.
- Only gold-status documents exported (24,706 rejected documents excluded).

## provenance/files

**1,387,775 rows.** One row per processed file with full pipeline metadata.

- `pdf_sha256`: SHA-256 hash of input PDF.
- `output_sha256`: SHA-256 hash of output JSON.
- `model_used`: OCR model (gemini-2.5-flash-lite, tesseract-community, etc.).
- `input_tokens` / `output_tokens`: API token consumption.
- `validation_score`: automated quality score (0-100).

## provenance/audit_log

**3,711,609 rows.** Append-only forensic audit trail.

- Every pipeline action (file processed, error, retry, fix applied) is logged.
- `checksum` field provides tamper detection on critical operations.
- Timestamps in ISO-8601 format.

## provenance/runs

**123 rows.** Pipeline execution records with timing, worker counts, and costs.
