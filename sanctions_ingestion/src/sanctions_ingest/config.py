"""Configuration for the sanctions-ingestion service.

pydantic-settings — every field can be overridden via an env var prefixed
``SANCTIONS_INGEST_`` (e.g. ``SANCTIONS_INGEST_INGEST_HOUR=6``). ``DATABASE_URL``
is read without the prefix so it matches the rest of the project (exposure_graph
and docker-compose all use ``DATABASE_URL``).
"""
from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


def _find_root() -> pathlib.Path:
    """Locate the repo root (where ``data/`` lives) by walking up to the
    ``.screensmart-root`` marker — same discovery the main app uses, so raw
    files land in the shared ``data/`` tree regardless of nesting depth.
    """
    here = pathlib.Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".screensmart-root").exists() or (parent / "data").is_dir():
            return parent
    return here.parents[3]  # fallback: <repo>/sanctions_ingestion/src/sanctions_ingest/


_ROOT = _find_root()

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://screensmart:screensmart@localhost:5432/screensmart"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SANCTIONS_INGEST_", extra="ignore")

    # Database — note: read from the un-prefixed DATABASE_URL env var (see below).
    database_url: str = DEFAULT_DATABASE_URL

    # Paths
    root_dir: pathlib.Path = _ROOT
    raw_dir: pathlib.Path = _ROOT / "data" / "raw"
    logs_dir: pathlib.Path = _ROOT / "sanctions_ingestion" / "logs"

    # Daily schedule (server local time)
    ingest_hour: int = 3
    ingest_minute: int = 0
    run_on_startup: bool = True

    # HTTP
    http_timeout: int = 120
    user_agent: str = "ScreenSmart-SanctionsIngest/1.0 (research; data download)"

    def ensure_dirs(self) -> None:
        """Create output directories; idempotent."""
        for d in (self.raw_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
# DATABASE_URL is the project-wide convention (un-prefixed); honour it if present.
settings.database_url = os.getenv("DATABASE_URL", settings.database_url)
