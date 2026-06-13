"""Structured (JSON-lines) logging.

Every log record is one JSON object written to `screensmart_app/logs/screensmart.jsonl`
(rotating), so logs are machine-parseable — useful here as the screening **audit
trail** (one structured event per verdict, defensible to a regulator). Call
`log_event("screen", txn_id=..., verdict=..., ...)` to emit a typed event.
"""
from __future__ import annotations
import datetime as dt
import json
import logging
from logging.handlers import RotatingFileHandler

from .config import settings

_CONFIGURED = False
_LOGGER_NAME = "screensmart"


class JsonLineFormatter(logging.Formatter):
    """Render each record as a single JSON object with any structured fields merged in."""

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
    """Idempotently attach a rotating JSON file handler under settings.logs_dir."""
    global _CONFIGURED
    logger = logging.getLogger(_LOGGER_NAME)
    if _CONFIGURED:
        return logger
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        settings.logs_dir / "screensmart.jsonl",
        maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(JsonLineFormatter())
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger() -> logging.Logger:
    return configure()


def log_event(event: str, **fields) -> None:
    """Emit one structured log event: `log_event("screen", verdict="MATCH", ...)`."""
    get_logger().info(event, extra={"fields": fields})
