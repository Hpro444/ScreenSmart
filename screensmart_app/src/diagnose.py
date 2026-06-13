"""Diagnostic: show how the model scores each transaction SCENARIO.

Prints, per scenario, the distribution of the best-candidate calibrated probability,
plus a few concrete examples with their feature vectors. Tells us whether the model
DISCRIMINATES true matches from false-positive bait (a ranking problem) or whether it
discriminates fine and only the thresholds are wrong.
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

from screensmart.config import settings
from screensmart.indexing.index import SanctionsIndex
from screensmart.screening.screener import SanctionsScreener
from screensmart.matching.scoring import build_features
from screensmart.domain.enums import Channel


def main():
    idx = SanctionsIndex.from_parquet(settings.sanctions_parquet)
    scr = SanctionsScreener.load(settings)
    print(f"model = {scr.model_name}  tau {scr.tau_low}/{scr.tau_high}\n")

    tx = pd.read_parquet(settings.transactions_parquet)
    # keep all rare (sanctioned) scenarios, sample the common ones, for speed
    rare = tx[~tx["scenario"].isin(["clean"])]
    clean = tx[tx["scenario"] == "clean"].sample(1500, random_state=0)
    tx = pd.concat([rare, clean]).reset_index(drop=True)
    rows = []
    for _, r in tx.iterrows():
        if r["channel"] == Channel.CRYPTO.value:
            res = scr.screen_wallet(r["wallet"])
        else:
            res = scr.screen_name(r["bene_name"], r["bene_country"])
        rows.append((r["scenario"], res.probability, res.verdict.value))
    d = pd.DataFrame(rows, columns=["scenario", "prob", "verdict"])

    print("== best-candidate probability by scenario ==")
    summary = d.groupby("scenario")["prob"].describe(
        percentiles=[0.5, 0.9])[["count", "mean", "50%", "90%", "max"]]
    print(summary.round(3).to_string())

    print("\n== verdict mix by scenario ==")
    print(pd.crosstab(d["scenario"], d["verdict"]).to_string())

    # concrete fiat examples: a true match vs a bait, with full feature vectors
    print("\n== example feature vectors ==")
    from screensmart.domain.features import MatchFeatures
    names = MatchFeatures.FEATURE_NAMES
    for scen in ["sanctioned_typo", "sanctioned_reorder", "fp_bait", "clean"]:
        sub = tx[(tx["scenario"] == scen) & (tx["channel"] == "fiat")].head(2)
        for _, r in sub.iterrows():
            q = r["bene_name"]
            cand_ids = idx.recall(q, settings.max_candidates)
            if not cand_ids:
                print(f"  [{scen}] {q!r}: no candidates"); continue
            best_p, best_vec, best_name = -1, None, None
            vecs = []
            for cid in cand_ids:
                f, _raw, nm = build_features(q, r["bene_country"], idx.entity_by_id[cid], idx)
                vecs.append((f, nm))
            probs = scr.model.predict_proba(np.asarray([f.to_vector() for f, _ in vecs])) \
                if scr.model else np.array([0.0])
            bi = int(np.argmax(probs))
            f, nm = vecs[bi]
            fv = dict(zip(names, [round(x, 2) for x in f.to_vector()]))
            print(f"  [{scen}] {q!r} -> p={probs[bi]:.3f}  best={nm!r}")
            print(f"        ts={fv['token_sort']} wr={fv['wratio']} jw={fv['jaro_winkler']} "
                  f"rare_overlap={fv['rare_token_overlap']} q_rarity={fv['query_rarity']} "
                  f"cov={fv['token_coverage_q']} ctry={fv['country_match_code']}")


if __name__ == "__main__":
    main()
