"""Pydantic schemas for the OFAC flat-file and enhanced-XML records."""
from __future__ import annotations

from pydantic import Field

from .base import IngestSchema


class OfacEntityIn(IngestSchema):
    list_source: str
    ent_num: int | None = None
    name: str | None = None
    sdn_type: str | None = None
    program: str | None = None
    title: str | None = None
    remarks: str | None = None


class OfacAliasIn(IngestSchema):
    ent_num: int | None = None
    alt_num: int | None = None
    alt_type: str | None = None
    alt_name: str | None = None
    alt_remarks: str | None = None


class OfacAddressIn(IngestSchema):
    ent_num: int | None = None
    add_num: int | None = None
    address: str | None = None
    city_state_zip: str | None = None
    country: str | None = None
    add_remarks: str | None = None


class OfacEnhancedEntryIn(IngestSchema):
    uid: str | None = None
    name: str | None = None
    entity_type: str | None = None
    programs: list[str] = Field(default_factory=list)
