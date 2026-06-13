"""Stage-2 feature extraction: turn a (query, candidate-entity) pair into MatchFeatures.

The query side is just a name + an optional country (everything a live fiat payment
carries). The candidate side is a SanctionedEntity with all its name variants. We pick
the best-matching variant and describe the pair with features the Stage-3 model scores.
"""
from __future__ import annotations
from rapidfuzz import fuzz, process
import jellyfish

from ..domain.models import SanctionedEntity, MatchFeatures
from ..domain.enums import EntitySchema, CountryMatch
from ..indexing.index import SanctionsIndex
from ..normalization import norm, tokens, phon, norm_id


def blended_score(token_sort: float, wratio: float) -> float:
    """Pre-model fallback score (matches the original prototype's blend)."""
    return 0.55 * token_sort + 0.45 * wratio


def _country_match(query_country: str, entity: SanctionedEntity) -> CountryMatch:
    q = (query_country or "").strip().lower()
    if not q or not entity.countries:
        return CountryMatch.UNKNOWN
    ecs = {c.strip().lower() for c in entity.countries}
    return CountryMatch.MATCH if q in ecs else CountryMatch.MISMATCH


def _dob_match(query_dob: str | None, entity: SanctionedEntity) -> float:
    """+1 exact date, +0.6 same year, 0 unknown, -1 mismatch (a strong discriminator
    between two people who share a name). Handles multi-valued entity DOBs like
    '1948-07-16;1948-07-26' by matching against ANY listed date."""
    if not query_dob or not entity.dob:
        return 0.0
    ent_dobs = [d.strip() for d in entity.dob.split(";") if d.strip()]
    if query_dob in ent_dobs:
        return 1.0
    if any(query_dob[:4] == d[:4] for d in ent_dobs):
        return 0.6
    return -1.0


def _id_match(query_ids: list[str] | None, entity: SanctionedEntity) -> float:
    """+1 if any payment identifier exactly matches one of the entity's IDs — near-definitive."""
    if not query_ids or not entity.identifiers:
        return 0.0
    ent_ids = {norm_id(i) for i in entity.identifiers if i}
    return 1.0 if any(norm_id(q) in ent_ids for q in query_ids if q) else 0.0


def build_features(query_name: str, query_country: str,
                   entity: SanctionedEntity, index: SanctionsIndex,
                   query_dob: str | None = None,
                   query_ids: list[str] | None = None,
                   ) -> tuple[MatchFeatures, float, str]:
    """Return (features, raw_fuzzy_score, best_matched_raw_name).

    `query_dob` / `query_ids` are optional secondary identifiers from the payment; when
    absent the identity features are 0 (no signal) and the model relies on the name.
    """
    q = norm(query_name)
    qtok = tokens(q)
    qtok_set = set(qtok)
    qphon = {phon(t) for t in qtok_set}
    dob_match = _dob_match(query_dob, entity)
    id_match = _id_match(query_ids, entity)

    variants = index.entity_variants.get(entity.id, [])
    # Pick the best-matching variant with one C-level call (rapidfuzz process),
    # instead of a Python loop over every alias — entities can have 200+ aliases.
    best = None
    if variants:
        choices = [v.variant_norm for v in variants]
        hit = process.extractOne(q, choices, scorer=fuzz.WRatio)
        if hit is not None:
            best = variants[hit[2]]
            best_wr = float(hit[1])

    if best is not None:
        best_ts = fuzz.token_sort_ratio(q, best.variant_norm)
        best_set = fuzz.token_set_ratio(q, best.variant_norm)
        best_jw = jellyfish.jaro_winkler_similarity(q, best.variant_norm) * 100.0
        best_raw = blended_score(best_ts, best_wr)

    # absolute rarity of the query itself (low for "Kim"/"Mohammed", high for
    # "Hizballah") — lets the model distinguish a common name from a distinctive one
    # even when the candidate matches it exactly.
    query_rarity = (sum(index.idf_of(t) for t in qtok_set) / len(qtok_set)
                    / index.default_idf) if qtok_set else 0.0

    if best is None:                       # entity had no usable name (defensive)
        feats = MatchFeatures(
            token_sort=0, token_set=0, wratio=0, jaro_winkler=0,
            phonetic_agreement=0, token_coverage_q=0, rare_token_overlap=0,
            query_rarity=query_rarity,
            len_ratio=0, n_query_tokens=len(qtok), n_cand_tokens=0,
            country_match=_country_match(query_country, entity),
            is_person=entity.schema_.is_person, schema_compatible=False,
            matched_is_primary=False, dob_match=dob_match, id_match=id_match,
        )
        return feats, 0.0, entity.name

    ctok = set(tokens(best.variant_norm))
    cphon = {phon(t) for t in ctok}

    # phonetic agreement & exact token coverage on the query side
    phon_hit = len(qphon & cphon)
    phonetic_agreement = phon_hit / len(qphon) if qphon else 0.0
    token_coverage_q = len(qtok_set & ctok) / len(qtok_set) if qtok_set else 0.0

    # IDF-weighted shared-token mass, matched FUZZILY so a mistyped distinctive
    # token still counts (khaddouur ~ khaddour). Matching a RARE token (Qadhafi)
    # counts far more than a common one (Mohammed) — the core anti-false-positive
    # signal, and it must survive transliteration/typos.
    q_idf = sum(index.idf_of(t) for t in qtok_set) or 1.0
    ctok_list = list(ctok)
    matched_idf = 0.0
    for qt in qtok_set:
        sim = max((jellyfish.jaro_winkler_similarity(qt, ct) for ct in ctok_list),
                  default=0.0)
        if sim >= 0.85:
            matched_idf += index.idf_of(qt) * sim
    rare_token_overlap = matched_idf / q_idf

    n_q, n_c = len(qtok), len(ctok)
    len_ratio = (min(n_q, n_c) / max(n_q, n_c)) if max(n_q, n_c) else 0.0

    schema_compatible = entity.schema_ in (
        EntitySchema.PERSON, EntitySchema.ORGANIZATION,
        EntitySchema.LEGAL_ENTITY, EntitySchema.COMPANY,
    )

    feats = MatchFeatures(
        token_sort=best_ts, token_set=best_set, wratio=best_wr, jaro_winkler=best_jw,
        phonetic_agreement=phonetic_agreement, token_coverage_q=token_coverage_q,
        rare_token_overlap=rare_token_overlap, query_rarity=query_rarity,
        len_ratio=len_ratio, n_query_tokens=n_q, n_cand_tokens=n_c,
        country_match=_country_match(query_country, entity),
        is_person=entity.schema_.is_person, schema_compatible=schema_compatible,
        matched_is_primary=best.is_primary, dob_match=dob_match, id_match=id_match,
    )
    return feats, best_raw, best.variant_raw
