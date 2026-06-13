"""Evaluate a screener against the labelled transaction stream.

Shared by train_model.py (model selection) and benchmark.py (reporting) so the
quality numbers are computed one way only.
"""
from __future__ import annotations
import time
import pandas as pd

from .screening.screener import SanctionsScreener
from .domain.enums import VerdictType, Channel
from .domain.models import ModelMetrics, PaymentInstruction


def row_to_payment(row) -> PaymentInstruction:
    """Build a PaymentInstruction from a transactions.parquet row (handles optional cols)."""
    def g(k):
        v = row[k] if k in row else None
        return (v or None) if isinstance(v, str) else v
    return PaymentInstruction(
        txn_id=str(row["txn_id"]), channel=Channel(row["channel"]),
        amount=g("amount"), currency=g("currency"), rail=g("rail"),
        orig_country=g("orig_country"),
        bene_name=row["bene_name"] if "bene_name" in row else "",
        bene_country=row["bene_country"] if "bene_country" in row else "",
        wallet=row["wallet"] if "wallet" in row else "",
        bene_dob=g("bene_dob"), bene_passport=g("bene_passport"),
        bene_national_id=g("bene_national_id"))

# payments that should NOT be auto-blocked (legit) — used for over-block rate
_CLEAN = {"clean", "fp_bait", "crypto_clean"}
# genuinely sanctioned payments — used for the safety (flag) recall
_SANCTIONED = {"sanctioned_exact", "sanctioned_reorder", "sanctioned_translit",
               "sanctioned_typo", "crypto_sanctioned"}


def screen_row(screener: SanctionsScreener, row) -> tuple[str, float, float]:
    """Return (verdict, probability, latency_ms) for one transaction row — the full
    pipeline (identity + risk) via screen()."""
    r = screener.screen(row_to_payment(row))
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
    # Ground truth is BINARY by scenario: a payment either names a genuinely
    # sanctioned party or it does not. Auto-blocking a sanctioned party is correct
    # whether we'd called it MATCH or REVIEW; blocking a clean one is the error.
    sanc = s["scenario"].isin(_SANCTIONED)
    clean = s["scenario"].isin(_CLEAN)
    pred_block = s["pred"].eq(VerdictType.MATCH.value)
    flagged = s["pred"].isin([VerdictType.MATCH.value, VerdictType.REVIEW.value])

    tp = int((sanc & pred_block).sum())                  # correctly auto-blocked
    fp = int((clean & pred_block).sum())                 # wrongly auto-blocked
    precision = tp / (tp + fp) if (tp + fp) else 0.0     # of blocks, fraction sanctioned
    recall = tp / int(sanc.sum()) if sanc.sum() else 0.0  # of sanctioned, fraction blocked
    over_block = float((clean & pred_block).sum() / clean.sum() * 100) if clean.sum() else 0.0
    review_rate = float(s["pred"].eq(VerdictType.REVIEW.value).mean() * 100)
    # safety metric: of sanctioned payments, fraction NOT released (>= REVIEW)
    flag_recall = float((sanc & flagged).sum() / sanc.sum()) if sanc.sum() else 0.0

    metrics = ModelMetrics(
        model_name=screener.model_name,
        block_precision=round(precision, 4),
        recall=round(recall, 4),
        flag_recall=round(flag_recall, 4),
        over_block_rate=round(over_block, 4),
        review_rate=round(review_rate, 4),
        tau_high=screener.tau_high,
        tau_low=screener.tau_low,
        train_seconds=0.0,
        mean_latency_ms=round(sum(lats) / len(lats), 4) if lats else 0.0,
    )
    return metrics, verdicts, lats
