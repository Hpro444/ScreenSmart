"""Continuous payment generator — keeps the live feed (and the dashboard's particle
animation) flowing with *genuine* screening traffic.

Unlike `ingest /ingest/replay` (a finite, one-shot drain of the seed file that reuses the
original txn_ids), this runs forever and stamps every payment with a FRESH unique txn_id +
current timestamp — so each emission is a brand-new screening the accumulator won't dedupe,
and the counts / review queue keep growing live.

It samples realistic, already-labelled payments from the synthetic transactions parquet, so
the verdict mix on screen (mostly green, occasional amber/red, some crypto) matches what the
engine really produces.

Run as its own service:  python -m pipeline.generator
Env:
  KAFKA_BOOTSTRAP   broker            (default kafka:9092)
  GEN_RATE          payments/second   (default 8)
  GEN_JITTER        0..1 fractional jitter on inter-arrival delay (default 0.5 → bursty/natural)
  GEN_SEED_PATH     sample parquet    (default /app/data/processed/transactions.parquet)
"""
from __future__ import annotations
import asyncio
import contextlib
import datetime as dt
import math
import os
import random
import uuid

from .bus import make_producer
from .config import settings
from .contracts import TxnEvent

RATE = float(os.environ.get("GEN_RATE", "8"))
JITTER = min(max(float(os.environ.get("GEN_JITTER", "0.5")), 0.0), 0.95)
SEED_PATH = os.environ.get("GEN_SEED_PATH", "/app/data/processed/transactions.parquet")

# the payment fields a TxnEvent carries (everything else in the parquet is a training label)
_FIELDS = ["channel", "amount", "currency", "rail", "orig_country", "bene_name",
           "bene_country", "wallet", "bene_dob", "bene_passport", "bene_national_id"]


def _clean(v):
    """parquet → JSON-safe: drop NaN/NaT, keep the rest."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _load_samples() -> list[dict]:
    import pandas as pd
    df = pd.read_parquet(SEED_PATH)
    cols = [c for c in _FIELDS if c in df.columns]
    return df[cols].to_dict("records")


def _event(sample: dict) -> TxnEvent:
    g = lambda k: _clean(sample.get(k))
    return TxnEvent(
        txn_id=f"GEN-{uuid.uuid4().hex[:12]}",
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        channel=str(g("channel") or "fiat"),
        amount=float(sample["amount"]) if g("amount") is not None else None,
        currency=g("currency"), rail=g("rail"), orig_country=g("orig_country"),
        bene_name=g("bene_name") or "", bene_country=g("bene_country") or "",
        wallet=g("wallet") or "",
        bene_dob=g("bene_dob"), bene_passport=g("bene_passport"),
        bene_national_id=g("bene_national_id"))


async def run() -> None:
    samples = _load_samples()
    if not samples:
        raise SystemExit(f"[generator] no sample payments in {SEED_PATH}")
    print(f"[generator] {len(samples)} sample payments | rate={RATE}/s jitter={JITTER} "
          f"-> {settings.topic_txns} @ {settings.kafka_bootstrap}", flush=True)

    producer = await make_producer(settings.kafka_bootstrap)
    base = 1.0 / RATE if RATE > 0 else 0.125
    n = 0
    try:
        while True:
            evt = _event(random.choice(samples))
            await producer.send_and_wait(settings.topic_txns, key=evt.txn_id, value=evt.model_dump())
            n += 1
            if n % 500 == 0:
                print(f"[generator] emitted {n}", flush=True)
            delay = base * (1 + random.uniform(-JITTER, JITTER)) if JITTER else base
            await asyncio.sleep(max(0.0, delay))
    finally:
        with contextlib.suppress(Exception):
            await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
