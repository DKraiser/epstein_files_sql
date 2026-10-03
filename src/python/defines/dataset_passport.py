from pathlib import Path
from .main_constants import PROJECT_ROOT


REPOSITORY = "kabasshouse/epstein-data"
REVISION = "133ef9f0a539fafc270cde8fa8638dc38d89968d"

PROJECT_DATASET_ROOT = PROJECT_ROOT / "data"
layers_and_counts: dict [str, int] = {
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

for (layer, count) in layers_and_counts.items(): 
    REMOTE_FILES_PATHS[layer] = [
        f"data/{layer}/{layer.split("/")[-1]}-{str(x).zfill(5)}-of-{str(count).zfill(5)}.parquet"
            for x in range (0, count)
    ]
    LOCAL_FILES_PATHS[layer] = [
        Path(f"{PROJECT_DATASET_ROOT}/{path}") for path in REMOTE_FILES_PATHS[layer]
    ]