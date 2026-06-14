"""Load chatbot config from config.yaml, with env-var overrides. Ollama (local models)
is the default backend; point OLLAMA_BASE_URL at the host running Ollama."""
from __future__ import annotations
import os
import pathlib
import yaml
from dataclasses import dataclass

_DEFAULT_PATH = pathlib.Path(__file__).resolve().parents[1] / "config.yaml"


@dataclass
class OllamaCfg:
    base_url: str
    model: str
    temperature: float
    num_ctx: int
    request_timeout: int


@dataclass
class Config:
    ollama: OllamaCfg
    host: str
    port: int


def _env(name: str, default, cast=str):
    v = os.environ.get(name)
    return cast(v) if v not in (None, "") else default


def load_config(path: str | None = None) -> Config:
    p = pathlib.Path(os.environ.get("CHATBOT_CONFIG", path or _DEFAULT_PATH))
    raw = {}
    if p.exists():
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    o = raw.get("ollama", {})
    s = raw.get("server", {})
    ollama = OllamaCfg(
        base_url=_env("OLLAMA_BASE_URL", o.get("base_url", "http://ollama:11434")),
        model=_env("OLLAMA_MODEL", o.get("model", "llama3.2")),
        temperature=_env("OLLAMA_TEMPERATURE", float(o.get("temperature", 0.2)), float),
        num_ctx=_env("OLLAMA_NUM_CTX", int(o.get("num_ctx", 8192)), int),
        request_timeout=_env("OLLAMA_TIMEOUT", int(o.get("request_timeout", 120)), int),
    )
    return Config(
        ollama=ollama,
        host=_env("CHATBOT_HOST", s.get("host", "0.0.0.0")),
        port=_env("CHATBOT_PORT", int(s.get("port", 8092)), int),
    )


settings = load_config()
