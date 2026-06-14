"""WS gateway — what the frontend talks to.

  WS   /ws/feed         live stream of every verdict (the landing-page dots)
  POST /auth/login      analyst login → JWT
  GET  /review          (auth) the REVIEW queue — full dossiers to action
  GET  /txn/{txn_id}     (auth) one dossier
  GET  /stats           live counts {allowed, review, blocked}
  GET  /health

A single background Kafka consumer drains `screening.verdicts` and broadcasts each verdict
to all connected WebSockets; history/queue come from Postgres.
"""
from __future__ import annotations
import asyncio
import contextlib
import datetime as dt
import json
import uuid
from contextlib import asynccontextmanager

import jwt
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from . import db

CLIENTS: set[WebSocket] = set()
ENGINE = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ENGINE
    ENGINE = db.get_engine(settings.database_url)
    with contextlib.suppress(Exception):
        db.init_db(ENGINE)
    task = asyncio.create_task(_broadcast_verdicts())
    yield
    task.cancel()


app = FastAPI(title="ScreenSmart WS Gateway", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def _broadcast_verdicts() -> None:
    """One consumer (unique group → sees all) fans out live verdicts to every WebSocket."""
    consumer = AIOKafkaConsumer(
        settings.topic_verdicts, bootstrap_servers=settings.kafka_bootstrap,
        group_id=f"ws-{uuid.uuid4()}", auto_offset_reset="latest",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")))
    await consumer.start()
    try:
        async for msg in consumer:
            dead = []
            for ws in list(CLIENTS):
                try:
                    await ws.send_json(msg.value)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                CLIENTS.discard(ws)
    finally:
        with contextlib.suppress(Exception):
            await consumer.stop()


@app.websocket("/ws/feed")
async def ws_feed(ws: WebSocket):
    await ws.accept()
    CLIENTS.add(ws)
    try:
        while True:                       # keep the socket open; we only push
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        CLIENTS.discard(ws)


# ---- auth (demo: single analyst account, JWT bearer) -----------------------
class Login(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
def login(body: Login):
    if body.username != settings.analyst_user or body.password != settings.analyst_password:
        raise HTTPException(401, "invalid credentials")
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=8)
    token = jwt.encode({"sub": body.username, "exp": exp}, settings.jwt_secret, algorithm="HS256")
    return {"token": token, "expires": exp.isoformat()}


def require_auth(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        payload = jwt.decode(authorization[7:], settings.jwt_secret, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid/expired token")


# ---- queries ---------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "clients": len(CLIENTS)}


@app.get("/stats")
def stats():
    counts = db.counts(ENGINE)
    return {"allowed": counts.get("allowed", 0), "review": counts.get("review", 0),
            "blocked": counts.get("blocked", 0)}


_STATUSES = {"allowed", "review", "blocked"}


@app.get("/review")
def review_queue(_: str = Depends(require_auth), status: str = "review", limit: int = 200):
    """Dossiers for a given status (review | allowed | blocked) — sender/recipient/
    identifiers + reasons + module results. Defaults to the REVIEW queue."""
    status = status if status in _STATUSES else "review"
    return db.list_by_status(ENGINE, status, min(max(limit, 1), 500))


@app.get("/txn/{txn_id}")
def dossier(txn_id: str, _: str = Depends(require_auth)):
    d = db.get_dossier(ENGINE, txn_id)
    if d is None:
        raise HTTPException(404, "not found")
    return d
