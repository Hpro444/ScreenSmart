"""Ingestion pipeline — download → parse → atomic refresh → audit, per source.

Each source is independent: a failure is recorded on its :class:`IngestRun` and
logged, but does not abort the rest of the run (same resilience as
``download_data.py``). The data load for a source is one transaction, so all of
its tables refresh atomically.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass

from .db.session import session_scope
from .logging_setup import log_event
from .models import IngestRun
from .sources import SOURCES, SOURCES_BY_NAME, Source, TableLoad
from .download import download


@dataclass
class SourceResult:
    name: str
    status: str          # ok | fail
    rows: int
    bytes: int
    seconds: float
    error: str | None = None


def _start_run(source: Source) -> int:
    """Insert a 'running' audit row and return its id (committed immediately)."""
    with session_scope() as s:
        run = IngestRun(source=source.name, url=source.url, status="running")
        s.add(run)
        s.flush()
        return run.id


def _finish_run(run_id: int, *, status: str, rows: int = 0, nbytes: int = 0,
                error: str | None = None) -> None:
    with session_scope() as s:
        run = s.get(IngestRun, run_id)
        if run is None:  # pragma: no cover - defensive
            return
        run.status = status
        run.rows = rows
        run.bytes = nbytes
        run.error = (error or None) and error[:1000]
        run.finished_at = dt.datetime.now(dt.timezone.utc)


def _apply_loads(loads: list[TableLoad], run_id: int) -> int:
    """Refresh every TableLoad for a source inside ONE transaction; return row total."""
    total = 0
    with session_scope() as s:
        for load in loads:
            repo = load.repo_cls(s)
            rows = [r.to_row() for r in load.rows]
            total += repo.refresh(rows, scope=load.scope, ingest_run_id=run_id)
    return total


def run_source(source: Source) -> SourceResult:
    """Download, parse and load a single source. Never raises — failures are recorded."""
    t0 = time.time()
    run_id = _start_run(source)
    try:
        path, nbytes = download(source.url, source.filename)
        loads = source.loader(path)
        rows = _apply_loads(loads, run_id)
        secs = round(time.time() - t0, 1)
        _finish_run(run_id, status="ok", rows=rows, nbytes=nbytes)
        log_event("ingest", source=source.name, status="ok", rows=rows,
                  bytes=nbytes, seconds=secs)
        return SourceResult(source.name, "ok", rows, nbytes, secs)
    except Exception as e:  # keep going on any single failure
        secs = round(time.time() - t0, 1)
        _finish_run(run_id, status="fail", error=str(e))
        log_event("ingest", source=source.name, status="fail", error=str(e)[:300],
                  seconds=secs)
        return SourceResult(source.name, "fail", 0, 0, secs, error=str(e))


def run_all() -> list[SourceResult]:
    """Ingest every registered source in order."""
    log_event("ingest_start", sources=len(SOURCES))
    results = [run_source(s) for s in SOURCES]
    ok = sum(r.status == "ok" for r in results)
    total_rows = sum(r.rows for r in results)
    log_event("ingest_done", ok=ok, total=len(results), rows=total_rows)
    return results


def run_named(name: str) -> SourceResult:
    """Ingest a single source by registry name (raises KeyError if unknown)."""
    return run_source(SOURCES_BY_NAME[name])
