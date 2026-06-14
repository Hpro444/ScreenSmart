"""Thin aiokafka helpers — JSON producer/consumer used by every streaming service."""
from __future__ import annotations
import json
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer


async def make_producer(bootstrap: str) -> AIOKafkaProducer:
    """JSON producer; key = txn_id (so a transaction's events share a partition)."""
    p = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        enable_idempotence=True,
    )
    await p.start()
    return p


def make_consumer(*topics: str, bootstrap: str, group_id: str) -> AIOKafkaConsumer:
    """JSON consumer in a named group. Distinct group_id per service → each service sees
    every message (fan-out). `earliest` so a late consumer still drains the backlog."""
    return AIOKafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
