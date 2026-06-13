"""Streaming downloader — fetch one source URL to a file under ``settings.raw_dir``.

Lifted from ``screensmart_app/src/download_data.py`` (chunked streaming, custom
User-Agent, timeout). Returns the number of bytes written so the pipeline can
record it on the ``IngestRun``.
"""
from __future__ import annotations

import pathlib

import requests

from .config import settings


def download(url: str, filename: str) -> tuple[pathlib.Path, int]:
    """Download ``url`` into ``settings.raw_dir/filename``; return (path, bytes)."""
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.raw_dir / filename
    headers = {"User-Agent": settings.user_agent}
    size = 0
    with requests.get(url, headers=headers, stream=True, timeout=settings.http_timeout) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)
    return dest, size
