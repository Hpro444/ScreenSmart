"""Base Pydantic schema shared by every parsed-record class.

Parsers return validated ``IngestSchema`` instances; the pipeline turns each into
a plain dict via :meth:`to_row` for fast bulk insert. Field names mirror the ORM
columns exactly, so the dict drops straight into ``BaseRepository.bulk_insert``.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IngestSchema(BaseModel):
    """A single parsed source record. Carries the verbatim upstream row in ``raw``."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, populate_by_name=True
    )

    raw: dict = Field(default_factory=dict)

    def to_row(self) -> dict:
        """Return a column-name-keyed dict ready for ``bulk_insert``.

        Serialised ``by_alias`` so fields that must shadow a Pydantic attribute
        (e.g. ``schema``) can use a safe Python name while still keying the dict
        by the real DB column name.
        """
        return self.model_dump(by_alias=True)
