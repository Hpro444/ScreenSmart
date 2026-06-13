"""Configuration — paths, thresholds and training knobs.

Uses pydantic-settings so any field can be overridden via an env var prefixed
SCREENSMART_ (e.g. SCREENSMART_TAU_HIGH=0.95).
"""
from __future__ import annotations
import pathlib
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = pathlib.Path(__file__).resolve().parents[2]   # repo root (…/Hakathon)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCREENSMART_", extra="ignore")

    # paths
    root_dir: pathlib.Path = _ROOT
    processed_dir: pathlib.Path = _ROOT / "data" / "processed"
    models_dir: pathlib.Path = _ROOT / "models"
    visuals_dir: pathlib.Path = _ROOT / "reports" / "visuals"

    sanctions_parquet: pathlib.Path = _ROOT / "data" / "processed" / "sanctions_clean.parquet"
    transactions_parquet: pathlib.Path = _ROOT / "data" / "processed" / "transactions.parquet"
    model_path: pathlib.Path = _ROOT / "models" / "precision_model.joblib"

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

    def ensure_dirs(self) -> None:
        """Create all output directories; idempotent — safe to call on every run."""
        for d in (self.processed_dir, self.models_dir, self.visuals_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
