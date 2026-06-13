"""
Benchmark the screener over the synthetic stream:
  (a) latency distribution single-thread  (is one check < 1s? by how much?)
  (b) parallel throughput across cores     (how we hold < 1s UNDER LOAD)
  (c) quality vs ground truth              (precision / recall / false-positive rate)

Uses the trained Stage-3 model if models/precision_model.joblib exists, otherwise
falls back to the fuzzy-only scorer (so you can see the before/after).

Run: .venv\\Scripts\\python.exe src\\benchmark.py
"""
from __future__ import annotations
import sys, os, statistics as st, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.stdout.reconfigure(encoding="utf-8")
sns.set_theme(style="whitegrid")

from screensmart.config import settings
from screensmart.screening.screener import SanctionsScreener
from screensmart.evaluation import evaluate, screen_row


def main():
    print("Building screener (index + model if present)...")
    t0 = time.perf_counter()
    scr = SanctionsScreener.load(settings)
    print(f"  ready in {time.perf_counter()-t0:.1f}s  | model = {scr.model_name} "
          f"(tau {scr.tau_low:.2f}/{scr.tau_high:.2f})")
    print(f"  index: {scr.index.n_entities:,} entities / {scr.index.n_variants:,} variants")

    tx = pd.read_parquet(settings.transactions_parquet)
    print(f"  {len(tx):,} transactions\n")

    # ---- (a) + (c): single-thread pass gives latency AND quality ----
    print("== single-thread latency + quality ==")
    metrics, verdicts, lat = evaluate(scr, tx)
    lat_sorted = sorted(lat)

    def pct(p):
        return lat_sorted[min(len(lat_sorted) - 1, int(len(lat_sorted) * p))]
    print(f"  checks     : {len(lat):,}")
    print(f"  mean       : {st.mean(lat):.3f} ms")
    print(f"  p50 / p95  : {pct(0.50):.3f} / {pct(0.95):.3f} ms")
    print(f"  p99 / max  : {pct(0.99):.3f} / {max(lat):.3f} ms")
    print(f"  slowest check = {max(lat)/1000:.4f} s  (target < 1 s)\n")

    # ---- (b) parallel throughput ----
    workers = max(2, (os.cpu_count() or 4))
    rows = [r for _, r in tx.iterrows()]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda r: screen_row(scr, r), rows, chunksize=64))
    pwall = time.perf_counter() - t0
    swall = sum(lat) / 1000
    print(f"== parallel ({workers} threads) ==")
    print(f"  throughput : {len(rows)/pwall:,.0f} checks/sec  "
          f"(vs {len(rows)/swall:,.0f}/sec single-thread)")
    print("  note: GIL caps in-process threading; scale with PROCESSES/replicas.\n")

    # ---- quality summary ----
    print("== quality vs ground truth ==")
    s = tx.assign(pred=verdicts)
    cm = pd.crosstab(s["expected_verdict"], s["pred"],
                     rownames=["expected"], colnames=["predicted"])
    print(cm.to_string())
    print(f"\n  BLOCK precision : {metrics.block_precision:.3f}")
    print(f"  BLOCK recall    : {metrics.recall:.3f}")
    print(f"  over-block rate : {metrics.over_block_rate:.3f}% of clean payments blocked")
    print(f"  REVIEW queue    : {metrics.review_rate:.2f}% of all payments to a human")

    # ---- charts ----
    fig, ax = plt.subplots(figsize=(8, 4.5))
    hi = pct(0.99) * 1.5 or 1
    sns.histplot([x for x in lat if x < hi], bins=50, ax=ax, color="#2c7fb8")
    ax.axvline(pct(0.99), color="red", ls="--", label=f"p99={pct(0.99):.1f}ms")
    ax.set_title("Per-check latency (single thread) — well inside the 1 s budget")
    ax.set_xlabel("milliseconds"); ax.legend()
    fig.tight_layout(); fig.savefig(settings.visuals_dir / "08_latency.png", dpi=120)
    plt.close(fig)
    print("\n  chart -> 08_latency.png")

    fig, ax = plt.subplots(figsize=(6.5, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax)
    ax.set_title(f"Verdict confusion matrix ({scr.model_name})")
    fig.tight_layout(); fig.savefig(settings.visuals_dir / "09_confusion.png", dpi=120)
    plt.close(fig)
    print("  chart -> 09_confusion.png")


if __name__ == "__main__":
    main()
