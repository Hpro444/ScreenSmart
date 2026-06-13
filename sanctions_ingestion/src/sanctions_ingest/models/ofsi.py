"""UK OFSI consolidated list (ConList.csv).

The OFSI CSV is wide and its columns shift between format revisions, so only the
stable, useful fields are typed here — the full row is always preserved in
``raw`` (inherited from ``BaseModel``).
"""
from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import BaseModel


class OfsiEntry(BaseModel):
    __tablename__ = "ofsi_entry"

    group_id: Mapped[str | None] = mapped_column(Text, index=True)  # links name rows for one person/entity
    name: Mapped[str | None] = mapped_column(Text)                  # full reconstructed name
    name_type: Mapped[str | None] = mapped_column(Text)            # Primary name|alias
    entity_type: Mapped[str | None] = mapped_column(Text)          # Individual|Entity|Ship
    regime: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    listed_on: Mapped[str | None] = mapped_column(Text)
