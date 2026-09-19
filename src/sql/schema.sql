-- Drop dependent tables before the tables they reference.
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS document_types;
DROP TABLE IF EXISTS datasets;
DROP TABLE IF EXISTS ocr_sources;

CREATE TABLE document_types (
    id SMALLSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE datasets(
    id SMALLSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE ocr_sources(
    id SMALLSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE documents(
    id BIGSERIAL PRIMARY KEY,
    file_key TEXT,
    dataset SMALLINT REFERENCES datasets(id) ON DELETE RESTRICT,
    full_text TEXT,
    document_type SMALLINT REFERENCES document_types(id) ON DELETE RESTRICT,
    date DATE,
    is_photo BOOLEAN,
    has_handwriting BOOLEAN,
    has_stamps BOOLEAN,
    ocr_source SMALLINT REFERENCES ocr_sources(id) ON DELETE RESTRICT,
    additional_notes TEXT,
    page_number TEXT,
    document_number TEXT,
    char_count INTEGER,
    created_at TIMESTAMP,
    email_fields JSONB
);

CREATE TABLE chunks(
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    content TEXT,
    token_count INTEGER,
    char_start INTEGER,
    char_end INTEGER,

    UNIQUE (document_id, chunk_index)
);
