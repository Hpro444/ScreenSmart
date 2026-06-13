"""Kafka worker — wraps SanctionsScreener as a streaming consumer.

Consumes `screening.txns`, runs name/identity screening on fiat payments, and produces a
`ModuleResult`-shaped JSON to `screening.results.name`. Crypto payments are not this
module's job → emitted as `applicable=False` so the accumulator ignores them.

Run (in its own container; do NOT co-deploy with exposure_graph — both use the package
name `screensmart`):  python -m screensmart.worker
"""
from __future__ import annotations
import asyncio
import contextlib
import json
import os
import sys

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from .config import settings as app_settings
from .screening.screener import SanctionsScreener
from .domain.models import PaymentInstruction
from .domain.enums import Channel

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC_TXNS = os.environ.get("TOPIC_TXNS", "screening.txns")
TOPIC_OUT = os.environ.get("TOPIC_RESULTS_NAME", "screening.results.name")
GROUP = os.environ.get("WORKER_GROUP", "screensmart-name")


def _na(txn_id: str) -> dict:
    return {"txn_id": txn_id, "module": "name", "verdict": "NO_MATCH", "score": 0.0,
            "reasons": ["nothing to screen (no name/wallet)"], "applicable": False,
            "latency_ms": 0.0}


def _payment(txn_id: str, v: dict) -> "PaymentInstruction | None":
    """Build a PaymentInstruction for either channel; None if nothing to screen."""
    if v.get("channel") == "crypto" and v.get("wallet"):
        return PaymentInstruction(txn_id=txn_id, channel=Channel.CRYPTO, wallet=v["wallet"],
                                  amount=v.get("amount"), currency=v.get("currency"),
                                  rail=v.get("rail"), orig_country=v.get("orig_country"))
    if v.get("bene_name"):
        return PaymentInstruction(
            txn_id=txn_id, channel=Channel.FIAT, amount=v.get("amount"),
            currency=v.get("currency"), rail=v.get("rail"),
            orig_country=v.get("orig_country"), bene_name=v["bene_name"],
            bene_country=v.get("bene_country") or "", bene_dob=v.get("bene_dob"),
            bene_passport=v.get("bene_passport"), bene_national_id=v.get("bene_national_id"))
    return None


def _result(txn_id: str, r) -> dict:
    return {"txn_id": txn_id, "module": "name", "verdict": r.verdict.value,
            "score": round(r.probability, 4), "matched_name": r.matched_name,
            "entity_id": r.entity_id, "reasons": r.reasons,
            "detail": {"model": r.model_name, "raw_fuzzy_score": r.raw_fuzzy_score,
                       "risk_score": r.risk_score},
            "applicable": True, "latency_ms": round(r.latency_ms, 3)}


async def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    scr = SanctionsScreener.load(app_settings)
    print(f"[screensmart.worker] model={scr.model_name} entities={scr.index.n_entities} "
          f"bootstrap={BOOTSTRAP}", flush=True)
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v, default=str).encode(),
        key_serializer=lambda k: k.encode() if k else None, enable_idempotence=True)
    consumer = AIOKafkaConsumer(
        TOPIC_TXNS, bootstrap_servers=BOOTSTRAP, group_id=GROUP,
        value_deserializer=lambda b: json.loads(b.decode()),
        enable_auto_commit=True, auto_offset_reset="earliest")
    await producer.start()
    await consumer.start()
    try:
        async for msg in consumer:
            v = msg.value
            txn_id = v.get("txn_id")
            if not txn_id:
                continue
            pay = _payment(txn_id, v)
            out = _result(txn_id, scr.screen(pay)) if pay is not None else _na(txn_id)
            await producer.send_and_wait(TOPIC_OUT, key=txn_id, value=out)
    finally:
        with contextlib.suppress(Exception):
            await consumer.stop()
        with contextlib.suppress(Exception):
            await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
