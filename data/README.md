---
license: cc-by-4.0
task_categories:
  - text-classification
  - question-answering
  - feature-extraction
language:
  - en
tags:
  - legal
  - ocr
  - documents
  - foia
  - knowledge-graph
  - financial
size_categories:
  - 1M<n<10M
pretty_name: "Epstein DOJ Document Archive (OCR + Structured Data)"
---

# Epstein DOJ Document Archive v2

**1.42 million OCR'd documents** from the Department of Justice Jeffrey Epstein document release, with structured entity extraction, vector embeddings, financial transactions, communication records, and a forensic audit trail.

Frontend: [epstein.academy](https://epstein.academy)

## What's New in v2

- **10.6M entities** (up from 8.5M) — expanded NER extraction
- **2.1M chunk embeddings** (up from 1.96M) — more documents embedded
- **49,770 financial transactions** — credit card and bank records (DeepSeek extraction)
- **3,038 derived events** — reconstructed calendar, travel, and financial timeline
- **5,766 curated gold documents** — expert-annotated research catalog across 5 subjects
- **143 investigative records** — law enforcement reports and evidence logs
- **128 communication records** — phone call and CDR data
- **604 DS10 files upgraded** from Tesseract to Gemini OCR

## Quick Start

### HuggingFace Datasets (streaming)

```python
from datasets import load_dataset

# Stream documents without downloading everything
ds = load_dataset("kabasshouse/epstein-data", "documents", streaming=True)
for doc in ds["train"]:
    print(doc["file_key"], doc["document_type"], len(doc["full_text"] or ""))
    break
```

### DuckDB (direct Parquet queries)

```sql
-- Query directly from HuggingFace without downloading
SELECT file_key, document_type, date, char_count
FROM 'hf://datasets/kabasshouse/epstein-data/data/documents/*.parquet'
WHERE document_type = 'Email'
  AND date LIKE '2015%'
ORDER BY date
LIMIT 20;

-- Financial transactions
SELECT transaction_date, amount, merchant_name, cardholder
FROM 'hf://datasets/kabasshouse/epstein-data/data/financial_transactions/*.parquet'
WHERE cardholder LIKE '%EPSTEIN%'
  AND amount > 1000
ORDER BY amount DESC
LIMIT 20;

-- Curated gold documents
SELECT file_key, subject, tier, headline, key_quote
FROM 'hf://datasets/kabasshouse/epstein-data/data/curated_docs/*.parquet'
WHERE tier = 'NUCLEAR'
ORDER BY subject, doc_date;
```

### Pandas

```python
import pandas as pd

docs = pd.read_parquet("hf://datasets/kabasshouse/epstein-data/data/documents/")
print(f"{len(docs):,} documents")
print(docs.groupby("dataset").size().sort_values(ascending=False))
```

## Data Layers

### Core Content

| Layer | Rows | Description |
|-------|------|-------------|
| `documents` | 1,424,673 | Full OCR text, document type, date, photo flag |
| `entities` | 10,629,198 | Named entities (person, org, location, date, etc.) |
| `chunks` | 2,193,090 | ~800-token text chunks for RAG |
| `embeddings_chunk` | 2,111,356 | 768-dim Gemini embeddings per chunk |

### Knowledge & Analysis

| Layer | Rows | Description |
|-------|------|-------------|
| `persons` | 1,614 | Curated person registry (name, aliases, category) |
| `kg_entities` | 467 | Knowledge graph nodes |
| `kg_relationships` | 2,198 | Knowledge graph edges (traveled_with, associated_with, etc.) |
| `recovered_redactions` | 37,870 | ML-recovered text from redacted pages |
| `curated_docs` | 5,766 | Expert-annotated gold documents (5 subjects, tiered) |

### Structured Records (NEW in v2)

| Layer | Rows | Description |
|-------|------|-------------|
| `financial_transactions` | 49,770 | Credit card & bank transactions |
| `derived_events` | 3,038 | Reconstructed calendar/travel/financial events |
| `event_participants` | 5,751 | People linked to derived events |
| `event_sources` | 21,910 | Source documents for derived events |
| `investigative_records` | 143 | Law enforcement reports & evidence logs |
| `communication_records` | 128 | Phone call & CDR records |

### Provenance

| Layer | Rows | Description |
|-------|------|-------------|
| `provenance/files` | 1,387,775 | Per-file processing metadata + SHA-256 checksums |
| `provenance/audit_log` | 3,711,609 | Append-only forensic audit trail |
| `provenance/runs` | 123 | Pipeline execution records |

## Datasets

| Dataset | Files | Source |
|---------|-------|--------|
| DataSet 1 | 3,158 | DOJ EFTA release |
| DataSet 2 | 574 | DOJ EFTA release |
| DataSet 3 | 67 | DOJ EFTA release |
| DataSet 4 | 152 | DOJ EFTA release |
| DataSet 5 | 120 | DOJ EFTA release |
| DataSet 6 | 13 | DOJ EFTA release |
| DataSet 7 | 17 | DOJ EFTA release |
| DataSet 8 | 10,595 | DOJ EFTA release |
| DataSet 9 | 531,279 | DOJ EFTA release (community Tesseract OCR) |
| DataSet 10 | 503,154 | DOJ EFTA release |
| DataSet 11 | 331,655 | DOJ EFTA release |
| DataSet 12 | 152 | DOJ EFTA release |
| FBIVault | 22 | FBI Vault FOIA release |
| HouseOversightEstate | 4,892 | House Oversight Committee |

**468 unrecoverable failures** (corrupt/empty source PDFs). Full failure catalog in `release/epstein_problems.json`.

## OCR Sources

- **Gemini 2.5 Flash Lite**: 856,028 files — structured JSON output with entities, document classification, and metadata
- **Tesseract (community)**: 531,279 files — raw text only (DataSet 9, community gap-fill imports)
- **Upgraded**: 1,377 files originally processed with Tesseract, now re-processed with Gemini

Distinguish OCR source via the `ocr_source` column: `NULL` = Gemini, `'tesseract-community'` = community Tesseract.

## Curated Documents

The `curated_docs` layer contains 5,766 expert-annotated gold documents across 5 investigation subjects:

| Subject | Gold Docs | Tiers |
|---------|-----------|-------|
| Hoffman | 1,526 | NUCLEAR / CRITICAL / HIGH / MEDIUM / SUPPORTING |
| Gates | 2,069 | NUCLEAR / CRITICAL / HIGH / MEDIUM / SUPPORTING |
| Summers | 739 | NUCLEAR / CRITICAL / HIGH / MEDIUM / SUPPORTING |
| Clinton | 765 | NUCLEAR / CRITICAL / HIGH / MEDIUM / SUPPORTING |
| Black | 667 | NUCLEAR / CRITICAL / HIGH / MEDIUM / SUPPORTING |

Each entry includes: tier, category, date, sender/recipient, headline, key quote, and investigative detail.

## Financial Transactions

49,770 clean records extracted from credit card statements and bank records using DeepSeek. Includes:

- Transaction date, amount, currency, merchant
- Cardholder name (Epstein, Maxwell, Shuliak, etc.)
- Flight data (origin, destination, carrier, passenger) for airline purchases
- Merchant category classification

31% of raw extractions were quarantined for quality issues and excluded from this release.

## License

CC-BY-4.0. Source documents are U.S. government public records.

## Citation

```bibtex
@dataset{epstein_archive_2026,
  title={Epstein DOJ Document Archive},
  author={kabasshouse},
  year={2026},
  url={https://huggingface.co/datasets/kabasshouse/epstein-data},
  version={2.0}
}
```
