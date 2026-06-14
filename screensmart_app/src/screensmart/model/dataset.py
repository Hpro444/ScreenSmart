"""Manufacture labelled training pairs from the sanctions list itself.

We have no labelled production data, so we synthesise it (the standard approach):
  positives      : an entity vs its own aliases / degraded spellings  (label 1)
  hard negatives : a name vs a DIFFERENT entity that recall surfaces   (label 0)
                   -> the "two different Mohammeds / John Smith vs John L. Smith" trap
  easy negatives : a random clean name vs whatever recall surfaces     (label 0)

The features are computed with the exact same code path used at serve time
(matching.build_features), so there is no train/serve skew.
"""
from __future__ import annotations
import random
import numpy as np

from ..indexing.index import SanctionsIndex
from ..matching.scoring import build_features
from ..normalization import norm
from ..synthesis import degrade, random_clean_name, random_dob, COMMON_BAIT
from ..domain.enums import EntitySchema

_COUNTRY_POOL = ["us", "gb", "de", "fr", "ng", "in", "br", "jp", "ae", "sg", "za", "mx"]


def _country_for_positive(entity, rng: random.Random) -> str:
    """Country for a POSITIVE pair, deliberately decorrelated from the label.

    Real payments to a sanctioned party often route through a third country, so a
    country mismatch must NOT veto a strong name match. We give positives matching,
    mismatching and unknown countries in roughly equal measure so the model treats
    country as a weak corroborator, not a hard gate.
    """
    r = rng.random()
    if entity.countries and r < 0.45:
        return entity.countries[0]          # match
    if r < 0.85:
        return rng.choice(_COUNTRY_POOL)     # usually a mismatch
    return ""                                # unknown


def build_training_pairs(index: SanctionsIndex, *, seed: int = 42,
                         max_entities: int = 15000,
                         train_ids: set[str] | None = None,
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Return (X feature matrix, y labels). If `train_ids` is given, positives are drawn
    ONLY from those entities (the rest are held out for an entity-disjoint test set)."""
    rng = random.Random(seed)
    rows: list[list[float]] = []
    labels: list[int] = []

    # focus positives on the entity types a fiat name-payment actually targets
    pool = [e for e in index.entities
            if e.schema_ in (EntitySchema.PERSON, EntitySchema.ORGANIZATION,
                             EntitySchema.LEGAL_ENTITY, EntitySchema.COMPANY)
            and (train_ids is None or e.id in train_ids)]
    rng.shuffle(pool)
    pool = pool[:max_entities]

    for e in pool:
        pos_country = _country_for_positive(e, rng)
        # secondary identifiers attached to the TRUE owner's payments (sometimes) —
        # teaches the model that a DOB/ID hit is strong evidence FOR a match.
        p_dob = e.dob if (e.dob and rng.random() < 0.45) else None
        p_ids = [rng.choice(e.identifiers)] if (e.identifiers and rng.random() < 0.25) else None

        # --- positive 1: an alias resolves to its own entity ---
        if e.aliases:
            alias = rng.choice(e.aliases)
            feats, _, _ = build_features(alias, pos_country, e, index, query_dob=p_dob, query_ids=p_ids)
            rows.append(feats.to_vector()); labels.append(1)

        # --- positive 2: a degraded spelling of a name ---
        base = rng.choice(e.all_names)
        dname, _ = degrade(base, rng)
        feats, _, _ = build_features(dname, pos_country, e, index, query_dob=p_dob, query_ids=p_ids)
        rows.append(feats.to_vector()); labels.append(1)

        # --- hard negative: same query name, a DIFFERENT entity recall surfaces. Attach
        #     the real owner's DOB so it MISMATCHES the other entity — teaches the model
        #     that a name collision with a DOB mismatch is NOT a match (the FP killer). ---
        neg_country = rng.choice(_COUNTRY_POOL)
        neg_dob = (e.dob or random_dob(rng)) if rng.random() < 0.5 else None
        for cid in index.recall(norm(dname), max_candidates=8):
            if cid != e.id:
                other = index.entity_by_id[cid]
                feats, _, _ = build_features(dname, neg_country, other, index, query_dob=neg_dob)
                rows.append(feats.to_vector()); labels.append(0)
                break

    # --- FALSE-POSITIVE bait negatives: common names (Kim, Mohammed, John Smith)
    #     vs every sanctioned entity they collide with on a COMMON token. These are
    #     the over-blocking trap; labelling them 0 teaches the model that a high
    #     fuzzy score with LOW rare-token overlap is not a real match. ---
    bait_rounds = max(1, len(pool) // (len(COMMON_BAIT) * 8))
    for _ in range(bait_rounds):
        for nm in COMMON_BAIT:
            b_dob = random_dob(rng) if rng.random() < 0.5 else None   # mismatching DOB -> clears
            for cid in index.recall(norm(nm), max_candidates=6):
                other = index.entity_by_id[cid]
                feats, _, _ = build_features(nm, rng.choice(_COUNTRY_POOL), other, index, query_dob=b_dob)
                rows.append(feats.to_vector()); labels.append(0)

    # --- easy negatives: random clean names vs whatever they collide with ---
    n_easy = max(1, len(rows) // 4)
    for _ in range(n_easy):
        nm = random_clean_name(rng)
        cands = index.recall(norm(nm), max_candidates=4)
        if not cands:
            continue
        other = index.entity_by_id[rng.choice(cands)]
        e_dob = random_dob(rng) if rng.random() < 0.3 else None
        feats, _, _ = build_features(nm, rng.choice(_COUNTRY_POOL), other, index, query_dob=e_dob)
        rows.append(feats.to_vector()); labels.append(0)

    X = np.asarray(rows, dtype=float)
    y = np.asarray(labels, dtype=int)
    return X, y
