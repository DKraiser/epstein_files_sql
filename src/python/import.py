"""Import the first 1,000 documents and normalise their lookup values."""

import json
import os
from pathlib import Path
from typing import Any

import polars as pl
from dotenv import load_dotenv
from psycopg import connect
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

import defines

BASE_PATH = defines.PROJECT_ROOT / "data"
DOCUMENTS_PATHS = [BASE_PATH / path for path in defines.DEFAULT_FILES_PATHS[0]]
CHUNKS_PATHS = [BASE_PATH / path for path in defines.DEFAULT_FILES_PATHS[1]]

def create_conninfo() -> str:
    """Return PostgreSQL connection information from the project .env file."""
    load_dotenv(defines.PROJECT_ENV)
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD must be set in .env")

    return make_conninfo(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DBNAME", os.getenv("POSTGRES_DB", "dbs2")),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=password,
    )


def as_json(value: str | None) -> Jsonb | None:
    """Convert JSON text from Parquet to a Psycopg JSONB parameter."""
    if value is None:
        return None
    return Jsonb(json.loads(value))


def insert_document_types(cursor, values: list[str]) -> dict[str, int]:
    """Insert known document types and return their name-to-ID mapping."""
    cursor.executemany(
        "INSERT INTO document_types (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
        [(value,) for value in values],
    )
    cursor.execute("SELECT name, id FROM document_types")
    return {name: identifier for name, identifier in cursor.fetchall()}


def fetch_lookup_ids(cursor, table_name: str) -> dict[str, int]:
    """Fetch a name-to-ID mapping from an already seeded lookup table."""
    cursor.execute(f"SELECT name, id FROM {table_name}")
    return {name: identifier for name, identifier in cursor.fetchall()}


def foreign_key(lookup: dict[str, int], value: str | None, column_name: str) -> int | None:
    """Return a lookup ID or clearly report an unseeded source value."""
    if value is None:
        return None
    try:
        return lookup[value]
    except KeyError as error:
        raise ValueError(
            f"No {column_name} lookup value exists for {value!r}. "
            "Seed the lookup table before importing."
        ) from error

def import_documents(conninfo: str, documents: pl.DataFrame, document_types: list[Any]) -> None: 
    with connect(conninfo) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                dataset_ids = fetch_lookup_ids(cursor, "datasets")
                ocr_source_ids = fetch_lookup_ids(cursor, "ocr_sources")
                document_type_ids = insert_document_types(cursor, document_types)

                rows = [
                    (
                        document["id"],
                        document["file_key"],
                        foreign_key(dataset_ids, document["dataset"], "dataset"),
                        document["full_text"],
                        foreign_key(
                            document_type_ids, document["document_type"], "document type"
                        ),
                        document["date"],
                        document["is_photo"],
                        document["has_handwriting"],
                        document["has_stamps"],
                        foreign_key(ocr_source_ids, document["ocr_source"], "OCR source"),
                        document["additional_notes"],
                        document["page_number"],
                        document["document_number"],
                        document["char_count"],
                        document["created_at"],
                        as_json(document["email_fields"]),
                    )
                    for document in documents.iter_rows(named=True)
                ]
                cursor.executemany(
                    """
                    INSERT INTO documents (
                        id, file_key, dataset, full_text, document_type, date,
                        is_photo, has_handwriting, has_stamps, ocr_source,
                        additional_notes, page_number, document_number, char_count,
                        created_at, email_fields
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    rows,
                )
    
    print(f"Imported {len(rows)} documents")


def import_chunks(conninfo: str, chunks: pl.DataFrame) -> None: 
    with connect(conninfo) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                rows = [
                    (
                        chunk["id"],
                        chunk["document_id"],
                        chunk["chunk_index"],
                        chunk["content"],
                        chunk["token_count"],
                        chunk["char_start"],
                        chunk["char_end"]
                    )
                    for chunk in chunks.iter_rows(named=True)
                ]
                cursor.executemany(
                    """
                    INSERT INTO chunks (
                        id, document_id, chunk_index, content, token_count,
                        char_start, char_end
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    rows
                )
    
    print(f"Imported {len(rows)} chunks")

    

def main() -> None:
    documents = (
        pl.read_parquet(DOCUMENTS_PATHS)
        .sort("id")
        .head(1_000)
        .with_columns(pl.col("ocr_source").fill_null("gemini"))
    )

    document_types = sorted(
        pl.scan_parquet(DOCUMENTS_PATHS)
        .select("document_type")
        .collect()["document_type"]
        .drop_nulls()
        .unique()
        .to_list()
    )

    chunks = (
        pl.read_parquet(CHUNKS_PATHS)
        .join(
            documents.select("id"),
            left_on="document_id",
            right_on="id",
            how="semi",
        )
    )

    conninfo = create_conninfo()
    try: 
        import_documents(conninfo, documents, document_types)
    except Exception as e: 
        print ("Importing documents failed")
        print (e)

    try:
        import_chunks(conninfo, chunks)
    except Exception as e: 
        print ("Importing chunks failed")
        print (e)



if __name__ == "__main__":
    main()
