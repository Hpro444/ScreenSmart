"""Benchmark and scenario audit for the synthetic crypto exposure graph.

Run:
    python -m crypto_exposure_graph.exposure.benchmark
"""

from __future__ import annotations

import collections
import datetime as dt
import time

import sqlalchemy as sa

from ..db.database import get_engine
from ..db.schema import (
    crypto_exposure_index,
    crypto_graph_edges,
    crypto_graph_nodes,
    crypto_synthetic_screenings,
)
from .lookup import CryptoWalletExposureLookup
from .precompute import compute_exposure, load_graph, write_exposure_rows

SCENARIO_ORDER = [
    "direct_sanctioned_wallet",
    "one_hop_wallet_exposure",
    "two_hop_wallet_exposure",
    "crypto_derived_anchor_milica_to_sanctioned",
    "crypto_mateja_to_derived_anchor",
    "crypto_andrija_funds_derived_proxy",
    "crypto_tiny_upstream_funding_suppressed",
    "crypto_exchange_upstream_funding_suppressed",
    "crypto_bridge_or_mixer_upstream_suppressed",
    "crypto_normal_high_concentration_control_no_match",
    "crypto_old_weak_derived_anchor_suppressed",
    "repeated_small_transfers_to_risky_wallet",
    "isolated_dust_exposure",
    "exchange_contamination_prevented",
    "bridge_contamination_prevented",
    "mixer_route",
    "bridge_route",
    "ransomware_cluster",
    "exchange_hot_wallet_noise",
    "smart_contract_noise",
    "clean_wallet",
]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def _scenario_sort_key(item: tuple[str, dict]) -> tuple[int, str]:
    scenario, _data = item
    if scenario in SCENARIO_ORDER:
        return (SCENARIO_ORDER.index(scenario), scenario)
    return (len(SCENARIO_ORDER), scenario)


def main() -> None:
    engine = get_engine()
    today = dt.date.today()

    precompute_t0 = time.perf_counter()
    nodes, adjacency, load_debug = load_graph(engine, today=today)
    rows, stats = compute_exposure(
        nodes,
        adjacency,
        max_depth=2,
        top_k=20,
        min_score=0.03,
        today=today,
    )
    stats.edges_considered = load_debug["edges_considered"]
    stats.adjacency_entries_created = load_debug["adjacency_entries_created"]
    stats.reverse_edges_skipped_due_to_directionality = load_debug["reverse_edges_skipped_due_to_directionality"]
    write_exposure_rows(engine, rows, reset=True)
    precompute_runtime = time.perf_counter() - precompute_t0

    lookup = CryptoWalletExposureLookup.load(engine)
    scenario_summary: dict[str, dict] = collections.defaultdict(
        lambda: {
            "expected": None,
            "observed_counts": collections.Counter(),
            "total": 0,
            "correct": 0,
        }
    )
    latency_samples: list[float] = []
    total_cases = 0
    correct_cases = 0
    review_cases = 0
    dangerous_misses = 0
    dangerous_total = 0
    false_positive_friction = 0
    no_match_total = 0

    with engine.connect() as conn:
        screening_rows = list(
            conn.execute(
                sa.select(
                    crypto_synthetic_screenings.c.case_id,
                    crypto_synthetic_screenings.c.scenario_type,
                    crypto_synthetic_screenings.c.chain,
                    crypto_synthetic_screenings.c.wallet_address,
                    crypto_synthetic_screenings.c.asset,
                    crypto_synthetic_screenings.c.amount_usd,
                    crypto_synthetic_screenings.c.expected_verdict,
                ).order_by(crypto_synthetic_screenings.c.case_id)
            )
        )
        counts = {
            "crypto_graph_nodes": conn.scalar(sa.select(sa.func.count()).select_from(crypto_graph_nodes)) or 0,
            "crypto_graph_edges": conn.scalar(sa.select(sa.func.count()).select_from(crypto_graph_edges)) or 0,
            "crypto_exposure_index": conn.scalar(sa.select(sa.func.count()).select_from(crypto_exposure_index)) or 0,
        }

    for row in screening_rows:
        result = lookup.screen_wallet(
            row.chain,
            row.wallet_address,
            asset=row.asset,
            amount_usd=float(row.amount_usd or 0.0),
        )
        observed = result.recommended_action.value
        expected = row.expected_verdict
        total_cases += 1
        correct = observed == expected
        correct_cases += int(correct)
        review_cases += int(observed == "REVIEW")
        latency_samples.append(result.latency_ms)

        scenario = scenario_summary[row.scenario_type]
        scenario["expected"] = expected
        scenario["observed_counts"][observed] += 1
        scenario["total"] += 1
        scenario["correct"] += int(correct)

        if expected == "MATCH":
            dangerous_total += 1
            dangerous_misses += int(observed != "MATCH")
        elif expected == "REVIEW":
            dangerous_total += 1
            dangerous_misses += int(observed == "NO_MATCH")
        elif expected == "NO_MATCH":
            no_match_total += 1
            false_positive_friction += int(observed != "NO_MATCH")

    print("Benchmark Metrics")
    print(f"crypto_accuracy: {correct_cases / total_cases:.4f}" if total_cases else "crypto_accuracy: 0.0000")
    print(
        f"dangerous_miss_rate: {dangerous_misses / dangerous_total:.4f}"
        if dangerous_total
        else "dangerous_miss_rate: 0.0000"
    )
    print(
        f"false_positive_friction_rate: {false_positive_friction / no_match_total:.4f}"
        if no_match_total
        else "false_positive_friction_rate: 0.0000"
    )
    print(f"review_rate: {review_cases / total_cases:.4f}" if total_cases else "review_rate: 0.0000")
    print(f"p50_lookup_latency: {_percentile(latency_samples, 50):.4f} ms")
    print(f"p95_lookup_latency: {_percentile(latency_samples, 95):.4f} ms")
    print(f"precompute_runtime: {precompute_runtime:.4f} s")
    print(f"exposure_index_size: {counts['crypto_exposure_index']}")
    print()
    print("Graph Counts")
    print(f"crypto_graph_nodes: {counts['crypto_graph_nodes']}")
    print(f"crypto_graph_edges: {counts['crypto_graph_edges']}")
    print(f"crypto_exposure_index: {counts['crypto_exposure_index']}")
    print()
    print("Precompute Debug")
    print(f"edges considered: {stats.edges_considered}")
    print(f"adjacency entries created: {stats.adjacency_entries_created}")
    print(f"reverse edges skipped due to policy: {stats.reverse_edges_skipped_due_to_directionality}")
    print(f"service-boundary propagation stops: {stats.service_boundary_propagation_stops}")
    print(f"top-k truncated edges: {stats.top_k_truncated_edges}")
    print(f"derived anchor candidates: {stats.derived_anchor_candidates}")
    print(f"derived anchor rows: {stats.derived_anchor_rows}")
    print(f"derived anchor suppressed rows: {stats.derived_anchor_suppressed_rows}")
    print()
    print("Scenario Results")
    for scenario_name, data in sorted(scenario_summary.items(), key=_scenario_sort_key):
        observed_counts = ", ".join(
            f"{verdict}={count}" for verdict, count in sorted(data["observed_counts"].items())
        )
        print(
            f"{scenario_name}: expected={data['expected']} observed=[{observed_counts}] "
            f"accuracy={data['correct']}/{data['total']}"
        )


if __name__ == "__main__":
    main()
