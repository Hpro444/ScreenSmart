"""Feature-vector models — intermediate representation between fuzzy matching and the classifier."""
from __future__ import annotations
from typing import ClassVar
from pydantic import BaseModel, Field

from .enums import EntitySchema, CountryMatch


class MatchFeatures(BaseModel):
    """Feature vector for one (payment, candidate-entity) pair.

    INVARIANT: every field is computable at inference time from the payment and
    the candidate alone — no DOB or other signal absent from a live payment — so
    there is zero train/serve skew. `to_vector()` and `FEATURE_NAMES` define the
    canonical ordering the model consumes.
    """
    token_sort: float            # rapidfuzz token_sort_ratio (0-100)
    token_set: float             # rapidfuzz token_set_ratio
    wratio: float                # rapidfuzz WRatio
    jaro_winkler: float          # best whole-string Jaro-Winkler (0-100)
    phonetic_agreement: float    # share of query tokens with a phonetic match (0-1)
    token_coverage_q: float      # share of query tokens present in candidate (0-1)
    rare_token_overlap: float    # IDF-weighted shared-token mass (0-1)
    query_rarity: float          # mean ABSOLUTE rarity of the query's tokens (0-1)
    len_ratio: float             # min/max of token counts (0-1)
    n_query_tokens: int
    n_cand_tokens: int
    country_match: CountryMatch
    is_person: bool
    schema_compatible: bool      # payment-vs-entity type plausibility
    matched_is_primary: bool     # best variant was the primary name (vs an alias)
    # Secondary-identity corroboration. These are COMPUTED for every pair and used by
    # the screener's deterministic rules (exact-ID short-circuit, DOB-mismatch demotion)
    # and in the explanation — but they are intentionally NOT model features: most
    # payments carry no identity, so feeding mostly-zero columns to the classifier only
    # diluted its name judgement and cost aggregate precision. Rules handle them better.
    dob_match: float             # +1 exact DOB, +0.6 year-only, 0 unknown, -1 mismatch
    id_match: float              # +1 a passport/national-id exactly matches the entity, else 0

    FEATURE_NAMES: ClassVar[tuple[str, ...]] = (
        "token_sort", "token_set", "wratio", "jaro_winkler",
        "phonetic_agreement", "token_coverage_q", "rare_token_overlap", "query_rarity",
        "len_ratio", "n_query_tokens", "n_cand_tokens",
        "country_match_code", "is_person", "schema_compatible", "matched_is_primary",
    )

    def to_vector(self) -> list[float]:
        """Serialise to the ordered float list the Stage-3 model consumes (name-based;
        DOB/ID are applied as rules in the screener, not as model inputs)."""
        return [
            self.token_sort, self.token_set, self.wratio, self.jaro_winkler,
            self.phonetic_agreement, self.token_coverage_q, self.rare_token_overlap,
            self.query_rarity, self.len_ratio,
            float(self.n_query_tokens), float(self.n_cand_tokens),
            self.country_match.as_code(), float(self.is_person),
            float(self.schema_compatible), float(self.matched_is_primary),
        ]


class MatchCandidate(BaseModel):
    """A candidate entity surfaced for a payment, with its feature vector."""
    entity_id: str
    matched_name: str
    schema_: EntitySchema = Field(alias="schema")
    features: MatchFeatures
    raw_fuzzy_score: float       # blended fuzzy score, for the pre-model fallback
