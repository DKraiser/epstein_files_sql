# Steps

## Downloading raw data

First files downloaded are: 

- `data/documents/documents-00000-of-00015.parquet`
- `data/chunks/chunks-00000-of-00011.parquet`

Data were accessed from repository `kabasshouse/epstein-data`, branch `main`, commit `133ef9f0a539fafc270cde8fa8638dc38d89968d` and downloaded using [downloader](###Python).

## Postgres

Data about running DB server: 

- Username: `postgres`
- Host: `localhost`
- Port: `5433`
- Database: `dbs2`
- Version: PostgreSQL 18.6 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit

## Python

Scripts (located in [`src/python`](src/python/)): 
- `small_download.py` - downloads `.parquet` files from hugging face via hugging face hub;
- `small_overview.py` - shows the schema and head of dataframes;
- `small_import.py` - imports dataframe data into database;
- `defines.py` - defines used in other scripts.

## SQL

Scripts (located in [`src/sql`](src/sql/)): 
- `schema.sql` - schema;
- `seed.sql` - seed data for datasets, ocr_sources;

# Quickstart

```bash
# Start postgres with
#
# Username: postgres
# Host: localhost
# Port: 5433
# Version: PostgreSQL 18.6 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
docker compose up

# Create and activate python environment
python3 -m venv c1/src/.venv 
source c1/src/.venv/bin/activate
c1/src/.venv/bin/python -m pip install -r c1/src/requirements.txt

# Download needed .parquet files
c1/src/.venv/bin/python c1/src/python/small_download.py

# Overview dataset structure
c1/src/.venv/bin/python c1/src/python/small_overview.py

# Run `c1/src/sql/schema.sql` and `c1/src/sql/seed.sql` 

# Import data for checkpoint 1
c1/src/.venv/bin/python c1/src/python/small_import.py
```

# Data mapping 

## `documents`

| Dataset field         | Dataset type | Postgres type  | Remarks                           |
| --------------------- | ------------ | ----------     | --------------------------------- |
| `id`                  |  Int64       | BIGSERIAL      |                                   |
| `created_at`          |  String      | TIMESTAMP      |                                   |
| `char_count`          |  String      | INTEGER        |                                   |
| `dataset`             |  String      | SMALLINT       | FK to `datasets` enum table       |
| `document_type`       |  String      | SMALLINT       | FK to `document_types` enum table |
| `ocr_source`          |  String      | SMALLINT       | FK to `ocr_sources` enum table    |
| `is_photo`            |  Boolean     | BOOLEAN        |                                   |
| `has_stamps`          |  Boolean     | BOOLEAN        |                                   |
| `has_handwriting`     |  Boolean     | BOOLEAN        |                                   |
| `file_key`            |  String      | TEXT           |                                   |
| `full_text`           |  String      | TEXT           |                                   |
| `date`                |  String      | TEXT           |                                   |
| `additional_notes`    |  String      | TEXT           |                                   |
| `page_number`         |  Int32       | TEXT           |                                   |
| `document_number`     |  String      | TEXT           |                                   |
| `email_fields`        |  String      | JSONB          |                                   |

## `chunks`

| Dataset field | Dataset type  | Postgres type | Remarks                      |
| ------------- | ------------- | ---------     | ---------------------------- |
| `id`          | Int64         | BIGSERIAL     |                              |
| `document_id` | Int64         | BIGINT        | FK to `documents` enum table |
| `chunk_index` | Int32         | INTEGER       |                              |
| `token_count` | Int32         | INTEGER       |                              |
| `char_start`  | Int32         | INTEGER       |                              |
| `char_end`    | Int32         | INTEGER       |                              |
| `content`     | String        | TEXT          |                              |

# Theoretical questions

| Precise lookup target         | Operator          | Index     | Risk                                                              |
| ----------------------------- | ----------------- | --------- | ----------------------------------------------------------------- |
| `file_key` (`documents`)      | `=`               | B-tree    | Optimizer can choose sequential scan strategy so index is unused  |
| substring                     | `LIKE`, `ILIKE`   | GIN       | For large text GIN using `pg_trgm` extension grows very fast      |
| `JSONB` containment           | `@>`, `@<`        | GIN       | Index grows very fast                                             |
| Time range in append-only log | `<=>`             | B-tree    | As log continuously grows, index becomes giant                    |

# AI statement analysis

| Date | Model | Goal of using | Statement | Risk or hypothesis | Test or primary source | Observed result | Approved, fixed or refused |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 9.18.26 | GPT 5.6-Luna | Designing an efficient PostgreSQL schema for documents and chunks. Optimizing data types for PostgreSQL storage and querying. | A hybrid PostgreSQL schema featuring inline text columns and enum tables is simple and efficient option. | Hypothesis: correct schema and datatypes will save memory and provide integrity along the database. Risk: messy or unparseable source strings could cause type-casting failures during direct import. | Sources: README.md and PROVENANCE.md | Generated and fixed `schema.sql` for `documents` and `chunks`, described in `data-mappings.md` | Approved, fixed |

Model recommended to use smallest acceptable types and enum tables for `ocr_sources` and `datasets`, but made mistakes in naming datasets. Manually was:
- changed order of columns in tables, which lead to lowering of an average row length;
- changed some types (`date` in `documents` etc), because data in columns included unparseable values;
- added `document_types` enum table as `document_type` column of `documents` contained a lot of duplicate values. 