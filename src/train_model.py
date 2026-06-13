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
from screensmart.evaluation import evaluate
from screensmart.domain.enums import VerdictType, Channel


def transaction_probs(screener: SanctionsScreener, tx: pd.DataFrame
                      ) -> tuple[np.ndarray, np.ndarray]:
    """Best-candidate calibrated probability per transaction + 'is a true block' truth."""
    probs, truth = [], []
    for _, row in tx.iterrows():
        if row["channel"] == Channel.CRYPTO.value:
            r = screener.screen_wallet(row["wallet"])
        else:
            r = screener.screen_name(row["bene_name"], row.get("bene_country", ""))
        probs.append(r.probability)
        truth.append(1 if row["expected_verdict"] == VerdictType.MATCH.value else 0)
    return np.asarray(probs), np.asarray(truth)


def choose_thresholds(probs: np.ndarray, truth: np.ndarray, target_precision: float,
                      ) -> tuple[float, float]:
    """tau_high: lowest cut giving precision>=target (=> max recall);
       tau_low : highest cut still catching >=98% of true blocks into REVIEW."""
    prec, rec, thr = precision_recall_curve(truth, probs)
    prec, rec = prec[:-1], rec[:-1]          # align with thr
    if len(thr) == 0:
        return 0.9, 0.5

    ok = np.where(prec >= target_precision)[0]
    tau_high = float(thr[ok[np.argmax(rec[ok])]]) if len(ok) else float(thr[np.argmax(prec)])

    hi_rec = np.where(rec >= 0.98)[0]
    tau_low = float(thr[hi_rec[np.argmax(thr[hi_rec])]]) if len(hi_rec) else tau_high * 0.5
    tau_low = min(tau_low, tau_high)
    if tau_low >= tau_high:                  # keep a real REVIEW band
        tau_low = tau_high * 0.5
    return round(tau_high, 4), round(tau_low, 4)


def main():
    settings.ensure_dirs()
    created_at = dt.datetime.now().isoformat(timespec="seconds")

    print("1) building index ...")
    index = SanctionsIndex.from_parquet(settings.sanctions_parquet)
    print(f"   {index.n_entities:,} entities / {index.n_variants:,} variants")

    print("2) manufacturing training pairs ...")
    X, y = build_training_pairs(index, seed=settings.random_seed)
    print(f"   {len(y):,} pairs  ({int(y.sum()):,} positive / {int((y==0).sum()):,} negative)")

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
        p_tune, t_tune = transaction_probs(probe, tx_tune)
        tau_high, tau_low = choose_thresholds(p_tune, t_tune, settings.target_precision)

        # evaluate on the disjoint test split
        screener = SanctionsScreener(index, m.as_loaded(tau_high=tau_high, tau_low=tau_low), settings)
        metrics, _, _ = evaluate(screener, tx_test)
        metrics = metrics.model_copy(update={"train_seconds": round(train_s, 2)})
        results.append((m, metrics, tau_high, tau_low))
        print(f"   {m.name:<12} precision={metrics.block_precision:.3f} "
              f"recall={metrics.recall:.3f} over_block={metrics.over_block_rate:.3f}% "
              f"review={metrics.review_rate:.2f}% lat={metrics.mean_latency_ms:.2f}ms "
              f"(tau {tau_low:.2f}/{tau_high:.2f}, train {train_s:.1f}s)")

    print("\n5) selecting winner (max recall s.t. precision >= "
          f"{settings.target_precision}) ...")

    def key(item):
        _m, mt, _th, _tl = item
        meets = mt.block_precision >= settings.target_precision
        f1 = (2 * mt.block_precision * mt.recall / (mt.block_precision + mt.recall)
              if (mt.block_precision + mt.recall) else 0.0)
        return (1 if meets else 0, mt.recall if meets else f1, f1)

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
