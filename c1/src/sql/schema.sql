-- Drop dependent tables before the tables they reference.
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS documents_types;
DROP TABLE IF EXISTS ocr_sources;
DROP TABLE IF EXISTS datasets;

CREATE TABLE datasets(
    id SMALLSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE document_types(
    id SMALLSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE ocr_sources(
    id SMALLSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE documents(
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP,
    char_count INTEGER,
    dataset SMALLINT REFERENCES datasets(id) ON DELETE RESTRICT,
    ocr_source SMALLINT REFERENCES ocr_sources(id) ON DELETE RESTRICT,
    is_photo BOOLEAN,
    has_stamps BOOLEAN,
    has_handwriting BOOLEAN,
    document_type TEXT,
    file_key TEXT,
    full_text TEXT,
    date TEXT,
    additional_notes TEXT,
    page_number TEXT,
    document_number TEXT,
    email_fields JSONB
);

CREATE TABLE chunks(
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    token_count INTEGER,
    char_start INTEGER,
    char_end INTEGER,
    content TEXT,

    UNIQUE (document_id, chunk_index)
);
