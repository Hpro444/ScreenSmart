"""OpenSanctions ``targets.simple.csv`` feeds — one table, ``dataset`` discriminator.

The sanctions / default / peps / crypto feeds share an identical column set, so
they map to a single table keyed by ``dataset``; each feed is refreshed
independently via ``refresh(scope={"dataset": ...})``.
"""
from __future__ import annotations

from sqlalchemy import ARRAY, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import BaseModel


class OpenSanctionsTarget(BaseModel):
    __tablename__ = "opensanctions_target"

    dataset: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # sanctions|default|peps|crypto
    entity_id: Mapped[str | None] = mapped_column(Text, index=True)         # OpenSanctions "id"
    schema: Mapped[str | None] = mapped_column(Text)                        # Person|Organization|CryptoWallet|...
    name: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    birth_date: Mapped[str | None] = mapped_column(Text)
    countries: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    addresses: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    identifiers: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    sanctions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    first_seen: Mapped[str | None] = mapped_column(Text)
    last_seen: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_opensanctions_target_dataset_entity", "dataset", "entity_id"),
    )
