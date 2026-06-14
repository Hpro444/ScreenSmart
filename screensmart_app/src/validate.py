"""
Validation report for the saved model — the honest, statistics-aware view.

Screens the (entity-disjoint, independent-noise) transaction stream once, then:
  * BOOTSTRAPS each metric (resample rows with replacement) -> mean ± 95% CI, so the
    numbers come with uncertainty instead of a single point estimate;
  * reports the DANGEROUS-MISS rate (a genuinely sanctioned payment RELEASED as NO_MATCH)
    — the metric that actually matters for compliance;
  * prints a per-scenario verdict breakdown so you see where errors concentrate.

Run: .venv\\Scripts\\python.exe screensmart_app\\src\\validate.py
"""
from __future__ import annotations
import sys, json
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

from screensmart.config import settings
from screensmart.screening.screener import SanctionsScreener
from screensmart.evaluation import screen_row, _SANCTIONED, _CLEAN
from screensmart.domain.enums import VerdictType

N_BOOT = 300


def _metrics(verdict: np.ndarray, sanc: np.ndarray, clean: np.ndarray) -> dict:
    block = verdict == VerdictType.MATCH.value
    flagged = np.isin(verdict, [VerdictType.MATCH.value, VerdictType.REVIEW.value])
    released = verdict == VerdictType.NO_MATCH.value
    nb, ns, nc = block.sum(), sanc.sum(), clean.sum()
    return {
        "block_precision": float((sanc & block).sum() / nb) if nb else 0.0,
        "recall_autoblock": float((sanc & block).sum() / ns) if ns else 0.0,
        "flag_recall": float((sanc & flagged).sum() / ns) if ns else 0.0,
        "over_block_pct": float((clean & block).sum() / nc * 100) if nc else 0.0,
        "review_pct": float((verdict == VerdictType.REVIEW.value).mean() * 100),
        "dangerous_miss_pct": float((sanc & released).sum() / ns * 100) if ns else 0.0,
    }


def main():
    print("loading screener + scoring the stream ...")
    scr = SanctionsScreener.load(settings)
    tx = pd.read_parquet(settings.transactions_parquet)
    verdict = np.array([screen_row(scr, r)[0] for _, r in tx.iterrows()])
    sanc = tx["scenario"].isin(_SANCTIONED).to_numpy()
    clean = tx["scenario"].isin(_CLEAN).to_numpy()
    n = len(tx)
    print(f"  model={scr.model_name}  tau {scr.tau_low}/{scr.tau_high}  rows={n:,}\n")

    point = _metrics(verdict, sanc, clean)

    # bootstrap 95% CI
    rng = np.random.default_rng(0)
    boot: dict[str, list[float]] = {k: [] for k in point}
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, n)
        m = _metrics(verdict[idx], sanc[idx], clean[idx])
        for k, v in m.items():
            boot[k].append(v)

    print("== metric            point     mean ± 95% CI ==")
    summary = {}
    for k in point:
        arr = np.array(boot[k])
        lo, hi = np.percentile(arr, [2.5, 97.5])
        summary[k] = {"point": round(point[k], 4), "mean": round(float(arr.mean()), 4),
                      "ci95": [round(float(lo), 4), round(float(hi), 4)]}
        unit = "%" if k.endswith("pct") else ""
        print(f"  {k:<20} {point[k]:7.3f}{unit:1}   {arr.mean():7.3f} "
              f"[{lo:.3f}, {hi:.3f}]{unit}")

    print("\n== per-scenario verdict breakdown ==")
    print(pd.crosstab(tx["scenario"], pd.Series(verdict, name="predicted")).to_string())

    print(f"\nDANGEROUS-MISS (sanctioned released): {point['dangerous_miss_pct']:.2f}% "
          f"— the compliance-critical number.")

    out = settings.models_dir / "validation.json"
    out.write_text(json.dumps({"model": scr.model_name, "rows": n,
                               "n_boot": N_BOOT, "metrics": summary}, indent=2))
    print(f"\nwrote -> {out}")


if __name__ == "__main__":
    main()
