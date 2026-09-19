from pathlib import Path

REPOSITORY = "kabasshouse/epstein-data"
REVISION = "133ef9f0a539fafc270cde8fa8638dc38d89968d"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FILES_PATHS = (
    "data/documents/documents-00000-of-00015.parquet",
    "data/chunks/chunks-00000-of-00011.parquet",
)

FULL_FILES_PATHS: tuple[str, ...] = ()
