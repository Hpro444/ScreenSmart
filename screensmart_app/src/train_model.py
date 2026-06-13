"""
Train, calibrate, compare and select the Stage-3 precision model.

Pipeline:
  1. build the in-RAM sanctions index
  2. manufacture labelled (positive / hard-neg / fp-bait / easy-neg) training pairs
  3. for each candidate classifier (incl. a soft-voting ensemble): fit + isotonic-calibrate
  4. **tune thresholds on a held-out slice of the LIVE transaction stream** — not on
     the balanced synthetic pairs. This is the fix for the base-rate problem: the
     synthetic set is ~50% positive, the real stream is ~2%, so thresholds learned on
     synthetic data over-block massively. We tune where the model will actually run.
  5. evaluate each on a DISJOINT test slice of the stream; select best; persist it.

Run: .venv\\Scripts\\python.exe src\\train_model.py
"""
from __future__ import annotations
import sys, json, time, datetime as dt
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_curve
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.stdout.reconfigure(encoding="utf-8")
sns.set_theme(style="whitegrid")

from screensmart.config import settings
from screensmart.indexing.index import SanctionsIndex
from screensmart.model.dataset import build_training_pairs
from screensmart.model.estimators import ALL_MODELS
from screensmart.model.base import PrecisionModel
from screensmart.screening.screener import SanctionsScreener
from screensmart.evaluation import evaluate, screen_row, _SANCTIONED

SANCTIONED_RECALL = 0.93   # tau_low aims to catch this share of sanctioned into >= REVIEW
REVIEW_BUDGET = 0.10       # ...but never send more than this share of traffic to a human


def transaction_probs(screener: SanctionsScreener, tx: pd.DataFrame
                      ) -> tuple[np.ndarray, np.ndarray]:
    """Per-transaction best-candidate prob + scenario-based 'is genuinely sanctioned'
       truth (used to tune BOTH thresholds — blocking a sanctioned party is correct
       whether we'd policy-label it MATCH or REVIEW)."""
    probs, truth_sanc = [], []
    for _, row in tx.iterrows():
        _v, p, _ms = screen_row(screener, row)
        probs.append(p)
        truth_sanc.append(1 if row["scenario"] in _SANCTIONED else 0)
    return np.asarray(probs), np.asarray(truth_sanc)


def choose_thresholds(probs: np.ndarray, truth_sanc: np.ndarray,
                      target_precision: float) -> tuple[float, float]:
    """Pick decision thresholds on the LIVE-distribution tune split.

    tau_high (auto-block): lowest cut where block precision (sanctioned vs clean)
       reaches target (=> max recall). If unreachable, the cut maximising F0.5
       (precision-weighted) — a sensible high-precision point, never the degenerate 1.0.
    tau_low (review): aims to catch SANCTIONED_RECALL of sanctioned payments into
       >= REVIEW (safety), capped by a REVIEW_BUDGET on analyst load — the MORE
       SELECTIVE of the two. If discrimination is good both are met; otherwise the
       budget binds and we report the (lower) flag-recall honestly.
    """
    prec, rec, thr = precision_recall_curve(truth_sanc, probs)
    prec, rec = prec[:-1], rec[:-1]
    if len(thr) == 0:
        return 0.9, 0.5
    ok = np.where(prec >= target_precision)[0]
    if len(ok):
        tau_high = float(thr[ok[np.argmax(rec[ok])]])
    else:
        beta2 = 0.5 ** 2
        f_beta = (1 + beta2) * prec * rec / (beta2 * prec + rec + 1e-9)
        tau_high = float(thr[np.argmax(f_beta)])

    # safety target: lowest cut catching SANCTIONED_RECALL of sanctioned payments
    sp, sr, sthr = precision_recall_curve(truth_sanc, probs)
    sr = sr[:-1]
    hi = np.where(sr >= SANCTIONED_RECALL)[0]
    tau_low_safety = float(sthr[hi[np.argmax(sthr[hi])]]) if len(hi) else 0.0
    # queue budget — TIE-ROBUST: the lowest distinct cut whose MATCH+REVIEW share <= budget.
    # (np.quantile breaks when a model piles many identical probabilities on one value, which
    #  is exactly why the tree models used to flood REVIEW to 90%.)
    tau_low_budget = _budget_threshold(probs, REVIEW_BUDGET)
    tau_low = max(tau_low_safety, tau_low_budget)   # more selective of the two
    tau_low = min(tau_low, tau_high)
    if tau_low >= tau_high:
        tau_low = tau_high * 0.5
    return round(tau_high, 4), round(tau_low, 4)


def _budget_threshold(probs: np.ndarray, budget: float) -> float:
    """Lowest distinct probability cut t such that fraction(probs >= t) <= budget.
    Tie-robust (unlike np.quantile) — guarantees the realised review rate <= budget."""
    for t in np.unique(probs):           # ascending distinct values
        if float(np.mean(probs >= t)) <= budget:
            return float(t)
    return float(np.max(probs)) + 1e-9


def main():
    settings.ensure_dirs()
    created_at = dt.datetime.now().isoformat(timespec="seconds")

    print("1) building index ...")
    index = SanctionsIndex.from_parquet(settings.sanctions_parquet)
    print(f"   {index.n_entities:,} entities / {index.n_variants:,} variants")

    print("2) manufacturing training pairs (entity-disjoint from the test stream) ...")
    from screensmart.synthesis import entity_split
    train_ids, eval_ids = entity_split([e.id for e in index.entities])
    X, y = build_training_pairs(index, seed=settings.random_seed, train_ids=train_ids)
    print(f"   {len(y):,} pairs  ({int(y.sum()):,} positive / {int((y==0).sum()):,} negative)"
          f"  | train entities={len(train_ids):,}, held-out eval entities={len(eval_ids):,}")

    tx = pd.read_parquet(settings.transactions_parquet)
    tx_tune, tx_test = train_test_split(
        tx, test_size=1 - settings.threshold_tune_frac,
        random_state=settings.random_seed, stratify=tx["scenario"])
    print(f"   stream: {len(tx_tune):,} tune / {len(tx_test):,} test\n")

    print("3-4) training, tuning thresholds on live stream, evaluating ...")
    results = []   # (PrecisionModel, ModelMetrics, tau_high, tau_low)
    for ModelClass in ALL_MODELS:
        m: PrecisionModel = ModelClass()
        t0 = time.perf_counter()
        m.fit(X, y, seed=settings.random_seed)
        train_s = time.perf_counter() - t0

        # tune thresholds on the live-distribution tune split
        probe = SanctionsScreener(index, m.as_loaded(tau_high=2.0, tau_low=2.0), settings)
        p_tune, ts_tune = transaction_probs(probe, tx_tune)
        tau_high, tau_low = choose_thresholds(p_tune, ts_tune, settings.target_precision)

        # evaluate on the disjoint test split
        screener = SanctionsScreener(index, m.as_loaded(tau_high=tau_high, tau_low=tau_low), settings)
        metrics, _, _ = evaluate(screener, tx_test)
        metrics = metrics.model_copy(update={"train_seconds": round(train_s, 2)})
        results.append((m, metrics, tau_high, tau_low))
        print(f"   {m.name:<12} precision={metrics.block_precision:.3f} "
              f"recall={metrics.recall:.3f} flag_recall={metrics.flag_recall:.3f} "
              f"over_block={metrics.over_block_rate:.3f}% review={metrics.review_rate:.2f}% "
              f"lat={metrics.mean_latency_ms:.2f}ms (tau {tau_low:.2f}/{tau_high:.2f})")

    print("\n5) selecting winner (operating constraints: over-block <= 1%, review <= 12%; "
          "then maximise flag-recall + F1) ...")

    # Domain-aware selection. A model is only viable if it doesn't over-block legit
    # customers (commercial killer) AND doesn't flood the analyst queue. Among viable
    # models, prefer the one that flags the most sanctioned payments (safety) and has
    # the best precision/recall balance. This rejects e.g. a 31%-review model that
    # would otherwise win on F1 alone.
    # a model is viable if it doesn't over-block customers AND keeps the review queue
    # bounded; among viable models, maximise flag-recall + F1.
    OVER_BLOCK_CAP, REVIEW_CAP = 1.0, 12.0

    def key(item):
        _m, mt, _th, _tl = item
        viable = mt.over_block_rate <= OVER_BLOCK_CAP and mt.review_rate <= REVIEW_CAP
        f1 = (2 * mt.block_precision * mt.recall / (mt.block_precision + mt.recall)
              if (mt.block_precision + mt.recall) else 0.0)
        return (1 if viable else 0, mt.flag_recall + f1)

    winner = max(results, key=key)
    wm, wmetrics, wth, wtl = winner
    print(f"   -> {wm.name}: precision {wmetrics.block_precision:.3f}, "
          f"recall {wmetrics.recall:.3f}, over-block {wmetrics.over_block_rate:.3f}%")

    wm.save(settings.model_path, tau_high=wth, tau_low=wtl,
            metrics=wmetrics, created_at=created_at)
    print(f"   saved -> {settings.model_path}")

    comparison = {
        "created_at": created_at,
        "winner": wm.name,
        "target_precision": settings.target_precision,
        "models": [mt.model_dump() for _m, mt, _th, _tl in results],
    }
    (settings.models_dir / "comparison.json").write_text(json.dumps(comparison, indent=2))
    print(f"   wrote -> {settings.models_dir/'comparison.json'}")

    _chart_comparison(results)
    _chart_calibration(winner, X, y)
    print("\nDONE.")


def _chart_comparison(results):
    names = [m.name for m, _mt, _a, _b in results]
    prec = [mt.block_precision for _m, mt, _a, _b in results]
    rec = [mt.recall for _m, mt, _a, _b in results]
    over = [mt.over_block_rate for _m, mt, _a, _b in results]
    x = np.arange(len(names)); w = 0.27
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(x - w, prec, w, label="block precision", color="#2c7fb8")
    ax.bar(x, rec, w, label="recall", color="#31a354")
    ax.bar(x + w, [o / 100 for o in over], w, label="over-block rate", color="#d95f0e")
    ax.axhline(0.95, color="red", ls="--", lw=1, label="precision target 0.95")
    ax.set_xticks(x); ax.set_xticklabels(names); ax.set_ylim(0, 1.05)
    ax.set_title("Stage-3 model comparison (held-out transactions)")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout(); fig.savefig(settings.visuals_dir / "10_model_comparison.png", dpi=120)
    plt.close(fig)
    print("   chart -> 10_model_comparison.png")


def _chart_calibration(winner, X, y):
    from sklearn.calibration import calibration_curve
    m, _mt, _th, _tl = winner
    _, Xte, _, yte = train_test_split(X, y, test_size=0.25,
                                      random_state=settings.random_seed, stratify=y)
    p = m.predict_proba(Xte)
    frac_pos, mean_pred = calibration_curve(yte, p, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.plot([0, 1], [0, 1], "k:", label="perfectly calibrated")
    ax.plot(mean_pred, frac_pos, "o-", color="#c51b8a", label=m.name)
    ax.set_xlabel("predicted probability"); ax.set_ylabel("observed frequency")
    ax.set_title(f"Calibration of winning model ({m.name})")
    ax.legend()
    fig.tight_layout(); fig.savefig(settings.visuals_dir / "11_calibration.png", dpi=120)
    plt.close(fig)
    print("   chart -> 11_calibration.png")


if __name__ == "__main__":
    main()
