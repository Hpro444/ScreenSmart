"""Risk-based decisioning layer.

Payment CONTEXT — amount, currency, rail, originator country — does NOT identify the
beneficiary, so it must never change the name/identity *match probability*. Instead it
sets **how cautious to be**: a large wire from a high-risk corridor should be flagged on
weaker name evidence than a small domestic card payment. We compute a transparent risk
score in [0,1] and use it to LOWER the decision thresholds for risky payments.

Deliberately rule-based and explainable (no labels, no black box) — a compliance officer
can read exactly why a payment's threshold was tightened.
"""
from __future__ import annotations
import math
from typing import Optional

# rough per-rail base risk (higher = more anonymous / cross-border / irreversible)
RAIL_RISK = {"crypto": 0.85, "SWIFT": 0.70, "FedWire": 0.60,
             "ACH": 0.30, "FPS": 0.25, "SEPA": 0.20, "card": 0.15}

# illustrative high-risk jurisdictions (FATF-style call-to-action / monitored)
HIGH_RISK_COUNTRIES = {"ir", "kp", "sy", "af", "ru", "by", "mm", "cu", "ve"}

# currencies more associated with sanctions-evasion flows (illustrative)
HIGH_RISK_CCY = {"RUB", "IRR", "KPW"}

# weights for the blended score (sum = 1.0)
_W_AMOUNT, _W_RAIL, _W_COUNTRY, _W_CCY = 0.35, 0.30, 0.25, 0.10
# how far a max-risk payment may lower the thresholds
MAX_THRESHOLD_SHIFT = 0.15


def amount_risk(amount: Optional[float]) -> float:
    """0 around small retail payments, saturating to 1 for large (~$1M+) transfers."""
    if not amount or amount <= 0:
        return 0.0
    return max(0.0, min(1.0, (math.log10(amount) - 3.0) / 3.0))   # $1k->0, $1M->1


def payment_risk(amount: Optional[float] = None, currency: Optional[str] = None,
                 rail: Optional[str] = None, orig_country: Optional[str] = None
                 ) -> tuple[float, list[str]]:
    """Return (risk_score in [0,1], human-readable factor list)."""
    r_amt = amount_risk(amount)
    r_rail = RAIL_RISK.get(rail or "", 0.30)
    r_ctry = 0.85 if (orig_country or "").lower() in HIGH_RISK_COUNTRIES else 0.10
    r_ccy = 0.70 if (currency or "").upper() in HIGH_RISK_CCY else 0.10

    score = _W_AMOUNT * r_amt + _W_RAIL * r_rail + _W_COUNTRY * r_ctry + _W_CCY * r_ccy
    score = round(min(1.0, score), 3)

    factors = []
    if r_amt >= 0.5:
        factors.append(f"large amount ({amount:,.0f})")
    if r_rail >= 0.6:
        factors.append(f"higher-risk rail ({rail})")
    if r_ctry >= 0.5:
        factors.append(f"high-risk originator country ({orig_country})")
    if r_ccy >= 0.5:
        factors.append(f"high-risk currency ({currency})")
    return score, factors


def adjust_thresholds(tau_high: float, tau_low: float, risk: float) -> tuple[float, float]:
    """Lower both thresholds proportionally to risk (more risk -> flag/block sooner)."""
    shift = MAX_THRESHOLD_SHIFT * max(0.0, min(1.0, risk))
    return max(0.0, tau_high - shift), max(0.0, tau_low - shift)
