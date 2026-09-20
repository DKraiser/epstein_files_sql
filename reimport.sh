#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck disable=SC1091
source "$PROJECT_ROOT/src/.venv/bin/activate"
set -a
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.env"
set +a

: "${POSTGRES_USER:?POSTGRES_USER must be set in .env}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in .env}"
: "${POSTGRES_DBNAME:?POSTGRES_DBNAME must be set in .env}"

export PGPASSWORD="$POSTGRES_PASSWORD"

docker exec postgres-dbs2 \
    psql --host localhost --port 5432 \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DBNAME" \
    --file "/src/sql/schema.sql"

docker exec postgres-dbs2 \
    psql --host localhost --port 5432 \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DBNAME" \
    --file "/src/sql/seed.sql"

"$PROJECT_ROOT/src/.venv/bin/python" "$PROJECT_ROOT/src/python/import.py"
