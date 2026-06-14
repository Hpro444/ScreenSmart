"""Scoring helpers for offline crypto wallet exposure propagation."""

from __future__ import annotations

import datetime as dt
import decimal
from typing import Any

DEFAULT_REVIEW_THRESHOLD = 0.08
HIGH_DEGREE_SMART_CONTRACT_THRESHOLD = 25
FLOW_EDGE_TYPES = {
    "TRANSFERRED_TO",
    "BRIDGED_TO",
    "DEPOSITED_TO_EXCHANGE",
    "WITHDREW_FROM_EXCHANGE",
}


def source_risk(risk_level: str) -> float:
    weights = {
        "SANCTIONED": 1.0,
        "HACK_PROCEEDS": 0.9,
        "RANSOMWARE": 0.9,
        "SCAM": 0.75,
        "SUSPICIOUS": 0.7,
        "MIXER": 0.6,
    }
    return weights.get((risk_level or "NONE").upper(), 0.0)


def relation_weight(edge_type: str) -> float:
    weights = {
        "TRANSFERRED_TO": 0.65,
        "USED_MIXER": 0.55,
        "BRIDGED_TO": 0.60,
        "DEPOSITED_TO_EXCHANGE": 0.50,
        "WITHDREW_FROM_EXCHANGE": 0.50,
    }
    return weights.get((edge_type or "").upper(), 0.20)


def value_weight(total_usd_value: decimal.Decimal | float | int | None) -> float:
    value = float(total_usd_value or 0.0)
    if value >= 100000:
        return 1.0
    if value >= 10000:
        return 0.8
    if value >= 1000:
        return 0.5
    if value >= 100:
        return 0.2
    return 0.05


def concentration_score(flow_concentration: float | int | None) -> float:
    concentration = float(flow_concentration or 0.0)
    if concentration >= 0.75:
        return 1.0
    if concentration >= 0.50:
        return 0.8
    if concentration >= 0.25:
        return 0.5
    if concentration >= 0.10:
        return 0.2
    return 0.05


def time_decay(last_seen: dt.date | None, *, today: dt.date | None = None) -> float:
    if last_seen is None:
        return 0.1
    today = today or dt.date.today()
    days = max(0, (today - last_seen).days)
    if days <= 7:
        return 1.0
    if days <= 30:
        return 0.8
    if days <= 180:
        return 0.4
    return 0.1


def hop_decay(depth: int) -> float:
    return {0: 1.0, 1: 0.7, 2: 0.4, 3: 0.2}.get(depth, 0.1)


def average_transaction_value(edge: dict) -> float:
    tx_count = max(0, int(edge.get("transaction_count") or 0))
    total = float(edge.get("total_usd_value") or 0.0)
    if tx_count <= 0:
        return total
    return total / tx_count


def crypto_materiality_weight(
    edge_type: str,
    total_usd_value: decimal.Decimal | float | int | None,
    *,
    flow_concentration: float | int | None = None,
) -> float:
    if (edge_type or "").upper() not in FLOW_EDGE_TYPES:
        return value_weight(total_usd_value)
    absolute_weight = value_weight(total_usd_value)
    concentration_weight = concentration_score(flow_concentration)
    return 0.70 * absolute_weight + 0.30 * concentration_weight


def hub_penalty(edge: dict) -> float:
    node_type = str(edge.get("to_node_type") or edge.get("neighbor_node_type") or "").upper()
    degree = int(edge.get("to_node_degree") or edge.get("neighbor_node_degree") or 0)
    if node_type == "EXCHANGE_HOT_WALLET":
        return 0.2
    if node_type == "MIXER":
        return 0.4
    if node_type == "BRIDGE":
        return 0.4
    if node_type == "SMART_CONTRACT":
        return 0.1 if degree >= HIGH_DEGREE_SMART_CONTRACT_THRESHOLD else 0.7
    if node_type and node_type != "WALLET":
        return 0.7
    return 1.0


def edge_score(edge: dict, *, today: dt.date | None = None) -> float:
    confidence = float(edge.get("confidence") or 1.0)
    return (
        relation_weight(edge.get("edge_type", ""))
        * crypto_materiality_weight(
            edge.get("edge_type", ""),
            edge.get("total_usd_value"),
            flow_concentration=edge.get("flow_concentration"),
        )
        * time_decay(edge.get("last_seen"), today=today)
        * confidence
        * hub_penalty(edge)
    )


def _parse_date(value: Any) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def is_low_value_structuring_pattern(edge: dict) -> bool:
    tx_count = int(edge.get("transaction_count") or 0)
    total = float(edge.get("total_usd_value") or 0.0)
    avg = average_transaction_value(edge)
    return tx_count >= 100 and total >= 1000.0 and avg < 100.0


def ignore_isolated_dust_edge(edge: dict) -> bool:
    """Prune only isolated dust, not aggregated repeated low-value flow.

    The graph stores aggregated edge rows, so pruning must examine aggregate
    activity rather than single-transaction thresholds. A tiny indirect edge is
    ignored only when it looks like a single isolated low-value touchpoint.
    """
    tx_count = int(edge.get("transaction_count") or 0)
    total = float(edge.get("total_usd_value") or 0.0)
    avg = average_transaction_value(edge)
    first_seen = _parse_date(edge.get("first_seen"))
    last_seen = _parse_date(edge.get("last_seen"))
    activity_span_days = (
        max(0, (last_seen - first_seen).days)
        if first_seen is not None and last_seen is not None
        else 0
    )

    if is_low_value_structuring_pattern(edge):
        return False
    if tx_count == 1 and total < 100.0 and avg < 100.0 and activity_span_days <= 1:
        return True
    return False


def path_reaches_sanctioned(best_path: list[dict]) -> bool:
    return any(str(node.get("risk_level", "")).upper() == "SANCTIONED" for node in best_path)


def path_is_override_eligible(best_path: list[dict]) -> bool:
    if not best_path:
        return False
    return all(bool(node.get("override_allowed", True)) for node in best_path[1:])


def exposure_verdict(
    score: float,
    *,
    direct_hit: bool = False,
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
    best_depth: int | None = None,
    best_path: list[dict] | None = None,
) -> str:
    path = best_path or []
    if direct_hit:
        return "MATCH"
    if score >= review_threshold:
        return "REVIEW"
    if best_depth is not None and best_depth <= 2 and path_reaches_sanctioned(path) and path_is_override_eligible(path):
        return "REVIEW"
    return "NO_MATCH"
