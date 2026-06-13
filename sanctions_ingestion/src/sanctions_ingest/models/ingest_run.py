"""Audit table: one row per (source, run) recording how the ingest went."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class IngestRun(Base):
    """Provenance / audit record for a single source ingest.

    Subclasses :class:`Base` (not ``BaseModel``) — it is the target of every other
    table's ``ingest_run_id`` foreign key and carries no ``raw`` payload itself.
    """

    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")  # running|ok|fail
    rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
