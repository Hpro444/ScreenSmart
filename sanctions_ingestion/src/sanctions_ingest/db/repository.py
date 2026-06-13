"""Generic repository — the single abstraction every concrete repo extends.

A new repository is just::

    class OfacEntityRepository(BaseRepository[OfacEntity]):
        model = OfacEntity

and it inherits CRUD plus the daily-load primitive :meth:`refresh`, which replaces
a source's rows atomically (delete-then-insert inside the caller's transaction).
"""
from __future__ import annotations

from typing import Generic, Iterable, Sequence, TypeVar

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .base import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseRepository(Generic[ModelT]):
    """Typed CRUD over a single ``BaseModel`` subclass.

    Subclasses set the class attribute :attr:`model`. All methods operate on the
    session passed at construction; transaction boundaries are owned by the caller
    (use :func:`session_scope`).
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        if getattr(self, "model", None) is None:
            raise TypeError(f"{type(self).__name__} must set the class attribute `model`")
        self.session = session

    # --- reads ---------------------------------------------------------------
    def get(self, id_: int) -> ModelT | None:
        """Fetch one row by primary key, or ``None``."""
        return self.session.get(self.model, id_)

    def list(self, *, limit: int | None = None, offset: int = 0) -> list[ModelT]:
        """Return rows, optionally paginated."""
        stmt = sa.select(self.model).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def count(self, **filters) -> int:
        """Count rows, optionally filtered by exact column equality."""
        stmt = sa.select(sa.func.count()).select_from(self.model)
        stmt = self._apply_filters(stmt, filters)
        return int(self.session.scalar(stmt) or 0)

    # --- writes --------------------------------------------------------------
    def add(self, obj: ModelT) -> ModelT:
        """Add a single instance and flush so its primary key is populated."""
        self.session.add(obj)
        self.session.flush()
        return obj

    def bulk_insert(self, rows: Iterable[dict | ModelT]) -> int:
        """Insert many rows. Accepts dicts (fast path) or model instances.

        Returns the number of rows inserted.
        """
        rows = list(rows)
        if not rows:
            return 0
        if isinstance(rows[0], dict):
            self.session.execute(sa.insert(self.model), rows)  # executemany
        else:
            self.session.add_all(rows)  # type: ignore[arg-type]
            self.session.flush()
        return len(rows)

    def delete_where(self, **filters) -> int:
        """Delete rows matching exact column equality. Empty filters ⇒ delete all."""
        stmt = sa.delete(self.model)
        stmt = self._apply_filters(stmt, filters)
        result = self.session.execute(stmt)
        return int(result.rowcount or 0)

    def refresh(
        self,
        rows: Sequence[dict | ModelT],
        *,
        scope: dict | None = None,
        ingest_run_id: int | None = None,
    ) -> int:
        """Full-refresh a source: delete the in-scope rows then insert ``rows``.

        Runs inside the caller's transaction, so readers never observe a
        half-loaded list. ``scope`` narrows the delete (e.g. ``{"dataset": "peps"}``
        for the shared OpenSanctions table); omit it to replace the whole table.
        When ``ingest_run_id`` is given and ``rows`` are dicts, it is stamped onto
        each row for per-row provenance.
        """
        self.delete_where(**(scope or {}))
        if ingest_run_id is not None and rows and isinstance(rows[0], dict):
            for r in rows:
                r.setdefault("ingest_run_id", ingest_run_id)  # type: ignore[union-attr]
        return self.bulk_insert(rows)

    # --- helpers -------------------------------------------------------------
    def _apply_filters(self, stmt, filters: dict):
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        return stmt
