"""Event contracts — the JSON shapes that flow over Kafka.

These are the single source of truth for the topic payloads. The screening workers
(in screensmart_app / exposure_graph) emit plain dicts matching `ModuleResult`; the
streaming services validate against these models.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    MATCH = "MATCH"        # block (red)
    REVIEW = "REVIEW"      # human review (yellow)
    NO_MATCH = "NO_MATCH"  # allow (green)


# severity for the worst-of combine (higher = more severe)
SEVERITY = {Verdict.NO_MATCH: 0, Verdict.REVIEW: 1, Verdict.MATCH: 2}
STATUS = {Verdict.MATCH: "blocked", Verdict.REVIEW: "review", Verdict.NO_MATCH: "allowed"}


class TxnEvent(BaseModel):
    """A payment entering the pipeline (ingest → screening.txns)."""
    txn_id: str
    timestamp: Optional[str] = None
    channel: str = "fiat"                 # fiat | crypto
    amount: Optional[float] = None
    currency: Optional[str] = None
    rail: Optional[str] = None
    orig_country: Optional[str] = None
    bene_name: str = ""
    bene_country: str = ""
    wallet: str = ""
    bene_account: Optional[str] = None    # graph node key (IBAN/account) → crypto-exposure trace
    bene_dob: Optional[str] = None
    bene_passport: Optional[str] = None
    bene_national_id: Optional[str] = None


class ModuleResult(BaseModel):
    """A single screening module's partial verdict (worker → results.*)."""
    txn_id: str
    module: str                           # "name" | "exposure"
    verdict: Verdict = Verdict.NO_MATCH
    score: float = 0.0                    # probability (name) or exposure score
    matched_name: Optional[str] = None
    entity_id: Optional[str] = None
    reasons: list[str] = Field(default_factory=list)
    detail: dict = Field(default_factory=dict)   # programs, hops, best_path, etc.
    applicable: bool = True               # False when the module had nothing to screen
    latency_ms: float = 0.0


class VerdictRecord(BaseModel):
    """The accumulated dossier (accumulator → verdicts topic + Postgres + frontend)."""
    txn_id: str
    decided_at: Optional[str] = None
    combined_verdict: Verdict
    status: str                           # blocked | review | allowed
    txn: TxnEvent                         # the original payment (sender/recipient/ids)
    name_result: Optional[ModuleResult] = None
    exposure_result: Optional[ModuleResult] = None
    reasons: list[str] = Field(default_factory=list)

    @classmethod
    def combine(cls, txn: TxnEvent, name: Optional[ModuleResult],
                exposure: Optional[ModuleResult], decided_at: str) -> "VerdictRecord":
        """Worst-of escalation across the applicable modules; aggregate reasons."""
        parts = [r for r in (name, exposure) if r and r.applicable]
        worst = max((p.verdict for p in parts), key=lambda v: SEVERITY[v],
                    default=Verdict.NO_MATCH)
        reasons = []
        for r in parts:
            reasons += [f"[{r.module}] {x}" for x in r.reasons]
        return cls(txn_id=txn.txn_id, decided_at=decided_at, combined_verdict=worst,
                   status=STATUS[worst], txn=txn, name_result=name,
                   exposure_result=exposure, reasons=reasons)
