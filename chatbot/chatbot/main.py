"""ScreenSmart chatbot service — streams plain-language explanations of why a payment was
flagged, using a local LLM (Ollama) orchestrated with LangGraph.

  POST /chat     { dossier, messages: [{role, content}] } -> streamed text tokens
  GET  /health   service + Ollama reachability / model availability
"""
from __future__ import annotations
import contextlib

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from .config import settings
from .agent import astream_answer

app = FastAPI(title="ScreenSmart Chatbot", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    dossier: dict = {}
    messages: list[dict] = []


@app.get("/health")
async def health():
    info = {"status": "ok", "model": settings.ollama.model, "ollama": settings.ollama.base_url,
            "ollama_reachable": False, "model_available": False}
    with contextlib.suppress(Exception):
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(f"{settings.ollama.base_url}/api/tags")
            if r.status_code == 200:
                info["ollama_reachable"] = True
                tags = [m.get("name", "") for m in r.json().get("models", [])]
                info["model_available"] = any(t == settings.ollama.model
                                               or t.split(":")[0] == settings.ollama.model.split(":")[0]
                                               for t in tags)
    return info


@app.post("/chat")
async def chat(req: ChatRequest):
    async def gen():
        try:
            async for tok in astream_answer(req.dossier, req.messages):
                yield tok
        except Exception as e:                     # Ollama down / model missing → readable msg
            yield ("\n\n⚠️ The assistant couldn't reach the local model "
                   f"({settings.ollama.model} @ {settings.ollama.base_url}). "
                   f"Check that Ollama is running and the model is pulled.\n\n[{type(e).__name__}: {e}]")
    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


@app.get("/")
def root():
    return JSONResponse({"service": "screensmart-chatbot", "chat": "POST /chat", "health": "GET /health"})
