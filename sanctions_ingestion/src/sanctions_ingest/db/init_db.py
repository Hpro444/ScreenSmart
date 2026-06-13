"""Create the Postgres schema (``Base.metadata.create_all``).

Project convention is create_all, not Alembic (see
``exposure_graph/src/screensmart/db/init_db.py``). Importing
:mod:`sanctions_ingest.models` registers every table on ``Base.metadata``.
"""
from __future__ import annotations

from .. import models  # noqa: F401 — populates Base.metadata with all tables
from .base import Base
from .session import get_engine


def init_db() -> list[str]:
    """Create all tables; return the table names that now exist on the metadata."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return sorted(Base.metadata.tables)


def main() -> None:
    names = init_db()
    print("created/verified tables: " + ", ".join(names))


if __name__ == "__main__":
    main()
