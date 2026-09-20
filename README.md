# Overview

Task 1 of DBS2 subject. 

**Author:** Oles Andrela

## Checkpoint 1

### Downloading raw data

First files downloaded are: 

- `data/documents/documents-00000-of-00015.parquet`
- `data/chunks/chunks-00000-of-00011.parquet`

Data were accessed from repository `kabasshouse/epstein-data`, branch `main`, commit `133ef9f0a539fafc270cde8fa8638dc38d89968d` and downloaded using downloader.

### Postgres

Data about running DB server: 

- Username: `postgres`
- Host: `localhost`
- Port: `5433`
- Database: `dbs2`
- Version: PostgreSQL 18.6 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit

### Python

Scripts (located in [`src/python`](src/python/)): 
- `download.py` - downloads `.parquet` files from hugging face via hugging face hub;
- `overview.py` - shows the schema and head of dataframes;
- `small_import.py` - imports dataframe data into database;
- `defines.py` - defines used in other scripts.

### SQL

Scripts (located in [`src/sql`](src/sql/)): 
- `schema.sql` - schema;
- `seed.sql` - seed data for datasets, ocr_sources;

## Quickstart

```bash
# Start postgres with
#
# Username: postgres
# Host: localhost
# Port: 5433
# Version: PostgreSQL 18.6 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
docker compose up

# Create and activate python environment
python3 -m venv src/.venv 
source src/.venv/bin/activate
src/.venv/bin/python -m pip install -r src/requirements.txt

# Download needed .parquet files
# Unless flag --full is provided, only 
# data/documents/documents-00000-of-00015 and 
# data/chunks/chunks-00000-of-00011 are downloaded
src/.venv/bin/python src/python/download.py

# Overview dataset structure
# Unless flag --full is provided, only 
# data/documents/documents-00000-of-00015 and 
# data/chunks/chunks-00000-of-00011 are shown
src/.venv/bin/python src/python/overview.py

# Run `schema.sql` and `seed.sql` 

# Import data for checkpoint 1
src/.venv/bin/python src/python/import.py
```