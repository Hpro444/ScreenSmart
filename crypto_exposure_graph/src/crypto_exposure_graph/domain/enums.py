"""Verdict enum shared by the crypto exposure-graph module."""

from __future__ import annotations

from enum import Enum


class VerdictType(str, Enum):
    MATCH = "MATCH"
    REVIEW = "REVIEW"
    NO_MATCH = "NO_MATCH"
