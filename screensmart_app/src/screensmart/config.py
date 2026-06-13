"""Configuration — paths, thresholds and training knobs.

Uses pydantic-settings so any field can be overridden via an env var prefixed
SCREENSMART_ (e.g. SCREENSMART_TAU_HIGH=0.95).
"""
from __future__ import annotations
import pathlib
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root() -> pathlib.Path:
    """Locate the data root (where `data/` lives) by walking up to the
    `.screensmart-root` marker. The code lives in the `screensmart_app/` bundle while
    the large `data/` artifacts stay at the repo root, so depth isn't fixed.
    """
    here = pathlib.Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".screensmart-root").exists() or (parent / "data").is_dir():
            return parent
    return here.parents[2]   # fallback: original layout


_ROOT = _find_root()                              # repo root — holds data/, reports/
_BUNDLE = pathlib.Path(__file__).resolve().parents[2]   # screensmart_app/ — holds code, models/, logs/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCREENSMART_", extra="ignore")

    # paths — data/reports at the repo root; code/models/logs in the bundle
    root_dir: pathlib.Path = _ROOT
    bundle_dir: pathlib.Path = _BUNDLE
    raw_dir: pathlib.Path = _ROOT / "data" / "raw"
    processed_dir: pathlib.Path = _ROOT / "data" / "processed"
    visuals_dir: pathlib.Path = _ROOT / "reports" / "visuals"
    models_dir: pathlib.Path = _BUNDLE / "models"
    logs_dir: pathlib.Path = _BUNDLE / "logs"

    sanctions_parquet: pathlib.Path = _ROOT / "data" / "processed" / "sanctions_clean.parquet"
    transactions_parquet: pathlib.Path = _ROOT / "data" / "processed" / "transactions.parquet"
    model_path: pathlib.Path = _BUNDLE / "models" / "precision_model.joblib"

    # data source: "parquet" (offline snapshot) or "db" (live Postgres from sanctions_ingestion)
    sanctions_source: str = "parquet"
    # reads the unprefixed DATABASE_URL (shared with sanctions_ingestion / exposure_graph)
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")
    opensanctions_dataset: str = "sanctions"    # which opensanctions_target feed to load
    use_crypto_exposure: bool = True            # consult exposure_index for crypto wallets (DB mode)
    exposure_review_threshold: float = 0.08     # graph exposure score -> REVIEW

    # decision thresholds on the calibrated probability (overridden by the
    # values learned during training and stored in the model artifact)
    tau_high: float = 0.90      # p >= tau_high          -> MATCH (block)
    tau_low: float = 0.50       # tau_low <= p < tau_high -> REVIEW (human)

    # screening / recall
    max_candidates: int = 150   # cap on candidates scored per query (IDF-ranked)

    # training
    random_seed: int = 42
    target_precision: float = 0.95   # block precision we tune thresholds to hit
    threshold_tune_frac: float = 0.5  # fraction of the live stream used to tune thresholds
    review_budget: float = 0.08       # max fraction of traffic sent to MATCH+REVIEW

    def ensure_dirs(self) -> None:
        """Create all output directories; idempotent — safe to call on every run."""
        for d in (self.processed_dir, self.models_dir, self.visuals_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
