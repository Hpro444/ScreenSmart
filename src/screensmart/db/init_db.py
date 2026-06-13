"""Create the Postgres schema for the synthetic exposure-graph MVP."""

from __future__ import annotations

from .database import get_engine
from .schema import TABLES_IN_ORDER, metadata


def main() -> None:
    engine = get_engine()
    metadata.create_all(engine)
    names = ", ".join(table.name for table in TABLES_IN_ORDER)
    print(f"created tables: {names}")


if __name__ == "__main__":
    main()
