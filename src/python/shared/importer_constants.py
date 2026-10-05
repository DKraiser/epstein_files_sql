"""Configuration for the importer; existing shared constants stay unchanged."""

from .main_constants import PROJECT_ROOT

# Each invocation rebuilds only these task tables in this working schema.
IMPORT_SCHEMA = "z1_import"
BATCH_SIZE = 5_000
SCHEMA_FILE = PROJECT_ROOT / "src" / "sql" / "schema.sql"
SEED_FILE = PROJECT_ROOT / "src" / "sql" / "seed.sql"

# Logs stay inside the directory the importer is allowed to write.
LOG_DIRECTORY = PROJECT_ROOT / "logs"
