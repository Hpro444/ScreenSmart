"""Command-line entry points.

    python -m sanctions_ingest.cli init-db
    python -m sanctions_ingest.cli ingest [--source NAME]
    python -m sanctions_ingest.cli run-scheduler

Console scripts (see pyproject): ``si-init-db``, ``si-ingest``, ``si-scheduler``.
"""
from __future__ import annotations

import argparse
import sys

from .config import settings
from .db.init_db import init_db
from .pipeline import SourceResult, run_all, run_named
from .scheduler import run_scheduler
from .sources import SOURCES_BY_NAME


def _print_results(results: list[SourceResult]) -> int:
    print(f"\n{'source':<26}{'status':<8}{'rows':>10}{'bytes':>14}{'secs':>8}")
    print("-" * 66)
    for r in results:
        print(f"{r.name:<26}{r.status:<8}{r.rows:>10,}{r.bytes:>14,}{r.seconds:>8}")
        if r.error:
            print(f"    └─ {r.error[:120]}")
    ok = sum(r.status == "ok" for r in results)
    print("-" * 66)
    print(f"{ok}/{len(results)} sources OK, {sum(r.rows for r in results):,} rows loaded.")
    return 0 if ok else 1


def do_init_db() -> int:
    settings.ensure_dirs()
    names = init_db()
    print("created/verified tables: " + ", ".join(names))
    return 0


def do_ingest(source: str | None) -> int:
    settings.ensure_dirs()
    init_db()  # idempotent — safe if the schema isn't created yet
    if source:
        if source not in SOURCES_BY_NAME:
            print(f"unknown source '{source}'. known: {', '.join(SOURCES_BY_NAME)}",
                  file=sys.stderr)
            return 2
        return _print_results([run_named(source)])
    return _print_results(run_all())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sanctions-ingest",
                                description="Download public sanctions sources into Postgres.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="create the database schema")
    ing = sub.add_parser("ingest", help="download + load sources (all, or one)")
    ing.add_argument("--source", help="ingest only this registry source name")
    sub.add_parser("run-scheduler", help="run the blocking daily scheduler")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init-db":
        return do_init_db()
    if args.command == "ingest":
        return do_ingest(args.source)
    if args.command == "run-scheduler":
        run_scheduler()
        return 0
    return 2


# --- console-script wrappers (pyproject [project.scripts]) -------------------
def init_db_cmd() -> None:
    raise SystemExit(do_init_db())


def ingest_cmd() -> None:
    raise SystemExit(main(["ingest", *sys.argv[1:]]))


def scheduler_cmd() -> None:
    run_scheduler()


if __name__ == "__main__":
    raise SystemExit(main())
