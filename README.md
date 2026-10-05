# Author

**Name :** Oles Andrela

**AIS ID:** 136166

**Academic year:** 2026/2027


# Used tools and packages

- `python` v3.13.5:
    - `polars`: 1.44.2
    - `psycopg[binary]`: 3.3.5
    - `python-dotenv`: 1.2.2
    - `huggingface-hub`: 1.4.1

- `postgresql` v18.6


# How to run

```bash
# Start postgres
docker compose up

# Create and activate python environment
python3 -m venv src/.venv && \
    source src/.venv/bin/activate && \
    export PYTHONPATH="$(pwd)/src" && \
    python -m pip install -r src/requirements.txt

# Download needed .parquet files
python src/python/downloader.py

# Create layers_profile.json
python -m python.data_profiler

# Import data from dataset
python -m python.importer

```