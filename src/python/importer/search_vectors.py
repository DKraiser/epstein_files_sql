"""SQL conversion rules shared by vector loading and verification."""

from psycopg import sql

from ..shared.text_search_constants import SEARCH_VECTOR_COLUMNS, TEXT_SEARCH_CONFIG, FULL_TEXT_SEARCH_MAX_BYTES


def vector_expression(table):
    """Return a SQL expression and its bound parameters for this table's vector.

    Measure stored text in bytes, rather than characters or compressed storage.
    CASE avoids invoking to_tsvector for oversized documents: they retain their
    full text and receive an empty vector, not SQL NULL. Exactly 1 MiB is allowed.
    NULL/empty text and chunk conversion retain their existing behavior.
    """
    text_column, _ = SEARCH_VECTOR_COLUMNS[table]
    text = sql.Identifier(text_column)
    conversion = sql.SQL("pg_catalog.to_tsvector(%s::pg_catalog.regconfig, {})").format(text)
    if table == "documents":
        expression = sql.SQL("CASE WHEN pg_catalog.octet_length({}) > %s "
                             "THEN ''::pg_catalog.tsvector ELSE {} END").format(text, conversion)
        return expression, (FULL_TEXT_SEARCH_MAX_BYTES, TEXT_SEARCH_CONFIG)
    return conversion, (TEXT_SEARCH_CONFIG,)
