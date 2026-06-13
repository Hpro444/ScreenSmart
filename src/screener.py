"""Backward-compatibility shim.

The screening engine moved into the `screensmart` clean-architecture package.
This module keeps old imports (`from screener import SanctionsScreener`) working.
Prefer importing from `screensmart.screening.screener` directly.
"""
from __future__ import annotations
from screensmart.screening.screener import SanctionsScreener
from screensmart.normalization import norm, tokens, phon

__all__ = ["SanctionsScreener", "norm", "tokens", "phon"]
