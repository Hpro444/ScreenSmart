"""Evaluate account-only exposure lookup against synthetic payments."""

from __future__ import annotations

import argparse

import pandas as pd
import sqlalchemy as sa

from ..db.database import get_engine
from ..db.schema import synthetic_payments
from .lookup import AccountExposureLookup
from .scoring import DEFAULT_REVIEW_THRESHOLD

THRESHOLDS = [0.05, 0.08, 0.10, 0.15, 0.25, 0.45]


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int((len(ordered) - 1) * p))
    return ordered[idx]


def evaluate_account_only(*, threshold: float | None = None) -> tuple[pd.DataFrame, dict[str, float]]:
    threshold = DEFAULT_REVIEW_THRESHOLD if threshold is None else threshold
    engine = get_engine()
    lookup = AccountExposureLookup.load(engine)
    with engine.connect() as conn:
        tx = pd.read_sql(
            sa.select(
                synthetic_payments.c.case_id,
                synthetic_payments.c.scenario_type,
                synthetic_payments.c.expected_verdict,
                synthetic_payments.c.recipient_iban,
            ),
            conn,
        )

    rows = []
    latencies = []
    for row in tx.itertuples():
        result = lookup.screen_account(row.recipient_iban, review_threshold=threshold)
        rows.append(
            {
                "case_id": row.case_id,
                "scenario_type": row.scenario_type,
                "expected_verdict": row.expected_verdict,
                "predicted_verdict": result.verdict.value,
                "score": result.exposure_score,
                "depth": result.best_depth,
                "latency_ms": result.latency_ms,
            }
        )
        latencies.append(result.latency_ms)

    df = pd.DataFrame(rows)
    account_accuracy = (df["predicted_verdict"] == df["expected_verdict"]).mean()
    dangerous = df["expected_verdict"].isin(["MATCH", "REVIEW"])
    dangerous_miss_rate = (
        ((df["predicted_verdict"] == "NO_MATCH") & dangerous).sum() / max(1, dangerous.sum())
    )
    clean = df["expected_verdict"] == "NO_MATCH"
    false_positive_friction_rate = (
        ((df["predicted_verdict"] != "NO_MATCH") & clean).sum() / max(1, clean.sum())
    )
    review_rate = (df["predicted_verdict"] == "REVIEW").mean()

    metrics = {
        "threshold": float(threshold),
        "account_accuracy": float(account_accuracy),
        "dangerous_miss_rate": float(dangerous_miss_rate),
        "false_positive_friction_rate": float(false_positive_friction_rate),
        "review_rate": float(review_rate),
        "p50_latency_ms": float(pct(latencies, 0.50)),
        "p95_latency_ms": float(pct(latencies, 0.95)),
    }
    return df, metrics


def _print_single_threshold(df: pd.DataFrame, metrics: dict[str, float]) -> None:
    print(f"threshold={metrics['threshold']:.2f}")
    print(f"account_accuracy: {metrics['account_accuracy']:.3f}")
    print(f"dangerous_miss_rate: {metrics['dangerous_miss_rate']:.3f}")
    print(f"false_positive_friction_rate: {metrics['false_positive_friction_rate']:.3f}")
    print(f"review_rate: {metrics['review_rate']:.3f}")
    print(f"p50 latency: {metrics['p50_latency_ms']:.4f} ms")
    print(f"p95 latency: {metrics['p95_latency_ms']:.4f} ms")
    print("per-scenario breakdown:")
    grouped = df.groupby("scenario_type")
    for scenario, part in grouped:
        sc_accuracy = (part["predicted_verdict"] == part["expected_verdict"]).mean()
        sc_miss = (
            ((part["predicted_verdict"] == "NO_MATCH") & part["expected_verdict"].isin(["MATCH", "REVIEW"])).sum()
            / max(1, part["expected_verdict"].isin(["MATCH", "REVIEW"]).sum())
        )
        sc_friction = (
            ((part["predicted_verdict"] != "NO_MATCH") & (part["expected_verdict"] == "NO_MATCH")).sum()
            / max(1, (part["expected_verdict"] == "NO_MATCH").sum())
        )
        counts = part["predicted_verdict"].value_counts().to_dict()
        print(
            f"  {scenario}: total={len(part)} account_accuracy={sc_accuracy:.3f} "
            f"dangerous_miss_rate={sc_miss:.3f} false_positive_friction_rate={sc_friction:.3f} "
            f"pred={{MATCH:{counts.get('MATCH', 0)}, REVIEW:{counts.get('REVIEW', 0)}, NO_MATCH:{counts.get('NO_MATCH', 0)}}}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=DEFAULT_REVIEW_THRESHOLD)
    parser.add_argument("--sweep", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sweep:
        print("account-only threshold sweep")
        print()
        for threshold in THRESHOLDS:
            df, metrics = evaluate_account_only(threshold=threshold)
            _print_single_threshold(df, metrics)
            print()
        return

    df, metrics = evaluate_account_only(threshold=args.threshold)
    _print_single_threshold(df, metrics)


if __name__ == "__main__":
    main()
