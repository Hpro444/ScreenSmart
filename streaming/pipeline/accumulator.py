"""Accumulator — the fan-in / stateful join.

Consumes three streams (the original txn + both module results), correlates them by
`txn_id`, and once both module verdicts are in (or a timeout fires) builds the combined
dossier, upserts it to Postgres, and publishes it to `screening.verdicts`.

State is an in-memory map keyed by txn_id (single-instance join). A sweeper flushes
entries that never received both partials within `join_timeout_s` so nothing hangs.
"""
from __future__ import annotations
import asyncio
import contextlib
import datetime as dt
import time

from .config import settings
from .bus import make_producer, make_consumer
from .contracts import TxnEvent, ModuleResult, VerdictRecord
from . import db


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


class Accumulator:
    def __init__(self):
        self.buf: dict[str, dict] = {}        # txn_id -> {txn, name, exposure, ts}
        self.engine = db.get_engine(settings.database_url)
        self.producer = None

    def _entry(self, txn_id: str) -> dict:
        return self.buf.setdefault(txn_id, {"txn": None, "name": None,
                                            "exposure": None, "ts": time.monotonic()})

    def _ready(self, e: dict) -> bool:
        return e["txn"] is not None and e["name"] is not None and e["exposure"] is not None

    async def _finalize(self, txn_id: str, e: dict) -> None:
        txn = e["txn"] or TxnEvent(txn_id=txn_id)
        rec = VerdictRecord.combine(txn, e["name"], e["exposure"], decided_at=_now())
        payload = rec.model_dump()
        db.upsert_verdict(self.engine, payload)
        await self.producer.send_and_wait(settings.topic_verdicts, key=txn_id, value=payload)
        self.buf.pop(txn_id, None)

    async def _sweeper(self) -> None:
        """Flush stale entries (got the txn but not both results in time)."""
        while True:
            await asyncio.sleep(settings.join_timeout_s)
            now = time.monotonic()
            stale = [k for k, e in self.buf.items()
                     if now - e["ts"] > settings.join_timeout_s and e["txn"] is not None]
            for k in stale:
                await self._finalize(k, self.buf[k])

    async def run(self) -> None:
        db.init_db(self.engine)
        self.producer = await make_producer(settings.kafka_bootstrap)
        consumer = make_consumer(
            settings.topic_txns, settings.topic_results_name, settings.topic_results_exposure,
            bootstrap=settings.kafka_bootstrap, group_id="accumulator")
        await consumer.start()
        sweeper = asyncio.create_task(self._sweeper())
        try:
            async for msg in consumer:
                v = msg.value
                txn_id = v.get("txn_id")
                if not txn_id:
                    continue
                e = self._entry(txn_id)
                if msg.topic == settings.topic_txns:
                    e["txn"] = TxnEvent(**v)
                elif msg.topic == settings.topic_results_name:
                    e["name"] = ModuleResult(**v)
                elif msg.topic == settings.topic_results_exposure:
                    e["exposure"] = ModuleResult(**v)
                if self._ready(e):
                    await self._finalize(txn_id, e)
        finally:
            sweeper.cancel()
            with contextlib.suppress(Exception):
                await consumer.stop()
            with contextlib.suppress(Exception):
                await self.producer.stop()


def main() -> None:
    asyncio.run(Accumulator().run())


if __name__ == "__main__":
    main()
