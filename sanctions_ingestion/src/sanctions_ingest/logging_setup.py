"""Structured (JSON-lines) logging for the ingestion service.

Mirrors ``screensmart_app/.../logging_setup.py``: every record is one JSON object
written to ``sanctions_ingestion/logs/ingest.jsonl`` (rotating) — the ingest audit
trail. A short human line also goes to stderr so CLI/scheduler runs are watchable.
Call ``log_event("ingest", source=..., rows=..., status=...)``.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import settings

_CONFIGURED = False
_LOGGER_NAME = "sanctions_ingest"


class JsonLineFormatter(logging.Formatter):
    """Render each record as a single JSON object with structured fields merged in."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": dt.datetime.fromtimestamp(record.created, dt.timezone.utc)
                    .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure() -> logging.Logger:
    """Idempotently attach a rotating JSON file handler + a stderr console handler."""
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    if _CONFIGURED:
        return logger
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        settings.logs_dir / "ingest.jsonl",
        maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(JsonLineFormatter())

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console)
    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger() -> logging.Logger:
    return configure()


def log_event(event: str, **fields) -> None:
    """Emit one structured log event: ``log_event("ingest", source="ofac_sdn", rows=12000)``."""
    get_logger().info(event, extra={"fields": fields})
