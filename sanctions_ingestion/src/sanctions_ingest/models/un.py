"""UN Security Council consolidated list (consolidated.xml)."""
from __future__ import annotations

from sqlalchemy import ARRAY, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import BaseModel


class UnEntity(BaseModel):
    """An individual or entity from the UN consolidated XML."""

    __tablename__ = "un_entity"

    un_id: Mapped[str | None] = mapped_column(Text, index=True)     # DATAID
    record_type: Mapped[str | None] = mapped_column(Text)           # individual|entity
    name: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    un_list_type: Mapped[str | None] = mapped_column(Text)
    reference_number: Mapped[str | None] = mapped_column(Text)
    programs: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    nationalities: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    listed_on: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
