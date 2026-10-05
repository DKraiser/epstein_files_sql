"""Source-located diagnostics and complete rejected/duplicate source records."""

from datetime import date, datetime, time, timezone
from decimal import Decimal
import json
import logging
import math

from psycopg.types.json import Jsonb

from .parsing import json_value


def serializable(value):
    if isinstance(value, Jsonb):
        return serializable(json_value(value.obj))
    if isinstance(value, dict):
        return {key: serializable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serializable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_float": repr(value)}
    if isinstance(value, (Decimal, date, time)):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


class Journal:
    """One small JSONL journal per local import run, separate from provenance."""

    def __init__(self, directory):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{stamp}.jsonl"
        self.stream = self.path.open("w", encoding="utf-8")
        self.write(kind="run", status="started", started_at=datetime.now(timezone.utc))

    def write(self, **record):
        # ASCII escaping retains original NUL/surrogates in rejected strings.
        self.stream.write(json.dumps(serializable(record), ensure_ascii=True, allow_nan=False) + "\n")

    def for_row(self, location):
        def log(kind, column, message, raw=None, parsed=None, status=None):
            record = {key: value for key, value in location.items() if key != "record"}
            record.update(kind=kind, column=column, message=message)

            if kind in ("quarantine", "duplicate"):
                record["source_record"] = location["record"]
            else:
                name = column or "value"
                record.update({name + "_raw": raw, name + "_parsed": parsed, name + "_status": status})

            self.write(**record)
            
            if kind != "conversion":
                logging.warning("%s %s:%s %s: %s", kind, location["source_file"],
                                location["source_row"], column or "row", message)
                
        return log

    def close(self):
        self.stream.close()
