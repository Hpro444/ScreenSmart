"""Declarative base and the shared ``BaseModel`` mixin.

Every table inherits ``BaseModel``, so adding a table is just::

    class MySource(BaseModel):
        __tablename__ = "my_source"
        name: Mapped[str] = mapped_column(Text)

and the surrogate key, the schema-drift-proof ``raw`` JSONB, the audit link to
``ingest_run`` and the timestamps come for free.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root declarative base — owns the shared ``MetaData`` (``Base.metadata``)."""


class BaseModel(Base):
    """Abstract mixin every concrete table extends.

    - ``id`` — surrogate autoincrement primary key.
    - ``raw`` — the verbatim upstream record as JSONB; guarantees we keep *every*
      field a feed publishes even when we only model a subset as typed columns.
    - ``ingest_run_id`` — links each row to the :class:`IngestRun` that produced it,
      giving a per-row provenance / audit trail.
    - ``created_at`` / ``updated_at`` — server-side timestamps.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ingest_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingest_run.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{type(self).__name__} id={self.id}>"
