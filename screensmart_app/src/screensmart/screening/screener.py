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
from .. import risk as risk_layer

# fallback thresholds (no model) operate on raw_fuzzy_score/100, matching the prototype
_FALLBACK_TAU_HIGH = 0.92
_FALLBACK_TAU_LOW = 0.80


class SanctionsScreener:
    def __init__(self, index: SanctionsIndex, model: Optional[LoadedModel] = None,
                 settings: Settings = default_settings, engine=None):
        """Wire up the index, optional model, resolved thresholds, and (DB mode) the
        Postgres engine used to consult the crypto exposure index."""
        self.index = index
        self.model = model
        self.settings = settings
        self._engine = engine
        if model is not None:
            self.tau_high, self.tau_low = model.tau_high, model.tau_low
            self.model_name = model.model_name
        else:
            self.tau_high, self.tau_low = _FALLBACK_TAU_HIGH, _FALLBACK_TAU_LOW
            self.model_name = "fuzzy-fallback"

    # ---- factory -------------------------------------------------------
    @classmethod
    def load(cls, settings: Settings = default_settings) -> "SanctionsScreener":
        """Build the index from the configured source (parquet snapshot or live Postgres),
        load the model if present, and keep the DB engine for crypto exposure lookups."""
        engine = None
        if settings.sanctions_source == "db":
            from .. import db
            engine = db.get_engine(settings.database_url or db.DEFAULT_DB_URL)
            index = SanctionsIndex.from_db(engine, settings.opensanctions_dataset)
        else:
            index = SanctionsIndex.from_parquet(settings.sanctions_parquet)
        model = load_model(settings.model_path) if settings.model_path.exists() else None
        return cls(index, model, settings, engine=engine)

    # ---- crypto --------------------------------------------------------
    def screen_wallet(self, address: str) -> ScreeningResult:
        """Crypto path: (S0) exact sanctioned-wallet hit → MATCH; else (DB mode) consult the
        precomputed graph-hop exposure index → MATCH (direct) / REVIEW (exposed) / NO_MATCH."""
        t0 = time.perf_counter()

        def done(verdict, prob, eid, matched, reasons):
            return ScreeningResult(
                verdict=verdict, probability=round(float(prob), 4), raw_fuzzy_score=0.0,
                query=address, channel=Channel.CRYPTO, entity_id=eid, matched_name=matched,
                reasons=reasons, model_name=self.model_name,
                latency_ms=(time.perf_counter() - t0) * 1000)

        eid = self.index.wallet_entity(address)
        if eid:
            return done(VerdictType.MATCH, 1.0, eid, address, ["exact sanctioned wallet address"])

        # crypto graph-hop exposure (precomputed by the exposure_graph service)
        if self._engine is not None and self.settings.use_crypto_exposure:
            from .. import db
            exp = db.lookup_exposure(self._engine, address)
            if exp:
                score, depth = exp["exposure_score"], exp["best_depth"]
                src = exp["source_risk_node"]
                reasons = [exp["reason"] or "crypto graph-hop exposure",
                           f"exposure {score:.2f} at {depth} hop(s) from sanctioned node {src}"]
                if depth == 0:
                    return done(VerdictType.MATCH, max(score, 1.0), src, src, reasons)
                if score >= self.settings.exposure_review_threshold:
                    return done(VerdictType.REVIEW, score, src, src, reasons)
                return done(VerdictType.NO_MATCH, score, None, None, reasons)

        return done(VerdictType.NO_MATCH, 0.0, None, None,
                    ["no direct wallet hit; no graph-hop exposure"])

    # ---- fiat name -----------------------------------------------------
    def screen_name(self, name: str, country: str = "", *,
                    dob: Optional[str] = None, ids: Optional[list[str]] = None,
                    risk: float = 0.0) -> ScreeningResult:
        """S0–S4 fiat pipeline: exact-ID → exact-name → recall → features → model → verdict.

        `dob`/`ids` are optional secondary identifiers; `risk` (0-1) is the payment-context
        risk that LOWERS the decision thresholds for risky payments.
        """
        t0 = time.perf_counter()
        q = norm(name)
        ids = ids or []
        # risk lowers the bar to flag/block (see risk.py)
        tau_high, tau_low = risk_layer.adjust_thresholds(self.tau_high, self.tau_low, risk)

        def done(verdict, prob, raw, eid, matched, reasons):
            return ScreeningResult(
                verdict=verdict, probability=round(float(prob), 4),
                raw_fuzzy_score=round(float(raw), 1), query=name, channel=Channel.FIAT,
                entity_id=eid, matched_name=matched, reasons=reasons,
                model_name=self.model_name, risk_score=round(risk, 3),
                latency_ms=(time.perf_counter() - t0) * 1000)

        # S0a exact IDENTITY hit — a passport/national-id that matches a sanctioned
        # entity is near-definitive, regardless of how the name was spelt.
        for pid in ids:
            id_eid = self.index.id_entity(pid)
            if id_eid:
                return done(VerdictType.MATCH, 1.0, 100.0, id_eid,
                            self.index.entity_by_id[id_eid].name,
                            ["exact match on a sanctioned identity number (passport/national ID)"])

        # S0b exact NAME — auto-block only when the name is DISTINCTIVE (rare tokens);
        # a common exact name ("Mohammed Ali", "Kim") falls through to the model.
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

        # S2 features for every candidate (with the secondary identifiers)
        feats: list[MatchFeatures] = []
        raws: list[float] = []
        names: list[str] = []
        for cid in cand_ids:
            f, raw, matched = build_features(
                name, country, self.index.entity_by_id[cid], self.index,
                query_dob=dob, query_ids=ids)
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
        # S4 decision against the (risk-adjusted) thresholds
        if prob >= tau_high:
            verdict = VerdictType.MATCH
        elif prob >= tau_low:
            verdict = VerdictType.REVIEW
        else:
            verdict = VerdictType.NO_MATCH

        # S4b identity RULES on the chosen candidate (DOB is a rule, not a model feature):
        #   exact DOB corroborates a borderline match -> promote REVIEW to MATCH;
        #   a DOB MISMATCH means a different person -> never auto-block, demote to REVIEW.
        if bf.dob_match >= 1.0 and verdict is VerdictType.REVIEW:
            verdict = VerdictType.MATCH
        elif bf.dob_match < 0 and verdict is VerdictType.MATCH:
            verdict = VerdictType.REVIEW

        reasons = self._reasons(bf, prob, risk)
        eid_out = bid if verdict is not VerdictType.NO_MATCH else None
        matched_out = names[best] if verdict is not VerdictType.NO_MATCH else None
        return done(verdict, prob, raws[best], eid_out, matched_out, reasons)

    # ---- unified entry -------------------------------------------------
    def screen(self, payment: PaymentInstruction) -> ScreeningResult:
        """Dispatch to crypto/fiat, deriving secondary identifiers + payment risk."""
        if payment.channel is Channel.CRYPTO:
            return self.screen_wallet(payment.wallet)
        risk, _factors = risk_layer.payment_risk(
            amount=payment.amount, currency=payment.currency,
            rail=payment.rail, orig_country=payment.orig_country)
        return self.screen_name(payment.bene_name, payment.bene_country,
                                dob=payment.bene_dob, ids=payment.identifiers, risk=risk)

    # ---- explanation ---------------------------------------------------
    @staticmethod
    def _reasons(f: MatchFeatures, prob: float, risk: float) -> list[str]:
        """Build human-readable explanation strings for an analyst reviewing the verdict."""
        r = [f"calibrated match probability {prob:.2f}",
             f"name similarity {f.token_sort:.0f}/100 (jaro-winkler {f.jaro_winkler:.0f})"]
        if f.rare_token_overlap >= 0.5:
            r.append(f"shares rare/distinctive tokens ({f.rare_token_overlap:.2f} IDF overlap)")
        elif f.rare_token_overlap < 0.25:
            r.append("only common tokens overlap (weak signal)")
        # secondary-identity corroboration
        if f.id_match >= 1.0:
            r.append("passport/national-ID matches the sanctioned entity")
        if f.dob_match >= 1.0:
            r.append("date of birth matches exactly")
        elif f.dob_match >= 0.6:
            r.append("birth year matches")
        elif f.dob_match < 0:
            r.append("date of birth does NOT match (likely a different person)")
        if f.country_match is CountryMatch.MATCH:
            r.append("payment country matches entity")
        elif f.country_match is CountryMatch.MISMATCH:
            r.append("payment country differs from entity")
        if not f.schema_compatible:
            r.append("entity type unusual for a name payment")
        if risk >= 0.5:
            r.append(f"elevated payment risk ({risk:.2f}) lowered the decision threshold")
        return r
