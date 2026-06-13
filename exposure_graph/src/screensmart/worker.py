"""Kafka worker — wraps the crypto graph-hop exposure engine as a streaming consumer.

Consumes `screening.txns`, runs `AccountExposureLookup.screen_account()` on the wallet/
account node_key, and produces a `ModuleResult`-shaped JSON to `screening.results.exposure`.
Payments with no account/wallet → `applicable=False`.

Run in its OWN container (its package is named `screensmart`, like screensmart_app — they
must not share a process):  python -m screensmart.worker
"""
from __future__ import annotations
import asyncio
import contextlib
import json
import os
import sys

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from screensmart.exposure.lookup import AccountExposureLookup

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC_TXNS = os.environ.get("TOPIC_TXNS", "screening.txns")
TOPIC_OUT = os.environ.get("TOPIC_RESULTS_EXPOSURE", "screening.results.exposure")
GROUP = os.environ.get("WORKER_GROUP", "exposure")


def _na(txn_id: str) -> dict:
    return {"txn_id": txn_id, "module": "exposure", "verdict": "NO_MATCH", "score": 0.0,
            "reasons": ["no account/wallet to trace"], "applicable": False, "latency_ms": 0.0}


def _result(txn_id: str, res) -> dict:
    return {"txn_id": txn_id, "module": "exposure",
            "verdict": getattr(res.verdict, "value", str(res.verdict)),
            "score": round(float(res.exposure_score), 4),
            "matched_name": res.source_risk_node, "entity_id": res.source_risk_node,
            "reasons": [res.reason] if getattr(res, "reason", None) else [],
            "detail": {"best_depth": res.best_depth, "best_path": res.best_path,
                       "rule_triggers": getattr(res, "rule_triggers", [])},
            "applicable": True, "latency_ms": round(float(res.latency_ms), 3)}


def _node_key(v: dict) -> str | None:
    """The graph node to trace: the crypto wallet, or a beneficiary account if present."""
    return v.get("wallet") or None


async def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    lookup = AccountExposureLookup.load()
    print(f"[exposure.worker] loaded exposure index; bootstrap={BOOTSTRAP}", flush=True)
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
            key = _node_key(v)
            if key:
                try:
                    out = _result(txn_id, lookup.screen_account(key))
                except Exception as e:        # never drop a txn on a screening error
                    out = {**_na(txn_id), "reasons": [f"exposure error: {e}"]}
            else:
                out = _na(txn_id)
            await producer.send_and_wait(TOPIC_OUT, key=txn_id, value=out)
    finally:
        with contextlib.suppress(Exception):
            await consumer.stop()
        with contextlib.suppress(Exception):
            await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
