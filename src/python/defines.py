"""Definitions used in other scripts."""

from pathlib import Path

REPOSITORY = "kabasshouse/epstein-data"
REVISION = "133ef9f0a539fafc270cde8fa8638dc38d89968d"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ENV = PROJECT_ROOT / ".env"
PROJECT_DATASET_ROOT = PROJECT_ROOT / "data"
_dict: dict [str, int] = {
    "documents": 15,
    "chunks": 11,
    "entities": 18,
    "persons": 1,
    "persons": 1,
    "kg_entities": 1,
    "kg_relationships": 1,
    "derived_events": 1,
    "event_participants": 1,
    "event_sources": 1,
    "financial_transactions": 1,
    "curated_docs": 1,
    "provenance/runs": 1,
    "provenance/files": 3
}
REMOTE_FILES_PATHS: dict[str, list[str]] = dict()
LOCAL_FILES_PATHS: dict[str, list[Path]] = dict()

for (name, count) in _dict.items(): 
    REMOTE_FILES_PATHS[name] = [
        f"data/{name}/{name.split("/")[-1]}-{str(x).zfill(5)}-of-{str(count).zfill(5)}.parquet"
            for x in range (0, count)
    ]
    LOCAL_FILES_PATHS[name] = [
        Path(f"{PROJECT_DATASET_ROOT}/{path}") for path in REMOTE_FILES_PATHS[name]
    ]