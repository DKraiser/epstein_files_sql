"""Definitions used in other scripts."""

from pathlib import Path


REPOSITORY = "kabasshouse/epstein-data"
REVISION = "133ef9f0a539fafc270cde8fa8638dc38d89968d"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ENV = PROJECT_ROOT / ".env"

DEFAULT_FILES_PATHS: tuple[list[str], ...] = (
    [ "data/documents/documents-00000-of-00015.parquet" ],
    [ "data/chunks/chunks-00000-of-00011.parquet" ]
)