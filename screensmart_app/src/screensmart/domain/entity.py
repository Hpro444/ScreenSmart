"""Sanctions-list entity models — what the index stores and the screener scores against."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from .enums import EntitySchema


class SanctionedEntity(BaseModel):
    """One entity on the consolidated list, with all searchable name variants."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    schema_: EntitySchema = Field(alias="schema")
    name: str
    aliases: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)
    first_seen: Optional[str] = None

    @property
    def all_names(self) -> list[str]:
        """Primary name followed by all aliases, in list order."""
        return [self.name, *self.aliases]


class NameVariant(BaseModel):
    """A single searchable name (primary or alias) flattened from an entity."""
    model_config = ConfigDict(frozen=True)

    entity_id: str
    schema_: EntitySchema = Field(alias="schema")
    variant_norm: str
    variant_raw: str
    is_primary: bool
