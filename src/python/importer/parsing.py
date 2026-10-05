"""Convert individual values; layer functions preserve their raw notation."""

from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
import re

from psycopg.types.json import Jsonb

from . import dates
from .literals import Model, ParseStatus


def capitalize_document_type(value):
    """Use the same document-type label during lookup collection and matching."""
    return value.capitalize() if value is not None else None


def ocr_source(value):
    """In this dataset, missing OCR attribution means Flash Lite was used.

    Return a label, not Model.id: enum_ocr_sources has its own database IDs.
    Explicit values, including empty strings, remain unchanged.
    """
    return Model.GEMINI_2_5_FLASH_LITE.value if value is None else value


def missing(value):
    if value is None:
        return ParseStatus.NULL
    if value == "":
        return ParseStatus.EMPTY
    return None


def json_value(raw):
    """Read standard JSON without losing decimal digits or accepting NaN."""
    def invalid_constant(value):
        raise ValueError(f"Invalid JSON constant {value}")
    return json.loads(raw, parse_float=Decimal, parse_constant=invalid_constant)


def check_json_strings(value):
    # PostgreSQL JSONB rejects these even though JSON text can express them.
    if isinstance(value, str):
        if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("JSON string is not representable in PostgreSQL")
    elif isinstance(value, list):
        for item in value:
            check_json_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            check_json_strings(key)
            check_json_strings(item)


def parse_json(raw, shape=None):
    status = missing(raw)
    if status is not None:
        return None, status
    try:
        value = json_value(raw)
        if shape is not None and not isinstance(value, shape):
            raise ValueError("Unexpected JSON shape")
        check_json_strings(value)
    except (ValueError, TypeError, RecursionError):
        return None, ParseStatus.FAILED
    # Send validated original JSON text so its numeric precision is unchanged.
    return Jsonb(raw, dumps=lambda value: value), ParseStatus.SUCCESS


@lru_cache(maxsize=16_384)
def parse_date(raw, kind="date"):
    value, status = dates.parse(raw)
    if value is None:
        return None, status, None
    if kind == "date":
        return value.date(), status, None
    if not re.search(r"\d{1,2}:\d{2}|\d{8}T\d{6}", raw):
        return None, ParseStatus.PARTIAL, None
    if kind == "timestamp":
        return (value, status, None) if value.tzinfo is None else (None, ParseStatus.PARTIAL, None)
    if value.tzinfo is None:
        # Keep available local wall-clock time separately; never assign a zone.
        return None, ParseStatus.PARTIAL, value
    return value, status, None


def parse_hash(raw):
    status = missing(raw)
    if status is not None:
        return None, status
    if not re.fullmatch(r"[0-9a-fA-F]{64}", raw):
        return None, ParseStatus.FAILED
    return bytes.fromhex(raw), ParseStatus.SUCCESS


def parse_models(raw):
    status = missing(raw)
    if status is not None:
        return [], status, []
    known, unknown = [], []
    for token in raw.split(","):
        token = token.strip()
        try:
            known.append(Model(token))
        except ValueError:
            unknown.append(token)
    status = ParseStatus.SUCCESS if not unknown else (ParseStatus.PARTIAL if known else ParseStatus.FAILED)
    return known, status, unknown


def amount(value):
    """Source amounts are already numeric; retain their available digits/sign."""
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("Amount is not finite")
        return result
    except InvalidOperation as error:
        raise ValueError("Invalid amount") from error
