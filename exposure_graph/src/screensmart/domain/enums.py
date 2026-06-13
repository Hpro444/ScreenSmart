"""Verdict enum shared by the exposure-graph and the main screening engine."""

from __future__ import annotations

from enum import Enum


class VerdictType(str, Enum):
    MATCH = "MATCH"      # block — direct sanctioned account
    REVIEW = "REVIEW"    # route to a human analyst
    NO_MATCH = "NO_MATCH"  # release
