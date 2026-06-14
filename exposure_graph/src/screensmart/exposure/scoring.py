"""Scoring helpers for offline graph-exposure propagation."""

from __future__ import annotations

import datetime as dt
import decimal
from typing import Any

DEFAULT_REVIEW_THRESHOLD = 0.08


def source_risk(risk_level: str) -> float:
    risk = (risk_level or "NONE").upper()
    if risk == "SANCTIONED":
        return 1.0
    if risk == "SUSPICIOUS":
        return 0.7
    return 0.0


def relation_weight(edge_type: str) -> float:
    weights = {
        "OWNS": 1.0,
        "USES_ACCOUNT": 0.9,
        "SENT_TO": 0.6,
        "RECEIVED_FROM": 0.6,
        "SHARED_IDENTIFIER": 0.4,
    }
    return weights.get((edge_type or "").upper(), 0.2)


def amount_weight(total_amount: decimal.Decimal | float | int | None) -> float:
    amount = float(total_amount or 0.0)
    if amount >= 50000:
        return 1.0
    if amount >= 10000:
        return 0.8
    if amount >= 1000:
        return 0.5
    if amount >= 100:
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


def flow_materiality_weight(
    edge_type: str,
    total_amount: decimal.Decimal | float | int | None,
    *,
    flow_concentration: float | int | None = None,
) -> float:
    if (edge_type or "").upper() in {"OWNS", "USES_ACCOUNT", "SHARED_IDENTIFIER"}:
        return 1.0
    absolute_weight = amount_weight(total_amount)
    concentration_weight = concentration_score(flow_concentration)
    return 0.70 * absolute_weight + 0.30 * concentration_weight


def edge_score(edge: dict, *, today: dt.date | None = None) -> float:
    confidence = float(edge.get("confidence") or 1.0)
    return (
        relation_weight(edge.get("edge_type", ""))
        * flow_materiality_weight(
            edge.get("edge_type", ""),
            edge.get("total_amount"),
            flow_concentration=edge.get("flow_concentration"),
        )
        * time_decay(edge.get("last_seen"), today=today)
        * confidence
    )


def ignore_weak_edge(edge: dict, *, today: dt.date | None = None) -> bool:
    amount = float(edge.get("total_amount") or 0.0)
    edge_type = (edge.get("edge_type") or "").upper()
    materiality = flow_materiality_weight(
        edge_type,
        edge.get("total_amount"),
        flow_concentration=edge.get("flow_concentration"),
    )
    t_decay = time_decay(edge.get("last_seen"), today=today)
    if edge_type == "SENT_TO" and amount < 100:
        return True
    if t_decay == 0.1 and materiality <= 0.2:
        return True
    return False


def _parse_date(value: Any) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def path_reaches_sanctioned(best_path: list[dict]) -> bool:
    return any(str(node.get("risk_level", "")).upper() == "SANCTIONED" for node in best_path)


def path_is_override_eligible(best_path: list[dict]) -> bool:
    if not best_path:
        return False
    return all(bool(node.get("override_allowed", True)) for node in best_path[1:])


def path_has_meaningful_signal(best_path: list[dict], *, today: dt.date | None = None) -> bool:
    today = today or dt.date.today()
    for node in best_path[1:]:
        edge_type = str(node.get("edge_type", "")).upper()
        amount = float(node.get("amount") or 0.0)
        last_seen = _parse_date(node.get("last_seen"))
        recent = last_seen is not None and (today - last_seen).days <= 180
        if edge_type in {"OWNS", "USES_ACCOUNT"}:
            return True
        if amount >= 1000:
            return True
        if amount >= 100 and recent:
            return True
    return False


def is_old_tiny_exposure(best_path: list[dict], *, today: dt.date | None = None) -> bool:
    if len(best_path) <= 1:
        return False
    if path_has_meaningful_signal(best_path, today=today):
        return False
    sent_edges = [node for node in best_path[1:] if str(node.get("edge_type", "")).upper() == "SENT_TO"]
    if not sent_edges:
        return False
    today = today or dt.date.today()
    for edge in sent_edges:
        amount = float(edge.get("amount") or 0.0)
        last_seen = _parse_date(edge.get("last_seen"))
        age_days = (today - last_seen).days if last_seen is not None else 9999
        if amount >= 100 or age_days <= 180:
            return False
    return True


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
    if is_old_tiny_exposure(path):
        return "NO_MATCH"
    if score >= review_threshold:
        return "REVIEW"
    if best_depth is not None and best_depth <= 2 and path_reaches_sanctioned(path) and path_is_override_eligible(path):
        return "REVIEW"
    return "NO_MATCH"
