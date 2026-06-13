"""Pydantic schema for OpenSanctions targets.simple records."""
from __future__ import annotations

from pydantic import Field

from .base import IngestSchema


class OpenSanctionsTargetIn(IngestSchema):
    dataset: str
    entity_id: str | None = None
    # `schema_` shadows Pydantic's BaseModel.schema; alias keeps the DB column "schema".
    schema_: str | None = Field(default=None, alias="schema")
    name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    birth_date: str | None = None
    countries: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    identifiers: list[str] = Field(default_factory=list)
    sanctions: list[str] = Field(default_factory=list)
    first_seen: str | None = None
    last_seen: str | None = None
