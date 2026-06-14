"""SQLAlchemy engine/session setup for the Postgres-backed crypto graph MVP."""

from __future__ import annotations

import os
from functools import lru_cache

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://screensmart:screensmart@localhost:5432/screensmart"
)
DATABASE_URL = os.getenv("CRYPTO_DATABASE_URL") or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


@lru_cache(maxsize=1)
def get_engine() -> sa.Engine:
    """Create the shared SQLAlchemy engine."""
    return sa.create_engine(DATABASE_URL, future=True, pool_pre_ping=True)


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def get_session() -> Session:
    """Open a new database session."""
    return SessionLocal()
