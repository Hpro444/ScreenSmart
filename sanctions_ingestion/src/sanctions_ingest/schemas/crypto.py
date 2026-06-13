"""Pydantic schema for sanctioned crypto wallet records."""
from __future__ import annotations

from .base import IngestSchema


class CryptoWalletIn(IngestSchema):
    address: str
    currency: str | None = None
    source: str
    entity_ref: str | None = None
    entity_name: str | None = None
