"""The import pipeline: schema setup, lookups, parents, dependent layers."""

from datetime import datetime, timezone
import logging
import os

from dotenv import load_dotenv
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from ..shared import PROJECT_ENV, dataset_passport
from ..shared.importer_constants import IMPORT_SCHEMA, SCHEMA_FILE, SEED_FILE, LOG_DIRECTORY
from .journal import Journal
from .layers import LAYERS
from .loading import load_layer
from .lookups import populate_lookups, load_parents
from .verification import BRIDGES, verify_counts, verify_foreign_keys


def connection_info():
    load_dotenv(PROJECT_ENV)
    password = os.getenv("POSTGRES_PASSWORD")

    if not password:
        raise ValueError("POSTGRES_PASSWORD must be set in .env or the environment")
    
    return make_conninfo(host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DBNAME", os.getenv("POSTGRES_DB", "dbs2")),
        user=os.getenv("POSTGRES_USER", "postgres"), password=password, connect_timeout=5)


def rebuild(connection, schema=IMPORT_SCHEMA):
    """Execute the supplied SQL unchanged, inside only the working schema.

    The current schema uses IF NOT EXISTS and seed inserts ignore conflicts,
    so prior imported rows survive setup. The legacy function name does not
    mean that tables are cleared. Failed setup rolls back table/data changes.
    Existing SQL is never patched by this function.
    """
    with connection.transaction():
        connection.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        connection.execute(SCHEMA_FILE.read_text())
        connection.execute(SEED_FILE.read_text())


def import_dataset(connection, paths, source_root, journal):
    """Run after schema setup; also used with synthetic Parquet fixtures."""

    lookups = populate_lookups(connection, paths)
    parents, reports, counts, bridge_counts = {}, {}, {}, {}

    for layer, transform in LAYERS:
        # LAYERS orders independent parents before their dependent tables.
        # load_layer returns only after its rows and model links have committed.
        report = load_layer(connection, layer, transform, paths[layer], lookups, parents, journal, source_root)
        reports[layer] = report
        table = layer.replace("/", "_")
        # Reports include the baseline from previous commits plus new inserts.
        # Run counters such as n_accepted alone are not expected table totals.
        counts[table] = report["target_rows"]

        if table in BRIDGES:
            bridge_counts[BRIDGES[table][0]] = report["model_links"]

        # Publish newly accepted parent keys for the NEXT layer's transformations.
        # Layers that cannot be referenced by later layers add no dictionaries.
        load_parents(connection, table, parents)

    verify_counts(connection, counts, bridge_counts)
    foreign_keys = verify_foreign_keys(connection)
    return reports, foreign_keys


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    paths = dataset_passport.LOCAL_FILES_PATHS

    # Complete source coverage is checked before schema setup or loading.
    for layer, _ in LAYERS:
        for path in paths[layer]:
            if not path.is_file():
                raise FileNotFoundError(f"Missing source shard: {path}")
    journal = Journal(LOG_DIRECTORY)

    try:
        with psycopg.connect(connection_info(), autocommit=True) as connection:
            rebuild(connection)
            # Check schema constraints before spending time loading the corpus.
            verify_foreign_keys(connection)
            reports, foreign_keys = import_dataset(connection, paths, dataset_passport.PROJECT_DATASET_ROOT, journal)
        journal.write(kind="run", status="completed", finished_at=datetime.now(timezone.utc),
                      layers=reports, validated_foreign_keys=foreign_keys)
        logging.info("Import and verification completed; journal: %s", journal.path)

    except BaseException as error:
        journal.write(kind="run", status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                      error=str(error), finished_at=datetime.now(timezone.utc))
        logging.exception("Import stopped; rerun the same module to reuse committed rows and retry")
        raise

    finally:
        journal.close()
