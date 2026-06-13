"""SanctionsScreener — the S0-S4 orchestrator.

    S0  exact name / wallet      -> instant MATCH
    S1  recall candidates        (phonetic+token blocking, index.recall)
    S2  build_features per cand   (matching.build_features)
    S3  calibrated probability    (Stage-3 model; fuzzy fallback if no model loaded)
    S4  thresholds -> verdict + human-readable reasons

The screener is stateless given its (read-only) index + model, so many instances
can run in parallel across processes.
"""
from __future__ import annotations
import time
from typing import Optional
import numpy as np

from ..config import Settings, settings as default_settings
from ..indexing.index import SanctionsIndex
from ..matching.scoring import build_features
from ..model.base import LoadedModel, load_model
from ..normalization import norm, tokens
from ..domain.models import PaymentInstruction, ScreeningResult, MatchFeatures
from ..domain.enums import VerdictType, Channel, CountryMatch

# fallback thresholds (no model) operate on raw_fuzzy_score/100, matching the prototype
_FALLBACK_TAU_HIGH = 0.92
_FALLBACK_TAU_LOW = 0.80


class SanctionsScreener:
    def __init__(self, index: SanctionsIndex, model: Optional[LoadedModel] = None,
                 settings: Settings = default_settings):
        """Wire up the index, optional model, and resolved decision thresholds."""
        self.index = index
        self.model = model
        self.settings = settings
        if model is not None:
            self.tau_high, self.tau_low = model.tau_high, model.tau_low
            self.model_name = model.model_name
        else:
            self.tau_high, self.tau_low = _FALLBACK_TAU_HIGH, _FALLBACK_TAU_LOW
            self.model_name = "fuzzy-fallback"

    # ---- factory -------------------------------------------------------
    @classmethod
    def load(cls, settings: Settings = default_settings) -> "SanctionsScreener":
        """Convenience factory: build index from parquet, load model if the joblib exists."""
        index = SanctionsIndex.from_parquet(settings.sanctions_parquet)
        model = load_model(settings.model_path) if settings.model_path.exists() else None
        return cls(index, model, settings)

    # ---- crypto --------------------------------------------------------
    def screen_wallet(self, address: str) -> ScreeningResult:
        """S0 crypto path: O(1) exact wallet-address lookup against the sanctions set."""
        t0 = time.perf_counter()
        eid = self.index.wallet_entity(address)
        if eid:
            return ScreeningResult(
                verdict=VerdictType.MATCH, probability=1.0, raw_fuzzy_score=100.0,
                query=address, channel=Channel.CRYPTO, entity_id=eid,
                matched_name=address, reasons=["exact sanctioned wallet address"],
                model_name=self.model_name,
                latency_ms=(time.perf_counter() - t0) * 1000)
        return ScreeningResult(
            verdict=VerdictType.NO_MATCH, probability=0.0, raw_fuzzy_score=0.0,
            query=address, channel=Channel.CRYPTO,
            reasons=["no direct wallet hit (graph-hop tracing is a future stage)"],
            model_name=self.model_name, latency_ms=(time.perf_counter() - t0) * 1000)

    # ---- fiat name -----------------------------------------------------
    def screen_name(self, name: str, country: str = "") -> ScreeningResult:
        """S0–S4 fiat pipeline: exact → phonetic recall → features → model → verdict."""
        t0 = time.perf_counter()
        q = norm(name)

        def done(verdict, prob, raw, eid, matched, reasons):
            return ScreeningResult(
                verdict=verdict, probability=round(float(prob), 4),
                raw_fuzzy_score=round(float(raw), 1), query=name, channel=Channel.FIAT,
                entity_id=eid, matched_name=matched, reasons=reasons,
                model_name=self.model_name, latency_ms=(time.perf_counter() - t0) * 1000)

        # S0 exact — auto-block only when the matched name is DISTINCTIVE (rare
        # tokens). A common exact name ("Mohammed Ali", "Kim") is too ambiguous to
        # auto-block and falls through to the model, which can route it to REVIEW.
        eid = self.index.exact_entity(q)
        qt = tokens(q)
        if eid and qt:
            rarity = sum(self.index.idf_of(t) for t in qt) / len(qt) / self.index.default_idf
            if rarity >= 0.6:
                return done(VerdictType.MATCH, 1.0, 100.0, eid,
                            self.index.entity_by_id[eid].name,
                            ["exact match on a distinctive name"])

        # S1 recall
        cand_ids = self.index.recall(q, self.settings.max_candidates)
        if not cand_ids:
            return done(VerdictType.NO_MATCH, 0.0, 0.0, None, None,
                        ["no phonetic candidates"])

        # S2 features for every candidate
        feats: list[MatchFeatures] = []
        raws: list[float] = []
        names: list[str] = []
        for cid in cand_ids:
            f, raw, matched = build_features(name, country, self.index.entity_by_id[cid], self.index)
            feats.append(f); raws.append(raw); names.append(matched)

        # S3 score -> pick best candidate
        if self.model is not None:
            probs = self.model.predict_proba(np.asarray([f.to_vector() for f in feats], dtype=float))
            best = int(np.argmax(probs))
            prob = float(probs[best])
        else:
            best = int(np.argmax(raws))
            prob = raws[best] / 100.0

        bid = cand_ids[best]
        bf = feats[best]
        # S4 decision
        if prob >= self.tau_high:
            verdict = VerdictType.MATCH
        elif prob >= self.tau_low:
            verdict = VerdictType.REVIEW
        else:
            verdict = VerdictType.NO_MATCH

        reasons = self._reasons(bf, prob, raws[best])
        eid_out = bid if verdict is not VerdictType.NO_MATCH else None
        matched_out = names[best] if verdict is not VerdictType.NO_MATCH else None
        return done(verdict, prob, raws[best], eid_out, matched_out, reasons)

    # ---- unified entry -------------------------------------------------
    def screen(self, payment: PaymentInstruction) -> ScreeningResult:
        """Dispatch to screen_wallet or screen_name based on payment channel."""
        if payment.channel is Channel.CRYPTO:
            return self.screen_wallet(payment.wallet)
        return self.screen_name(payment.bene_name, payment.bene_country)

    # ---- explanation ---------------------------------------------------
    @staticmethod
    def _reasons(f: MatchFeatures, prob: float, raw: float) -> list[str]:
        """Build human-readable explanation strings for an analyst reviewing the verdict."""
        r = [f"calibrated match probability {prob:.2f}",
             f"name similarity {f.token_sort:.0f}/100 (jaro-winkler {f.jaro_winkler:.0f})"]
        if f.rare_token_overlap >= 0.5:
            r.append(f"shares rare/distinctive tokens ({f.rare_token_overlap:.2f} IDF overlap)")
        elif f.rare_token_overlap < 0.25:
            r.append("only common tokens overlap (weak signal)")
        if f.country_match is CountryMatch.MATCH:
            r.append("payment country matches entity")
        elif f.country_match is CountryMatch.MISMATCH:
            r.append("payment country differs from entity")
        if not f.schema_compatible:
            r.append("entity type unusual for a name payment")
        return r
