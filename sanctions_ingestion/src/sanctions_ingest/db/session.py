"""SQLAlchemy engine + session management.

Same engine/URL pattern as ``exposure_graph/src/screensmart/db/database.py`` —
one shared engine, ``DATABASE_URL`` from the environment, Postgres default.
``session_scope()`` is a transactional contextmanager (commit / rollback / close).
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings


@lru_cache(maxsize=1)
def get_engine() -> sa.Engine:
    """Create (once) and return the shared SQLAlchemy engine."""
    return sa.create_engine(settings.database_url, future=True, pool_pre_ping=True)


SessionLocal = sessionmaker(
    bind=get_engine(), autoflush=False, autocommit=False, future=True
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional session scope: commit on success, rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
