"""Continuous payment generator — keeps the live feed (and the dashboard's particle
animation) flowing with *genuine* screening traffic.

Unlike `ingest /ingest/replay` (a finite, one-shot drain of the seed file that reuses the
original txn_ids), this runs forever and stamps every payment with a FRESH unique txn_id +
current timestamp — so each emission is a brand-new screening the accumulator won't dedupe,
and the counts / review queue keep growing live.

It samples realistic, already-labelled payments from the synthetic transactions parquet, so
the verdict mix on screen (mostly green, occasional amber/red, some crypto) matches what the
engine really produces. A configurable fraction of payments are additionally tagged with a
real graph account key (sampled from the exposure-graph's `exposure_index`) so the crypto
graph-exposure module genuinely fires and the dashboard shows live exposure graphs.

Run as its own service:  python -m pipeline.generator
Env:
  KAFKA_BOOTSTRAP   broker            (default kafka:9092)
  DATABASE_URL      postgres (for sampling exposure-graph account keys; optional)
  GEN_RATE          payments/second   (default 8)
  GEN_JITTER        0..1 fractional jitter on inter-arrival delay (default 0.5)
  GEN_ACCOUNT_RATE  fraction of payments tagged with a graph account (default 0.22)
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
ACCOUNT_RATE = min(max(float(os.environ.get("GEN_ACCOUNT_RATE", "0.22")), 0.0), 1.0)
# which exposure-path depths (hops to the risk source) to sample accounts for. The offline
# precompute caps depth (default 2), so GEN_MAX_HOPS only yields deeper paths if precompute
# was run with a matching --max-depth.
MIN_HOPS = max(1, int(os.environ.get("GEN_MIN_HOPS", "1")))
MAX_HOPS = max(MIN_HOPS, int(os.environ.get("GEN_MAX_HOPS", "2")))
SEED_PATH = os.environ.get("GEN_SEED_PATH", "/app/data/processed/transactions.parquet")

_FIELDS = ["channel", "amount", "currency", "rail", "orig_country", "bene_name",
           "bene_country", "wallet", "bene_dob", "bene_passport", "bene_national_id"]


def _clean(v):
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


def _load_accounts() -> dict:
    """Sample graph account keys from the exposure index so a slice of payments traces a
    real exposure path. `by_depth[d]` = accounts whose best path is `d` hops to a
    sanctioned/suspicious anchor (→ REVIEW); `direct` = accounts that are themselves
    sanctioned, depth 0 (→ MATCH). Empty if no DB/data."""
    url = settings.database_url
    pools = {"by_depth": {}, "direct": []}
    if not url:
        return pools
    try:
        from sqlalchemy import create_engine, text
        eng = create_engine(url)
        with eng.connect() as c:
            # Per depth: only paths that terminate at a SANCTIONED anchor, so every exposure
            # graph runs all the way to a red source node. Deeper (2-hop) paths carry a low
            # raw exposure_score but still get a high risk_score → REVIEW, so sample by depth.
            for d in range(MIN_HOPS, MAX_HOPS + 1):
                rows = c.execute(text(
                    "SELECT ei.node_key FROM exposure_index ei "
                    "JOIN graph_nodes gn ON gn.node_key = ei.source_risk_node "
                    "WHERE ei.best_depth = :d AND gn.risk_level = 'SANCTIONED' "
                    "ORDER BY ei.exposure_score DESC LIMIT 4000"), {"d": d})
                keys = [r[0] for r in rows]
                if keys:
                    pools["by_depth"][d] = keys
            pools["direct"] = [r[0] for r in c.execute(text(
                "SELECT ei.node_key FROM exposure_index ei JOIN graph_nodes gn "
                "ON gn.node_key = ei.node_key "
                "WHERE ei.best_depth = 0 AND gn.risk_level = 'SANCTIONED' "
                "AND gn.node_type IN ('IBAN','ACCOUNT') LIMIT 2000"))]
        eng.dispose()
    except Exception as e:                                    # DB optional — degrade gracefully
        print(f"[generator] could not load exposure accounts: {e}", flush=True)
    return pools


def _pick_account(pools: dict) -> str | None:
    """With prob ACCOUNT_RATE attach an account: a few direct sanctioned hits, otherwise a
    multi-hop path weighted toward deeper (e.g. 2-hop) routes for richer exposure graphs."""
    if random.random() >= ACCOUNT_RATE:
        return None
    if pools["direct"] and random.random() < 0.15:
        return random.choice(pools["direct"])
    by_depth = {d: ks for d, ks in pools["by_depth"].items() if ks}
    if not by_depth:
        return random.choice(pools["direct"]) if pools["direct"] else None
    depths = list(by_depth)
    depth = random.choices(depths, weights=depths, k=1)[0]     # weight by depth → favour 2-hop
    return random.choice(by_depth[depth])


def _event(sample: dict, account: str | None) -> TxnEvent:
    g = lambda k: _clean(sample.get(k))
    return TxnEvent(
        txn_id=f"GEN-{uuid.uuid4().hex[:12]}",
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        channel=str(g("channel") or "fiat"),
        amount=float(sample["amount"]) if g("amount") is not None else None,
        currency=g("currency"), rail=g("rail"), orig_country=g("orig_country"),
        bene_name=g("bene_name") or "", bene_country=g("bene_country") or "",
        wallet=g("wallet") or "", bene_account=account,
        bene_dob=g("bene_dob"), bene_passport=g("bene_passport"),
        bene_national_id=g("bene_national_id"))


async def run() -> None:
    samples = _load_samples()
    if not samples:
        raise SystemExit(f"[generator] no sample payments in {SEED_PATH}")
    pools = _load_accounts()
    by_depth = {d: len(ks) for d, ks in sorted(pools["by_depth"].items())}
    print(f"[generator] {len(samples)} sample payments | rate={RATE}/s jitter={JITTER} | "
          f"accounts @ {ACCOUNT_RATE:.0%}: hops {MIN_HOPS}-{MAX_HOPS} {by_depth} "
          f"/ {len(pools['direct'])} direct -> {settings.topic_txns} @ {settings.kafka_bootstrap}",
          flush=True)

    producer = await make_producer(settings.kafka_bootstrap)
    base = 1.0 / RATE if RATE > 0 else 0.125
    n = 0
    try:
        while True:
            evt = _event(random.choice(samples), _pick_account(pools))
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
