"""FastAPI service for sanctions screening.

POST a payment (a name + country, or a crypto wallet) and get back a verdict
(MATCH / REVIEW / NO_MATCH) together with a structured EXPLANATION of why — the
matched entity, the signals that fired, and where the calibrated probability sits
relative to the decision thresholds. Built for the "explain it to a regulator" need.

Run:  .venv\\Scripts\\python.exe src\\serve.py
Docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from .config import settings
from .screening.screener import SanctionsScreener
from .matching.scoring import build_features
from .domain.enums import VerdictType, Channel, CountryMatch
from .domain.models import ScreeningResult, SanctionedEntity, MatchFeatures, PaymentInstruction
from .logging_setup import configure as configure_logging, log_event
from . import risk as risk_layer

# loaded once at startup (index build + model load is ~5s; never per-request)
SCREENER: Optional[SanctionsScreener] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global SCREENER
    configure_logging()
    SCREENER = SanctionsScreener.load(settings)
    log_event("startup", model=SCREENER.model_name, entities=SCREENER.index.n_entities,
              tau_low=SCREENER.tau_low, tau_high=SCREENER.tau_high)
    yield
    log_event("shutdown")
    SCREENER = None


app = FastAPI(
    title="ScreenSmart Sanctions Screening API",
    description="Screen a payment for sanctions exposure and get an explained verdict.",
    version="1.0.0",
    lifespan=lifespan,
)


def screener() -> SanctionsScreener:
    if SCREENER is None:                      # pragma: no cover
        raise HTTPException(503, "screener not loaded yet")
    return SCREENER


# ----------------------------------------------------------------- I/O models
class ScreenRequest(BaseModel):
    """A payment to screen. Provide `name` (+optional `country`) for fiat, or
    `wallet` for crypto."""
    name: Optional[str] = Field(None, examples=["Muammar Qadhafi"])
    country: str = Field("", examples=["ly"], description="ISO-2 country of the payment")
    wallet: Optional[str] = Field(None, examples=[None])
    txn_id: Optional[str] = Field(None, examples=["TX0000001"])
    # secondary identifiers (optional) — strengthen or clear a name match
    dob: Optional[str] = Field(None, examples=["1942-06-07"], description="beneficiary DOB (ISO)")
    passport: Optional[str] = Field(None, description="beneficiary passport number")
    national_id: Optional[str] = Field(None, description="beneficiary national / tax ID")
    # payment context (optional) — feeds the risk layer that modulates thresholds
    amount: Optional[float] = Field(None, examples=[250000])
    currency: Optional[str] = Field(None, examples=["USD"])
    rail: Optional[str] = Field(None, examples=["SWIFT"])
    orig_country: Optional[str] = Field(None, examples=["ru"])

    @model_validator(mode="after")
    def _need_one(self) -> "ScreenRequest":
        if not self.name and not self.wallet:
            raise ValueError("provide either 'name' (fiat) or 'wallet' (crypto)")
        return self

    def to_payment(self) -> PaymentInstruction:
        return PaymentInstruction(
            txn_id=self.txn_id or "api",
            channel=Channel.CRYPTO if self.wallet else Channel.FIAT,
            amount=self.amount, currency=self.currency, rail=self.rail,
            orig_country=self.orig_country, bene_name=self.name or "",
            bene_country=self.country or "", wallet=self.wallet or "",
            bene_dob=self.dob, bene_passport=self.passport, bene_national_id=self.national_id)


class MatchedEntity(BaseModel):
    entity_id: str
    name: str
    type: str
    programs: list[str] = []
    countries: list[str] = []


class Explanation(BaseModel):
    summary: str                       # one-line, human-readable verdict rationale
    decision: str                      # where the probability sits vs the thresholds
    thresholds: dict[str, float]       # {"review": tau_low, "block": tau_high} (risk-adjusted)
    risk_score: float                  # payment-context risk in [0,1]
    signals: list[str]                 # the individual reasons that drove the score


class ScreenResponse(BaseModel):
    txn_id: Optional[str]
    verdict: VerdictType
    probability: float
    channel: Channel
    query: str
    model_name: str
    risk_score: float
    matched_entity: Optional[MatchedEntity]
    explanation: Explanation
    latency_ms: float


# ----------------------------------------------------------------- explanation
def _signals(feats: MatchFeatures, entity: SanctionedEntity) -> list[str]:
    out = [
        f"name similarity {feats.token_sort:.0f}/100 "
        f"(Jaro-Winkler {feats.jaro_winkler:.0f}/100)",
    ]
    if feats.rare_token_overlap >= 0.6:
        out.append(f"shares distinctive/rare name tokens "
                   f"(IDF overlap {feats.rare_token_overlap:.2f})")
    elif feats.rare_token_overlap < 0.3:
        out.append("only common name tokens overlap — weak signal")
    else:
        out.append(f"partial distinctive-token overlap ({feats.rare_token_overlap:.2f})")

    # secondary-identity corroboration (the new layer)
    if feats.id_match >= 1.0:
        out.append("passport / national-ID EXACTLY matches the sanctioned entity (definitive)")
    if feats.dob_match >= 1.0:
        out.append("date of birth matches exactly")
    elif feats.dob_match >= 0.6:
        out.append("birth year matches")
    elif feats.dob_match < 0:
        out.append("date of birth does NOT match — likely a different person")
    if feats.country_match is CountryMatch.MATCH:
        out.append("payment country matches the sanctioned entity's country")
    elif feats.country_match is CountryMatch.MISMATCH:
        out.append("payment country differs from the entity's country")
    if not feats.schema_compatible:
        out.append("matched entity type is unusual for a name payment")
    if entity.programs:
        prog = _short(entity.programs[0], 90)
        out.append(f"listed under sanctions program: {prog}")
    return out


def _short(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n].rstrip() + "…"


def _build_response(req: ScreenRequest, res: ScreeningResult,
                    scr: SanctionsScreener) -> ScreenResponse:
    matched = None
    feats = None
    if res.entity_id and res.channel is Channel.FIAT:
        entity = scr.index.entity_by_id.get(res.entity_id)
        if entity is not None:
            matched = MatchedEntity(
                entity_id=entity.id, name=entity.name, type=entity.schema_.value,
                programs=[_short(p, 120) for p in entity.programs[:3]],
                countries=entity.countries)
            # recompute features WITH the payment's secondary identifiers so the
            # explanation reflects the DOB/ID signals that actually drove the verdict
            ids = [i for i in (req.passport, req.national_id) if i]
            feats, _raw, _nm = build_features(req.name or "", req.country, entity,
                                              scr.index, query_dob=req.dob, query_ids=ids)
    elif res.entity_id and res.channel is Channel.CRYPTO:
        matched = MatchedEntity(entity_id=res.entity_id, name=res.matched_name or "",
                                type="CryptoWallet")

    # thresholds shown are the RISK-ADJUSTED ones the decision actually used
    eff_high, eff_low = risk_layer.adjust_thresholds(scr.tau_high, scr.tau_low, res.risk_score)
    tau = {"review": round(eff_low, 3), "block": round(eff_high, 3)}
    p = res.probability
    if res.verdict is VerdictType.MATCH:
        decision = f"probability {p:.2f} ≥ block threshold {tau['block']:.2f} → auto-block"
        summary = (f"BLOCK — '{res.query}' matches sanctioned entity "
                   f"'{res.matched_name}' with high confidence.")
    elif res.verdict is VerdictType.REVIEW:
        decision = (f"probability {p:.2f} is in the review band "
                    f"[{tau['review']:.2f}, {tau['block']:.2f}) → human review")
        summary = (f"REVIEW — '{res.query}' is a plausible but uncertain match to "
                   f"'{res.matched_name}'. A human should confirm using secondary "
                   f"identifiers (DOB / passport / national ID) or other records.")
    else:
        decision = f"probability {p:.2f} < review threshold {tau['review']:.2f} → release"
        summary = f"NO MATCH — '{res.query}' has no sufficiently strong sanctions match."

    signals = _signals(feats, scr.index.entity_by_id[res.entity_id]) if (feats and res.entity_id) \
        else (res.reasons or ["no candidate matches surfaced"])
    if res.risk_score >= 0.5:
        signals.append(f"elevated payment risk ({res.risk_score:.2f}) lowered the threshold")

    # structured audit trail — one JSON event per verdict
    log_event("screen", txn_id=req.txn_id, channel=res.channel.value,
              query=res.query, verdict=res.verdict.value, probability=round(p, 4),
              entity_id=res.entity_id, matched_name=res.matched_name,
              risk_score=res.risk_score, model=res.model_name,
              latency_ms=round(res.latency_ms, 3))

    return ScreenResponse(
        txn_id=req.txn_id, verdict=res.verdict, probability=round(p, 4),
        channel=res.channel, query=res.query, model_name=res.model_name,
        risk_score=res.risk_score, matched_entity=matched,
        explanation=Explanation(summary=summary, decision=decision,
                                thresholds=tau, risk_score=res.risk_score, signals=signals),
        latency_ms=round(res.latency_ms, 3),
    )


# ----------------------------------------------------------------- endpoints
@app.get("/health")
def health():
    scr = screener()
    return {
        "status": "ok",
        "model": scr.model_name,
        "thresholds": {"review": scr.tau_low, "block": scr.tau_high},
        "entities": scr.index.n_entities,
        "name_variants": scr.index.n_variants,
        "wallets": len(scr.index.wallets),
    }


@app.post("/screen", response_model=ScreenResponse)
def screen(req: ScreenRequest) -> ScreenResponse:
    """Screen a single payment and return an explained verdict."""
    scr = screener()
    res = scr.screen(req.to_payment())
    return _build_response(req, res, scr)


@app.post("/screen/batch", response_model=list[ScreenResponse])
def screen_batch(reqs: list[ScreenRequest]) -> list[ScreenResponse]:
    """Screen many payments (e.g. a review-queue refresh) in one call."""
    scr = screener()
    return [_build_response(req, scr.screen(req.to_payment()), scr) for req in reqs]
