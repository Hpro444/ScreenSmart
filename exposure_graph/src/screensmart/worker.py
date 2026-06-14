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


def _build_graph(lookup: AccountExposureLookup, res) -> dict | None:
    """Turn the winning `best_path` into a small node-link graph the dashboard can draw:
    account → hop(s) → sanctioned/suspicious source, enriched with display names + risk."""
    path = list(getattr(res, "best_path", None) or [])
    if not path:
        return None
    meta = lookup.nodes_by_key
    nodes, edges = [], []
    n = len(path)
    for i, step in enumerate(path):
        nk = step.get("node_key")
        m = meta.get(nk, {})
        risk = str(step.get("risk_level") or m.get("risk_level") or "NONE").upper()
        role = "account" if i == 0 else ("source" if i == n - 1 else "hop")
        nodes.append({
            "id": nk,
            "label": m.get("display_name") or nk,
            "type": step.get("node_type") or m.get("node_type"),
            "risk": risk,
            "country": m.get("country"),
            "role": role,
        })
        if i > 0:
            edges.append({
                "from": path[i - 1].get("node_key"),
                "to": nk,
                "type": step.get("edge_type"),
                "amount": step.get("amount"),
                "flow": step.get("semantic_flow"),         # outbound_to_anchor | inbound_from_anchor
            })
    return {"nodes": nodes, "edges": edges,
            "depth": res.best_depth, "score": round(float(res.exposure_score), 4),
            "source": res.source_risk_node}


def _chain(lookup: AccountExposureLookup, res) -> list[dict]:
    """The full discovered route, hop by hop — payee → … → risk source — with the edge
    that connected each step and a plain-language description of *how* it was traversed."""
    path = list(getattr(res, "best_path", None) or [])
    meta = lookup.nodes_by_key
    out = []
    for i, step in enumerate(path):
        nk = step.get("node_key")
        m = meta.get(nk, {})
        flow = str(step.get("semantic_flow") or "")
        edge = step.get("edge_type")
        if i == 0:
            via = "starting account (the payee)"
        elif flow == "outbound_to_anchor":
            via = f"sent funds ({edge}) onward toward the risk source"
        elif flow == "inbound_from_anchor":
            via = f"received funds ({edge}) from upstream"
        else:
            via = f"linked via {edge}" if edge else "linked"
        out.append({
            "step": i,
            "node_key": nk,
            "label": m.get("display_name") or nk,
            "type": step.get("node_type") or m.get("node_type"),
            "risk": str(step.get("risk_level") or m.get("risk_level") or "NONE").upper(),
            "country": m.get("country"),
            "edge_type": edge,
            "amount": step.get("amount"),
            "transaction_count": step.get("transaction_count"),
            "first_seen": step.get("first_seen"),
            "last_seen": step.get("last_seen"),
            "flow": flow,
            "via": via,
        })
    return out


def _evidence(res) -> list[dict]:
    """Trimmed evidence package — the reason codes + scores that explain the decision."""
    out = []
    for e in (getattr(res, "evidence", None) or []):
        out.append({
            "reason_code": e.get("reason_code"),
            "severity": e.get("severity"),
            "score_contribution": e.get("score_contribution"),
            "explanation": e.get("explanation"),
        })
    return out


def _result(txn_id: str, res, lookup: AccountExposureLookup) -> dict:
    src = lookup.nodes_by_key.get(res.source_risk_node or "", {})
    return {"txn_id": txn_id, "module": "exposure",
            "verdict": getattr(res.verdict, "value", str(res.verdict)),
            "score": round(float(res.exposure_score), 4),
            "matched_name": src.get("display_name") or res.source_risk_node,
            "entity_id": res.source_risk_node,
            "reasons": [res.reason] if getattr(res, "reason", None) else [],
            "detail": {"best_depth": res.best_depth,
                       "risk_score": round(float(res.risk_score), 4),
                       "source_risk_level": res.source_risk_level,
                       "rule_triggers": getattr(res, "rule_triggers", []),
                       "chain": _chain(lookup, res),       # full route, how each hop was found
                       "evidence": _evidence(res),         # why — reason codes + contributions
                       "best_path": res.best_path,         # raw path (all per-hop metadata)
                       "graph": _build_graph(lookup, res)},
            "applicable": True, "latency_ms": round(float(res.latency_ms), 3)}


def _node_key(v: dict) -> str | None:
    """The graph node to trace: a beneficiary account (IBAN/graph key) or a crypto wallet."""
    return v.get("bene_account") or v.get("wallet") or None


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
                    out = _result(txn_id, lookup.screen_account(key), lookup)
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
