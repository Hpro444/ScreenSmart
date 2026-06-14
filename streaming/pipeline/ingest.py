"""Ingest gateway — the front door to the streaming pipeline.

  POST /ingest         push one payment (TxnEvent) → produce to screening.txns
  POST /ingest/replay  stream the synthetic transactions.parquet as a live feed
                       (count, rate/sec) so the dashboard fills with real dots
  GET  /health

Produces to a single topic keyed by txn_id; both screening workers fan out from it.
"""
from __future__ import annotations
import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .bus import make_producer
from .contracts import TxnEvent

PRODUCER = None
SEED_PATH = "/app/data/processed/transactions.parquet"   # mounted read-only in compose


@asynccontextmanager
async def lifespan(app: FastAPI):
    global PRODUCER
    PRODUCER = await make_producer(settings.kafka_bootstrap)
    yield
    with contextlib.suppress(Exception):
        await PRODUCER.stop()


app = FastAPI(title="ScreenSmart Ingest Gateway", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def _emit(evt: TxnEvent) -> None:
    await PRODUCER.send_and_wait(settings.topic_txns, key=evt.txn_id,
                                 value=evt.model_dump())


@app.get("/health")
def health():
    return {"status": "ok", "topic": settings.topic_txns, "kafka": settings.kafka_bootstrap}


@app.post("/ingest")
async def ingest(evt: TxnEvent):
    await _emit(evt)
    return {"queued": True, "txn_id": evt.txn_id}


async def _replay(count: int, rate: float) -> None:
    import pandas as pd
    df = pd.read_parquet(SEED_PATH).head(count)
    delay = 1.0 / rate if rate > 0 else 0.0
    for _, r in df.iterrows():
        evt = TxnEvent(
            txn_id=str(r.get("txn_id")), timestamp=str(r.get("timestamp") or ""),
            channel=str(r.get("channel") or "fiat"),
            amount=float(r["amount"]) if r.get("amount") is not None else None,
            currency=r.get("currency"), rail=r.get("rail"), orig_country=r.get("orig_country"),
            bene_name=r.get("bene_name") or "", bene_country=r.get("bene_country") or "",
            wallet=r.get("wallet") or "",
            bene_dob=(r.get("bene_dob") or None), bene_passport=(r.get("bene_passport") or None),
            bene_national_id=(r.get("bene_national_id") or None))
        await _emit(evt)
        if delay:
            await asyncio.sleep(delay)


@app.post("/ingest/replay")
async def replay(bg: BackgroundTasks, count: int = 500, rate: float = 20.0):
    """Stream `count` transactions from the synthetic stream at `rate`/sec into Kafka."""
    bg.add_task(_replay, count, rate)
    return {"replaying": count, "rate_per_s": rate}
