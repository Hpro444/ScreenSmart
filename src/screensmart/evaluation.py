"""Evaluate a screener against the labelled transaction stream.

Shared by train_model.py (model selection) and benchmark.py (reporting) so the
quality numbers are computed one way only.
"""
from __future__ import annotations
import time
import pandas as pd

from .screening.screener import SanctionsScreener
from .domain.enums import VerdictType, Channel
from .domain.models import ModelMetrics

_CLEAN = {"clean", "fp_bait", "crypto_clean"}


def screen_row(screener: SanctionsScreener, row) -> tuple[str, float, float]:
    """Return (verdict, probability, latency_ms) for one transaction row."""
    if row["channel"] == Channel.CRYPTO.value:
        r = screener.screen_wallet(row["wallet"])
    else:
        r = screener.screen_name(row["bene_name"], row.get("bene_country", ""))
    return r.verdict.value, r.probability, r.latency_ms


def evaluate(screener: SanctionsScreener, tx: pd.DataFrame,
             ) -> tuple[ModelMetrics, list[str], list[float]]:
    """Run the screener over every row; return metrics + per-row verdicts + latencies."""
    verdicts: list[str] = []
    lats: list[float] = []
    t0 = time.perf_counter()
    for _, row in tx.iterrows():
        v, _p, ms = screen_row(screener, row)
        verdicts.append(v)
        lats.append(ms)
    wall = time.perf_counter() - t0

    s = tx.assign(pred=verdicts)
    truth_pos = s["expected_verdict"].eq(VerdictType.MATCH.value)
    pred_block = s["pred"].eq(VerdictType.MATCH.value)
    tp = int((truth_pos & pred_block).sum())
    fp = int((~truth_pos & pred_block).sum())
    fn = int((truth_pos & ~pred_block).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    clean = s["scenario"].isin(_CLEAN)
    over_block = float((clean & pred_block).mean() * 100)
    review_rate = float(s["pred"].eq(VerdictType.REVIEW.value).mean() * 100)

    metrics = ModelMetrics(
        model_name=screener.model_name,
        block_precision=round(precision, 4),
        recall=round(recall, 4),
        over_block_rate=round(over_block, 4),
        review_rate=round(review_rate, 4),
        tau_high=screener.tau_high,
        tau_low=screener.tau_low,
        train_seconds=0.0,
        mean_latency_ms=round(sum(lats) / len(lats), 4) if lats else 0.0,
    )
    return metrics, verdicts, lats
