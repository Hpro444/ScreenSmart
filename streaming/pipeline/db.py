"""Postgres store for accumulated verdicts (the analyst dossier + live-feed history).

One table: `pipeline_verdict`. Key columns are denormalised for fast querying of the
review queue / landing feed; the full dossier (both modules + reasons + original txn) is
kept as JSONB so the analyst view has everything without extra joins.
"""
from __future__ import annotations
import functools
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Text, Float, DateTime, JSON, text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

metadata = MetaData()

pipeline_verdict = Table(
    "pipeline_verdict", metadata,
    Column("txn_id", Text, primary_key=True),
    Column("decided_at", DateTime(timezone=True), server_default=func.now()),
    Column("combined_verdict", Text, nullable=False, index=True),  # MATCH|REVIEW|NO_MATCH
    Column("status", Text, nullable=False, index=True),            # blocked|review|allowed
    Column("bene_name", Text),
    Column("channel", Text),
    Column("amount", Float),
    Column("dossier", JSONB().with_variant(JSON, "sqlite"), nullable=False),
)


@functools.lru_cache(maxsize=2)
def get_engine(url: str) -> Engine:
    return create_engine(url, future=True, pool_pre_ping=True)


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)


def upsert_verdict(engine: Engine, rec: dict) -> None:
    """Idempotent upsert keyed by txn_id (at-least-once delivery → exactly-once row)."""
    row = {
        "txn_id": rec["txn_id"],
        "combined_verdict": rec["combined_verdict"],
        "status": rec["status"],
        "bene_name": rec["txn"].get("bene_name") or rec["txn"].get("wallet"),
        "channel": rec["txn"].get("channel"),
        "amount": rec["txn"].get("amount"),
        "dossier": rec,
    }
    stmt = text(
        "INSERT INTO pipeline_verdict (txn_id, combined_verdict, status, bene_name, channel, amount, dossier) "
        "VALUES (:txn_id, :combined_verdict, :status, :bene_name, :channel, :amount, CAST(:dossier AS JSONB)) "
        "ON CONFLICT (txn_id) DO UPDATE SET combined_verdict=EXCLUDED.combined_verdict, "
        "status=EXCLUDED.status, dossier=EXCLUDED.dossier, decided_at=now()"
    )
    import json
    with engine.begin() as conn:
        conn.execute(stmt, {**row, "dossier": json.dumps(row["dossier"], default=str)})


def list_by_status(engine: Engine, status: str, limit: int = 200) -> list[dict]:
    sql = text("SELECT dossier FROM pipeline_verdict WHERE status = :s "
               "ORDER BY decided_at DESC LIMIT :n")
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(sql, {"s": status, "n": limit})]


def get_dossier(engine: Engine, txn_id: str) -> dict | None:
    sql = text("SELECT dossier FROM pipeline_verdict WHERE txn_id = :t")
    with engine.connect() as conn:
        row = conn.execute(sql, {"t": txn_id}).first()
    return row[0] if row else None


def counts(engine: Engine) -> dict:
    sql = text("SELECT status, count(*) FROM pipeline_verdict GROUP BY status")
    with engine.connect() as conn:
        return {s: n for s, n in conn.execute(sql)}
