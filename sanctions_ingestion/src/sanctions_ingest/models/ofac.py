"""OFAC flat-file (SDN / CONSOLIDATED / ALT / ADD) and enhanced-XML tables."""
from __future__ import annotations

from sqlalchemy import ARRAY, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import BaseModel


class OfacEntity(BaseModel):
    """Primary records from SDN.CSV and CONSOLIDATED.CSV (same column layout)."""

    __tablename__ = "ofac_entity"

    list_source: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # sdn|consolidated
    ent_num: Mapped[int | None] = mapped_column(Integer, index=True)
    name: Mapped[str | None] = mapped_column(Text)
    sdn_type: Mapped[str | None] = mapped_column(Text)   # Individual|Entity|Vessel|Aircraft
    program: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)


class OfacAlias(BaseModel):
    """Alternate names (a.k.a.) from ALT.CSV."""

    __tablename__ = "ofac_alias"

    ent_num: Mapped[int | None] = mapped_column(Integer, index=True)
    alt_num: Mapped[int | None] = mapped_column(Integer)
    alt_type: Mapped[str | None] = mapped_column(Text)
    alt_name: Mapped[str | None] = mapped_column(Text)
    alt_remarks: Mapped[str | None] = mapped_column(Text)


class OfacAddress(BaseModel):
    """Addresses from ADD.CSV."""

    __tablename__ = "ofac_address"

    ent_num: Mapped[int | None] = mapped_column(Integer, index=True)
    add_num: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str | None] = mapped_column(Text)
    city_state_zip: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    add_remarks: Mapped[str | None] = mapped_column(Text)


class OfacEnhancedEntry(BaseModel):
    """Entities from SDN_ENHANCED.XML (the source of crypto wallet 'features')."""

    __tablename__ = "ofac_enhanced_entry"

    uid: Mapped[str | None] = mapped_column(Text, index=True)
    name: Mapped[str | None] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(Text)
    programs: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
