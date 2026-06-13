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
from .domain.models import ScreeningResult, SanctionedEntity, MatchFeatures

# loaded once at startup (index build + model load is ~5s; never per-request)
SCREENER: Optional[SanctionsScreener] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global SCREENER
    SCREENER = SanctionsScreener.load(settings)
    yield
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

    @model_validator(mode="after")
    def _need_one(self) -> "ScreenRequest":
        if not self.name and not self.wallet:
            raise ValueError("provide either 'name' (fiat) or 'wallet' (crypto)")
        return self


class MatchedEntity(BaseModel):
    entity_id: str
    name: str
    type: str
    programs: list[str] = []
    countries: list[str] = []


class Explanation(BaseModel):
    summary: str                       # one-line, human-readable verdict rationale
    decision: str                      # where the probability sits vs the thresholds
    thresholds: dict[str, float]       # {"review": tau_low, "block": tau_high}
    signals: list[str]                 # the individual reasons that drove the score


class ScreenResponse(BaseModel):
    txn_id: Optional[str]
    verdict: VerdictType
    probability: float
    channel: Channel
    query: str
    model_name: str
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
            feats, _raw, _nm = build_features(req.name or "", req.country, entity, scr.index)
    elif res.entity_id and res.channel is Channel.CRYPTO:
        matched = MatchedEntity(entity_id=res.entity_id, name=res.matched_name or "",
                                type="CryptoWallet")

    tau = {"review": round(scr.tau_low, 3), "block": round(scr.tau_high, 3)}
    p = res.probability
    if res.verdict is VerdictType.MATCH:
        decision = f"probability {p:.2f} ≥ block threshold {tau['block']:.2f} → auto-block"
        summary = (f"BLOCK — '{res.query}' matches sanctioned entity "
                   f"'{res.matched_name}' with high confidence.")
    elif res.verdict is VerdictType.REVIEW:
        decision = (f"probability {p:.2f} is in the review band "
                    f"[{tau['review']:.2f}, {tau['block']:.2f}) → human review")
        summary = (f"REVIEW — '{res.query}' is a plausible but uncertain match to "
                   f"'{res.matched_name}'. A human must confirm using secondary data "
                   f"(DOB / ID), which a name+country payment does not carry.")
    else:
        decision = f"probability {p:.2f} < review threshold {tau['review']:.2f} → release"
        summary = f"NO MATCH — '{res.query}' has no sufficiently strong sanctions match."

    signals = _signals(feats, scr.index.entity_by_id[res.entity_id]) if (feats and res.entity_id) \
        else (res.reasons or ["no candidate matches surfaced"])

    return ScreenResponse(
        txn_id=req.txn_id, verdict=res.verdict, probability=round(p, 4),
        channel=res.channel, query=res.query, model_name=res.model_name,
        matched_entity=matched,
        explanation=Explanation(summary=summary, decision=decision,
                                thresholds=tau, signals=signals),
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
    if req.wallet:
        res = scr.screen_wallet(req.wallet)
    else:
        res = scr.screen_name(req.name, req.country)
    return _build_response(req, res, scr)


@app.post("/screen/batch", response_model=list[ScreenResponse])
def screen_batch(reqs: list[ScreenRequest]) -> list[ScreenResponse]:
    """Screen many payments (e.g. a review-queue refresh) in one call."""
    scr = screener()
    out = []
    for req in reqs:
        res = scr.screen_wallet(req.wallet) if req.wallet else scr.screen_name(req.name, req.country)
        out.append(_build_response(req, res, scr))
    return out
