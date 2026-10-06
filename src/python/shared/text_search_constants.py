"""Shared rules for the importer's PostgreSQL full-text search columns."""

# Qualify the configuration so imports do not depend on a session's default.
# Queries over these vectors should use this same English configuration.
TEXT_SEARCH_CONFIG = "pg_catalog.english"

# table: (original text column, derived tsvector column)
SEARCH_VECTOR_COLUMNS = {
    "documents": ("full_text", "full_text_searchvec"),
    "chunks": ("content", "content_searchvec"),
}

# Apply to documents.full_text only. Exactly 1 MiB still goes through conversion.
FULL_TEXT_SEARCH_MAX_BYTES = 1024 * 1024 - 1
