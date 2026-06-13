"""Pydantic schema for UN consolidated-list records."""
from __future__ import annotations

from pydantic import Field

from .base import IngestSchema


class UnEntityIn(IngestSchema):
    un_id: str | None = None
    record_type: str | None = None
    name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    un_list_type: str | None = None
    reference_number: str | None = None
    programs: list[str] = Field(default_factory=list)
    nationalities: list[str] = Field(default_factory=list)
    listed_on: str | None = None
    comments: str | None = None
