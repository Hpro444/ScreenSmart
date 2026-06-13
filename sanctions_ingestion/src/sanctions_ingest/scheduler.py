"""Daily scheduler — an in-process APScheduler that runs the full ingest.

A ``BlockingScheduler`` fires :func:`pipeline.run_all` once a day at
``settings.ingest_hour:settings.ingest_minute``. On startup it ensures the schema
exists and, if configured and the DB has never had a successful run, kicks off one
ingest immediately so a fresh deployment isn't empty until the first nightly tick.
"""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .db.init_db import init_db
from .db.session import session_scope
from .logging_setup import log_event
from .pipeline import run_all
from .repositories import IngestRunRepository


def _never_succeeded() -> bool:
    """True if no source has ever completed an ingest (DB looks fresh)."""
    with session_scope() as s:
        return IngestRunRepository(s).count(status="ok") == 0


def run_scheduler() -> None:
    """Start the blocking daily scheduler (Ctrl-C to stop)."""
    init_db()  # idempotent: guarantee tables exist before we count / load

    if settings.run_on_startup and _never_succeeded():
        log_event("scheduler_startup_ingest")
        run_all()

    scheduler = BlockingScheduler()
    trigger = CronTrigger(hour=settings.ingest_hour, minute=settings.ingest_minute)
    scheduler.add_job(run_all, trigger, id="daily_ingest",
                      max_instances=1, coalesce=True)
    log_event("scheduler_started", hour=settings.ingest_hour,
              minute=settings.ingest_minute)
    print(f"[sanctions-ingest] daily ingest scheduled at "
          f"{settings.ingest_hour:02d}:{settings.ingest_minute:02d}. Ctrl-C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):  # pragma: no cover
        log_event("scheduler_stopped")
