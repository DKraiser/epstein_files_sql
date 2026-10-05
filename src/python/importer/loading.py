"""Stream one source layer into one transaction, keeping every row accounted.

load_layer() reads Parquet batches and calls the layer's transformation function.
write_batch() tries fast COPY, falling back to individual inserts if a row is bad.
The batch savepoints can roll back independently, but only load_layer() commits:
an interruption or failed verification therefore undoes the entire active layer.
"""

from dataclasses import dataclass, asdict
import logging

import polars as pl
import psycopg
from psycopg import sql

from ..shared.importer_constants import BATCH_SIZE
from .layers import Rejected
from .verification import BRIDGES, identical, verify_batch, verify_counts


@dataclass
class Counts:
    """Count source rows, not model links; every read row needs one outcome."""
    n_read: int = 0
    n_accepted: int = 0
    n_quarantined: int = 0
    n_duplicate: int = 0

    def check(self):
        if self.n_read != self.n_accepted + self.n_quarantined + self.n_duplicate:
            raise ValueError(f"Source accounting does not balance: {asdict(self)}")


@dataclass
class PreparedRow:
    """Keep SQL values, model-link pairs, and the original row together.

    values has already been transformed to SQL column names/types. location
    includes the untouched source record so rejection never loses its contents.
    """
    values: dict
    models: list
    location: dict


def copy_rows(connection, table, columns, rows):
    """Send already prepared rows through PostgreSQL's bulk COPY protocol.

    Identifiers safely quote table/column names. psycopg handles value encoding,
    including SQL NULL for None; we do not construct CSV or interpolate values.
    """
    query = sql.SQL("COPY {} ({}) FROM STDIN").format(sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns)))
    with connection.cursor() as cursor, cursor.copy(query) as copy:
        for row in rows:
            copy.write_row(row)


def write_models(connection, table, entries):
    """Write a provenance row's model pairs under its parent's savepoint.

    Other layers have no bridge table. A link failure also undoes its parent
    insert, preventing an accepted provenance row with only some of its links.
    """
    if table in BRIDGES:
        bridge, parent = BRIDGES[table]
        rows = [link for entry in entries for link in entry.models]
        if rows:
            copy_rows(connection, bridge, [parent, "model_id"], rows)


def write_batch(connection, table, entries, counts, journal):
    """Insert a batch, classify rejected/duplicate rows, and verify accepted ones.

    Return the accepted entries and number of model links they produced. These
    writes remain uncommitted until the surrounding layer transaction finishes.
    """

    if not entries:
        # A whole source batch may already have been rejected by transformation.
        return [], 0
    
    # Every transformed row of a layer uses the same SQL columns. Use that
    # column order for both COPY and its fallback INSERT parameter tuples.
    columns = list(entries[0].values)
    duplicates = []
    try:
        # Nested transactions are savepoints; the layer remains the unit of commit.
        with connection.transaction():
            copy_rows(connection, table, columns, [tuple(entry.values[name] for name in columns) for entry in entries])
            write_models(connection, table, entries)

        accepted = entries

    except (psycopg.IntegrityError, psycopg.DataError):
        # The failed COPY savepoint has undone ALL batch rows and model links.
        # Retry one row at a time to identify bad data while retaining good rows.
        # Unexpected SQL/programming errors are not swallowed by this fallback.
        accepted = []
        insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(sql.Identifier(table),
            sql.SQL(", ").join(map(sql.Identifier, columns)), sql.SQL(", ").join(sql.Placeholder() for _ in columns))
        
        for entry in entries:
            log = journal.for_row(entry.location)
        
            try:
                # A failed single row must not leave the layer transaction in
                # PostgreSQL's aborted state, or block subsequent valid rows.
                with connection.transaction():
                    connection.execute(insert, tuple(entry.values[name] for name in columns))
        
                    write_models(connection, table, [entry])
            except psycopg.errors.UniqueViolation as error:
                # An existing primary key is a duplicate only if ALL prepared
                # values match. A different row reusing a key is quarantined.
                if identical(connection, table, entry.values):
                    counts.n_duplicate += 1
                    duplicates.append(entry)
                    log("duplicate", None, "All normalized target values equal an already accepted row")
                else:
                    counts.n_quarantined += 1
                    log("quarantine", None, f"Conflicting unique key: {error.diag.constraint_name}")
        
            except (psycopg.IntegrityError, psycopg.DataError) as error:
                counts.n_quarantined += 1
                log("quarantine", None, str(error))
           
            else:
                accepted.append(entry)
    
    # Check both newly inserted and existing identical rows, including model
    # links. Matching parent columns alone cannot prove its bridge is complete.
    # This runs inside the layer transaction, so verification failure rolls it back.
    verify_batch(connection, table, accepted + duplicates)
    counts.n_accepted += len(accepted)
    return accepted, sum(len(entry.models) for entry in accepted)


def load_layer(connection, layer, transform, paths, lookups, parents, journal, source_root, batch_size=BATCH_SIZE):
    """Read every shard of one layer and commit only after all checks pass.

    transform is the matching function from layers.LAYERS. lookups maps enum
    labels to IDs; parents holds accepted keys from earlier committed layers.
    File counters reset per shard; total aggregates them for the layer report.
    """
    
    # Source paths use provenance/files; SQL uses the table provenance_files.
    table = layer.replace("/", "_")
    total, file_counts, model_count = Counts(), [], 0
    bridge = BRIDGES[table][0] if table in BRIDGES else None
    already_linked = 0
    ordinal = 0
    journal.write(kind="layer", layer=layer, status="started")

    try:
        # This is the outer transaction. Returning from nested batch savepoints
        # does not commit anything yet; any error here rolls back the whole layer.
        with connection.transaction():
            # Preserve the baseline from prior commits. Only accepted NEW rows
            # and links increase it; duplicates do not add to either table.
            already_stored = connection.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]
            if bridge is not None:
                already_linked = connection.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(bridge))).fetchone()[0]

            for path in paths:
                name = str(path.relative_to(source_root))
                # Compare streamed row counts against an independent Parquet
                # count, so missing rows cannot be hidden by balanced counters.
                expected = pl.scan_parquet(path).select(pl.len()).collect().item()
                counts = Counts()

                for frame in pl.scan_parquet(path).collect_batches(chunk_size=batch_size, maintain_order=True, engine="streaming", lazy=True):
                    # Keep source order stable for row locations and generated IDs.
                    entries = []

                    for original in frame.iter_rows(named=True):
                        # Capture the zero-based position BEFORE incrementing the
                        # count, and retain the untouched record for diagnostics.
                        location = {"layer": layer, "source_file": name, "source_row": counts.n_read,
                                    "source_id": original.get("id", original.get("run_id")), "record": original}
                        counts.n_read += 1
                        ordinal += 1
                        source = dict(original)

                        if layer == "provenance/files":
                            # This layer has no source ID. Its local ordinal spans
                            # all shards; the original source position is also stored.
                            source.update(id=ordinal, source_file=name, source_row=location["source_row"])
                        
                        log = journal.for_row(location)
                        
                        try:
                            row, models = transform(source, lookups, parents, log)
                        
                        except (Rejected, ValueError) as error:
                            # Required missing parents or invalid numeric values
                            # reject a row before SQL. Log it in full and count it.
                            counts.n_quarantined += 1
                            log("quarantine", None, str(error))
                            continue
                        
                        entries.append(PreparedRow(row, models, location))
                    
                    _, links = write_batch(connection, table, entries, counts, journal)
                    model_count += links
                    journal.stream.flush()
                    
                counts.check()
                
                if counts.n_read != expected:
                    raise ValueError(f"Source count mismatch for {name}: {counts.n_read} != {expected}")
                
                file_counts.append({"source_file": name, **asdict(counts)})
                
                for field, value in asdict(counts).items():
                    setattr(total, field, getattr(total, field) + value)
                
                logging.info("%s %s: %s", layer, name, asdict(counts))
            
            total.check()
            # A rerun can start with previously committed rows. Verify the total
            # against the baseline plus this run's newly accepted source rows.
            expected_rows = already_stored + total.n_accepted
            stored = connection.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]
            
            if stored != expected_rows:
                raise ValueError(f"{table} count is {stored}, expected {expected_rows} "
                                 f"({already_stored} existing + {total.n_accepted} accepted)")
            if bridge is not None:
                verify_counts(connection, {}, {bridge: already_linked + model_count})
            
            if table == "provenance_files" and total.n_accepted:
                # Explicit ordinal IDs bypass the identity sequence. Advance it
                # so a later default-ID insert cannot collide with imported IDs.
                connection.execute("SELECT setval(pg_get_serial_sequence('provenance_files','id'), (SELECT max(id) FROM provenance_files))")
            
    except BaseException:
        # Includes KeyboardInterrupt: the transaction has rolled back by the
        # time this marker is written. Earlier layer commits remain intact.
        journal.write(kind="layer", layer=layer, status="rolled_back")
        journal.stream.flush()
        raise
    
    # Only reaching here means the outer transaction committed successfully.
    # Earlier diagnostic entries describe attempted work, not a durable commit.
    # target_rows/model_links are expected TOTALS for main.py's final check.
    # Keep newly accepted rows and newly added links as separate run counters.
    report = {**asdict(total), "existing_rows": already_stored, "target_rows": expected_rows,
              "model_links_added": model_count, "model_links": already_linked + model_count,
              "files": file_counts}
    journal.write(kind="layer", layer=layer, status="committed", **report)
    journal.stream.flush()
    logging.info("Committed %s: %s", layer, asdict(total))
    return report
