"""Output models — the screener's verdict and model evaluation summary."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from .enums import VerdictType, Channel


class ScreeningResult(BaseModel):
    """The verdict returned for a payment — the screener's public output."""
    model_config = ConfigDict(protected_namespaces=())

    verdict: VerdictType
    probability: float           # calibrated P(true match); 0-1
    raw_fuzzy_score: float
    query: str
    channel: Channel
    entity_id: Optional[str] = None
    matched_name: Optional[str] = None
    reasons: list[str] = Field(default_factory=list)
    model_name: str = "fuzzy-fallback"
    latency_ms: float = 0.0


class ModelMetrics(BaseModel):
    """Evaluation summary for one trained model (the comparison report)."""
    model_config = ConfigDict(protected_namespaces=())

    model_name: str
    block_precision: float       # of MATCH verdicts, fraction truly sanctioned
    recall: float                # of true-MATCH payments, fraction auto-blocked
    flag_recall: float           # of ALL sanctioned payments, fraction NOT released
                                 #   (caught as MATCH or REVIEW) — the safety metric
    over_block_rate: float       # % of clean payments wrongly blocked
    review_rate: float           # % of all payments routed to a human
    tau_high: float
    tau_low: float
    train_seconds: float
    mean_latency_ms: float
