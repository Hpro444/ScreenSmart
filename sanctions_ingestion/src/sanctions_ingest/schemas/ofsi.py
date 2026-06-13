"""Pydantic schema for UK OFSI consolidated-list records."""
from __future__ import annotations

from .base import IngestSchema


class OfsiEntryIn(IngestSchema):
    group_id: str | None = None
    name: str | None = None
    name_type: str | None = None
    entity_type: str | None = None
    regime: str | None = None
    country: str | None = None
    listed_on: str | None = None
