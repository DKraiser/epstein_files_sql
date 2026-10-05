"""One explicit transformation function for each source layer.

Each function returns target columns and optional model links. SQL insertion,
transactions and source-row accounting belong to loading.py.

Arguments shared by every layer function:
    source: one original Parquet row, represented as a dictionary.
    lookups: enum table -> {source label: database enum ID}.
    parents: previously committed document/entity/event/run keys.
    log: callback that already knows this row's source file and position.

The return value is (row, model_links). row uses SQL column names; model_links
contains (parent ID, model ID) pairs for provenance bridge tables. Each function
copies source before changing columns, leaving the original available for logs.
"""

from .literals import ParseStatus, MatchStatus, RunStatus, FileStatus, CuratedStatus, CuratedTier, Model
from .parsing import (parse_json, parse_date, parse_hash, parse_models, missing, amount,
                      capitalize_document_type, ocr_source)


class Rejected(ValueError):
    """A required source relationship/value cannot be stored safely."""


def parsed(row, field, value, status, log):
    """Replace a source field with its raw/parsed/status SQL columns.

    For example, source date='04/05/00' becomes date_raw='04/05/00',
    date_parsed=date(2000, 4, 5), and date_status=ParseStatus.SUCCESS.id.
    """
    raw = row.pop(field)
    row[field + "_raw"] = raw
    row[field + "_parsed"] = value
    row[field + "_status"] = status.id
    
    if status in (ParseStatus.FAILED, ParseStatus.PARTIAL):
        log("parse", field, status.value, raw, value, status.value)


def date_field(row, field, log, kind="date", keep_local=False):
    """Parse for DATE, TIMESTAMP, or TIMESTAMPTZ and preserve the notation.

    keep_local is used only where the schema has an extra column for a local
    timestamp that cannot safely be represented as a timezone-aware instant.
    """
    value, status, local = parse_date(row[field], kind)
    parsed(row, field, value, status, log)
    if keep_local:
        row[field + "_local_parsed"] = local


def json_field(row, field, log, shape=None):
    """Preserve JSON text and store validated JSONB, optionally requiring a shape."""
    value, status = parse_json(row[field], shape)
    parsed(row, field, value, status, log)


def category(row, field, target, table, lookups, log, convert=None):
    """Replace a category label with the ID collected in the lookup stage.

    field is the source column; target is its SQL foreign-key column. convert
    applies the same label rule as lookup collection, including the OCR default.
    """
    raw = row.pop(field)
    label = convert(raw) if convert else raw

    if convert:
        # The fixed DDL has no raw/parsed/status columns for these category
        # conversions. Preserve those triples in the source-located JSONL log.
        # A missing OCR value has a valid dataset-defined default. Its raw
        # value remains NULL in this journal entry, while the conversion succeeds.
        status = missing(raw) or ParseStatus.SUCCESS
        if raw is None and label is not None:
            status = ParseStatus.SUCCESS
        log("conversion", field, "Category normalization", raw, label, status.value)
    
    if label is None:
        row[target] = None
        return
    
    try:
        row[target] = lookups[table][label]
    except KeyError as error:
        raise Rejected(f"Unknown {field} label {raw!r}") from error


def fixed(row, field, target, enum):
    """Resolve a fixed literal through its enum ID, verified against seed.sql.

    Unlike collected categories, fixed enums have a predefined set of labels.
    An unknown label rejects the row rather than inventing a new status/tier.
    """
    raw = row.pop(field)
    try:
        row[target] = enum(raw).id
    except ValueError as error:
        raise Rejected(f"Unknown {field} label {raw!r}") from error


def reference(parents, table, raw, field, log, required=False):
    """Resolve an exact parent key without a SQL query for each source row.

    Missing optional parents return None; required ones raise Rejected, which
    loading.py catches and records as a quarantined original source row.
    """
    value = parents[table].get(raw)
    if value is None:
        log("match", field, f"No exact {table} match", raw)
        if required:
            raise Rejected(f"Required {field} reference {raw!r} does not resolve")
    return value


def document_key(row, parents, log, required=False):
    """Use the original file_key to add a document FK and optional match status."""
    value = reference(parents, "file_keys", row["file_key"], "file_key", log, required)
    row["document_id"] = value
    if not required:
        row["document_match_status"] = (MatchStatus.MATCHED if value is not None else MatchStatus.UNRESOLVED).id


def models(row, field, parent, log):
    """Keep the original CSV and return distinct model links for the same row.

    The parsed representation is the bridge table, rather than a parsed column.
    Known tokens can still link when other tokens fail; raw retains all tokens.
    """
    raw = row.pop(field)
    values, status, unknown = parse_models(raw)
    row[field + "_raw"] = raw
    row[field + "_status"] = status.id
    if unknown:
        log("parse", field, f"Unknown model tokens: {unknown!r}", raw,
            [value.value for value in values], status.value)
    return [(parent, value.id) for value in sorted(set(values), key=lambda value: value.id)]


def documents(source, lookups, parents, log):
    """Prepare independent document rows before any layer can reference them."""
    row = dict(source)
    category(row, "dataset", "dataset", "enum_datasets", lookups, log)
    category(row, "document_type", "document_type", "enum_document_types", lookups, log, capitalize_document_type)
    category(row, "ocr_source", "ocr_source", "enum_ocr_sources", lookups, log, ocr_source)
    date_field(row, "date", log)
    date_field(row, "created_at", log, "timestamp")
    json_field(row, "email_fields", log)
    return row, []


def persons(source, lookups, parents, log):
    """Resolve the person category and parse its three JSON list fields."""
    row = dict(source)
    category(row, "category", "category_id", "enum_person_categories", lookups, log)
    for field in ("aliases", "search_terms", "sources"):
        json_field(row, field, log, list)
    return row, []


def kg_entities(source, lookups, parents, log):
    """Prepare knowledge-graph nodes and parse their metadata object."""
    row = dict(source)
    category(row, "entity_type", "entity_type_id", "enum_kg_entity_types", lookups, log)
    json_field(row, "metadata", log, dict)
    return row, []


def derived_events(source, lookups, parents, log):
    """Resolve event categories and parse dates without changing other event text."""
    row = dict(source)
    for field, target, table in (("event_type", "event_type_id", "enum_event_types"),
                                 ("track", "track_id", "enum_event_tracks"),
                                 ("confidence", "confidence_id", "enum_event_confidences")):
        category(row, field, target, table, lookups, log)
    for field in ("event_date", "event_end_date"):
        date_field(row, field, log)
    row["amount"] = amount(row["amount"])
    row["time_of_day_raw"] = row.pop("time_of_day")  # fixed DDL keeps notation only
    return row, []


def provenance_runs(source, lookups, parents, log):
    """Prepare upstream runs and the model links written in their transaction."""
    row = dict(source)
    fixed(row, "status", "run_status", RunStatus)
    for field in ("started_at", "last_heartbeat"):
        date_field(row, field, log, "timestamptz")
    date_field(row, "completed_at", log, "timestamptz", keep_local=True)
    row["cost_usd"] = amount(row["cost_usd"])
    links = models(row, "model", row["run_id"], log)
    return row, links


def chunks(source, lookups, parents, log):
    """Preserve chunk columns; quarantine chunks whose document was not accepted."""
    row = dict(source)
    row["document_id"] = reference(parents, "documents", row["document_id"], "document_id", log, True)
    return row, []


def entities(source, lookups, parents, log):
    """Keep extracted mentions even when their optional document cannot resolve."""
    row = dict(source)
    category(row, "entity_type", "entity_type_id", "enum_entity_types", lookups, log)
    row["document_id_raw"] = row["document_id"]
    row["document_id"] = reference(parents, "documents", row["document_id_raw"], "document_id", log)
    row["document_match_status"] = (MatchStatus.MATCHED if row["document_id"] is not None else MatchStatus.UNRESOLVED).id
    row["value_raw"] = row.pop("value")
    row["normalized_value_raw"] = row.pop("normalized_value")
    # This source field is retained but no new normalization is performed.
    row["normalized_value_parsed"] = None
    row["normalization_rule"] = None
    return row, []


def kg_relationships(source, lookups, parents, log):
    """Require both KG nodes to exist, then resolve type and parse edge metadata."""
    row = dict(source)
    category(row, "relationship_type", "relationship_type_id", "enum_relationship_types", lookups, log)
    for field in ("source_id", "target_id"):
        row[field] = reference(parents, "kg_entities", row[field], field, log, True)
    json_field(row, "metadata", log, dict)
    return row, []


def event_participants(source, lookups, parents, log):
    """Require an accepted event and resolve the participant role.

    person_name remains source text: a name alone is not a persons.id match.
    """
    row = dict(source)
    category(row, "role", "role_id", "enum_participant_roles", lookups, log)
    row["event_id"] = reference(parents, "derived_events", row["event_id"], "event_id", log, True)
    return row, []


def event_sources(source, lookups, parents, log):
    """Require the event; keep evidence file keys even if their document is absent."""
    row = dict(source)
    row["event_id"] = reference(parents, "derived_events", row["event_id"], "event_id", log, True)
    document_key(row, parents, log)
    return row, []


def financial_transactions(source, lookups, parents, log):
    """Require the source document and parse dates, amount, and extraction model."""
    row = dict(source)
    category(row, "dataset", "dataset_id", "enum_datasets", lookups, log)
    document_key(row, parents, log, required=True)
    for field in ("transaction_date", "statement_date", "flight_departure"):
        date_field(row, field, log)
    row["amount"] = amount(row["amount"])
    raw = row.pop("extraction_model")
    status = missing(raw)
    try:
        model_id = Model(raw).id if status is None else None
        status = status or ParseStatus.SUCCESS
    except ValueError:
        model_id, status = None, ParseStatus.FAILED
        log("parse", "extraction_model", "Unknown model", raw, None, status.value)
    row["extraction_model_raw"] = raw
    row["extraction_model_id"] = model_id
    row["extraction_model_status"] = status.id
    return row, []


def curated_docs(source, lookups, parents, log):
    """Resolve curated enums/document, then parse its date and appearance list."""
    row = dict(source)
    category(row, "subject", "subject_id", "enum_curated_subjects", lookups, log)
    fixed(row, "status", "curated_status", CuratedStatus)
    raw_tier = row["tier"]
    row["tier"] = raw_tier.lower() if raw_tier is not None else None
    fixed(row, "tier", "tier_id", CuratedTier)
    log("conversion", "tier", "Match lowercase enum literal", raw_tier,
        raw_tier.lower() if raw_tier is not None else None, (missing(raw_tier) or ParseStatus.SUCCESS).value)
    document_key(row, parents, log, required=True)
    date_field(row, "doc_date", log)
    json_field(row, "also_appears_as", log, list)
    return row, []


def provenance_files(source, lookups, parents, log):
    """Prepare file provenance, parsed hashes/timestamps, and model bridge pairs."""
    row = dict(source)
    # loading.py adds the stable source location and local surrogate ID.
    fixed(row, "status", "file_status", FileStatus)
    for field in ("pdf_sha256", "output_sha256"):
        value, status = parse_hash(row[field])
        parsed(row, field, value, status, log)
    for field in ("first_seen_at", "processed_at"):
        date_field(row, field, log, "timestamptz")
    if row["run_id"] is not None:
        row["run_id"] = reference(parents, "provenance_runs", row["run_id"], "run_id", log, True)
    document_key(row, parents, log)
    links = models(row, "model_used", row["id"], log)
    return row, links


# The first five layers reference only lookup tables. Model links are written
# in their parent's transaction; all remaining layers follow committed parents.
LAYERS = (
    ("documents", documents), ("persons", persons), ("kg_entities", kg_entities),
    ("derived_events", derived_events), ("provenance/runs", provenance_runs),
    ("chunks", chunks), ("entities", entities), ("kg_relationships", kg_relationships),
    ("event_participants", event_participants), ("event_sources", event_sources),
    ("financial_transactions", financial_transactions), ("curated_docs", curated_docs),
    ("provenance/files", provenance_files),
)
