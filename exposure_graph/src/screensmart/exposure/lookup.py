"""Realtime account exposure lookup over precomputed data only.

This module performs O(1)-style lookups against `graph_nodes` and `exposure_index`.
It does not traverse `graph_edges` and does not run BFS online.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import json
import time
from typing import Any

import sqlalchemy as sa

from ..db.database import get_engine
from ..db.schema import exposure_index, graph_edges, graph_nodes
from ..domain.enums import VerdictType
from .scoring import DEFAULT_REVIEW_THRESHOLD, is_old_tiny_exposure

ACCOUNT_NODE_TYPES = {"IBAN", "ACCOUNT", "WALLET", "PERSON", "COMPANY", "BANK"}
RISK_TYPE = "SANCTIONS_EVASION"
EVASION_TYPOLOGY = "PROXY_NETWORK"
REVIEW_RISK_SCORE_THRESHOLD = 0.30
HIGH_RISK_COUNTRIES = {"IR", "KP", "SY", "RU", "BY"}


@dataclasses.dataclass(frozen=True)
class AccountScreeningResult:
    """Final account-exposure payload returned by the realtime lookup path."""

    module: str
    node_key: str
    score: float
    exposure_score: float
    graph_exposure_score: float
    risk_score: float
    sanctions_evasion_score: float
    recommended_action: VerdictType
    verdict: VerdictType
    risk_type: str
    evasion_typology: str
    source_risk_level: str
    source_node_type: str | None
    rule_triggers: list[str]
    best_depth: int | None
    direct_hit: bool
    node_type: str | None
    risk_level: str | None
    source_risk_node: str | None
    best_path: list[dict]
    primary_reason: str
    reason: str
    evidence: list[dict]
    evidence_package: list[dict]
    latency_ms: float


class AccountExposureLookup:
    """Realtime reader over precomputed account exposure data."""

    def __init__(
        self,
        nodes_by_key: dict[str, dict],
        exposures_by_key: dict[str, dict],
        behavior_profiles_by_key: dict[str, dict],
    ) -> None:
        self.nodes_by_key = nodes_by_key
        self.exposures_by_key = exposures_by_key
        self.behavior_profiles_by_key = behavior_profiles_by_key

    @classmethod
    def load(cls, engine=None) -> "AccountExposureLookup":
        """Hydrate the in-memory lookup tables from Postgres."""
        engine = engine or get_engine()
        nodes_by_key: dict[str, dict] = {}
        exposures_by_key: dict[str, dict] = {}
        edge_rows: list[dict] = []
        with engine.connect() as conn:
            for row in conn.execute(
                sa.select(
                    graph_nodes.c.node_key,
                    graph_nodes.c.node_type,
                    graph_nodes.c.display_name,
                    graph_nodes.c.country,
                    graph_nodes.c.risk_level,
                )
            ):
                nodes_by_key[row.node_key] = {
                    "node_key": row.node_key,
                    "node_type": row.node_type,
                    "display_name": row.display_name,
                    "country": row.country,
                    "risk_level": row.risk_level,
                }

            for row in conn.execute(
                sa.select(
                    exposure_index.c.node_key,
                    exposure_index.c.exposure_score,
                    exposure_index.c.best_depth,
                    exposure_index.c.best_path,
                    exposure_index.c.source_risk_node,
                    exposure_index.c.reason,
                )
            ):
                exposures_by_key[row.node_key] = {
                    "node_key": row.node_key,
                    "exposure_score": float(row.exposure_score),
                    "best_depth": row.best_depth,
                    "best_path": row.best_path or [],
                    "source_risk_node": row.source_risk_node,
                    "reason": row.reason or "",
                }
            for row in conn.execute(
                sa.select(
                    graph_edges.c.from_node_key,
                    graph_edges.c.to_node_key,
                    graph_edges.c.edge_type,
                    graph_edges.c.total_amount,
                    graph_edges.c.transaction_count,
                    graph_edges.c.first_seen,
                    graph_edges.c.last_seen,
                    graph_edges.c.confidence,
                )
            ):
                edge_rows.append(
                    {
                        "from_node_key": row.from_node_key,
                        "to_node_key": row.to_node_key,
                        "edge_type": row.edge_type,
                        "total_amount": float(row.total_amount or 0.0),
                        "transaction_count": int(row.transaction_count or 0),
                        "first_seen": row.first_seen,
                        "last_seen": row.last_seen,
                        "confidence": float(row.confidence or 1.0),
                    }
                )
        behavior_profiles_by_key = cls._build_behavior_profiles(nodes_by_key, edge_rows)
        return cls(nodes_by_key, exposures_by_key, behavior_profiles_by_key)

    @staticmethod
    def _empty_behavior_profile() -> dict[str, Any]:
        return {
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 0.0,
            "incoming_tx_count": 0,
            "outgoing_tx_count": 0,
            "incoming_counterparties": set(),
            "outgoing_counterparties": set(),
            "small_inbound_counterparties": set(),
            "small_inbound_edge_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_first_seen": None,
            "small_inbound_last_seen": None,
            "largest_outgoing_amount": 0.0,
            "largest_outgoing_tx_count": 0,
            "largest_outgoing_edge": None,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "largest_incoming_edge": None,
            "max_outgoing_concentration": 0.0,
            "max_incoming_concentration": 0.0,
            "ownership_first_seen": None,
            "control_node_count": 0,
        }

    @classmethod
    def _build_behavior_profiles(cls, nodes_by_key: dict[str, dict], edge_rows: list[dict]) -> dict[str, dict]:
        profiles: dict[str, dict] = collections.defaultdict(cls._empty_behavior_profile)
        sent_rows = [row for row in edge_rows if str(row.get("edge_type") or "").upper() == "SENT_TO"]
        outgoing_totals: collections.defaultdict[str, float] = collections.defaultdict(float)
        incoming_totals: collections.defaultdict[str, float] = collections.defaultdict(float)

        for row in sent_rows:
            amount = float(row["total_amount"] or 0.0)
            outgoing_totals[row["from_node_key"]] += amount
            incoming_totals[row["to_node_key"]] += amount

        for row in edge_rows:
            edge_type = str(row.get("edge_type") or "").upper()
            if edge_type in {"USES_ACCOUNT", "OWNS"}:
                profile = profiles[row["to_node_key"]]
                profile["control_node_count"] += 1
                first_seen = row.get("first_seen")
                if first_seen and (profile["ownership_first_seen"] is None or first_seen < profile["ownership_first_seen"]):
                    profile["ownership_first_seen"] = first_seen
                continue

            if edge_type != "SENT_TO":
                continue

            amount = float(row["total_amount"] or 0.0)
            tx_count = int(row["transaction_count"] or 0)
            avg_tx = amount / tx_count if tx_count > 0 else amount
            sender_profile = profiles[row["from_node_key"]]
            receiver_profile = profiles[row["to_node_key"]]

            sender_profile["total_outgoing_amount"] += amount
            sender_profile["outgoing_tx_count"] += tx_count
            sender_profile["outgoing_counterparties"].add(row["to_node_key"])
            receiver_profile["total_incoming_amount"] += amount
            receiver_profile["incoming_tx_count"] += tx_count
            receiver_profile["incoming_counterparties"].add(row["from_node_key"])

            sender_total = outgoing_totals[row["from_node_key"]]
            receiver_total = incoming_totals[row["to_node_key"]]
            outgoing_concentration = amount / sender_total if sender_total > 0 else 0.0
            incoming_concentration = amount / receiver_total if receiver_total > 0 else 0.0
            edge_summary = {
                "counterparty": row["to_node_key"],
                "source": row["from_node_key"],
                "edge_type": edge_type,
                "amount": amount,
                "transaction_count": tx_count,
                "average_transaction_value": avg_tx,
                "first_seen": row["first_seen"].isoformat() if row.get("first_seen") else None,
                "last_seen": row["last_seen"].isoformat() if row.get("last_seen") else None,
                "sender_total_outgoing_amount": sender_total,
                "receiver_total_incoming_amount": receiver_total,
                "outgoing_concentration": outgoing_concentration,
                "incoming_concentration": incoming_concentration,
            }

            if amount > sender_profile["largest_outgoing_amount"]:
                sender_profile["largest_outgoing_amount"] = amount
                sender_profile["largest_outgoing_tx_count"] = tx_count
                sender_profile["largest_outgoing_edge"] = edge_summary
            if amount > receiver_profile["largest_incoming_amount"]:
                receiver_profile["largest_incoming_amount"] = amount
                receiver_profile["largest_incoming_tx_count"] = tx_count
                receiver_profile["largest_incoming_edge"] = edge_summary
            sender_profile["max_outgoing_concentration"] = max(
                sender_profile["max_outgoing_concentration"],
                outgoing_concentration,
            )
            receiver_profile["max_incoming_concentration"] = max(
                receiver_profile["max_incoming_concentration"],
                incoming_concentration,
            )

            if avg_tx <= 150.0 and amount <= 2000.0:
                receiver_profile["small_inbound_edge_count"] += 1
                receiver_profile["small_inbound_total_amount"] += amount
                receiver_profile["small_inbound_tx_count"] += tx_count
                receiver_profile["small_inbound_counterparties"].add(row["from_node_key"])
                first_seen = row.get("first_seen")
                last_seen = row.get("last_seen")
                if first_seen and (
                    receiver_profile["small_inbound_first_seen"] is None
                    or first_seen < receiver_profile["small_inbound_first_seen"]
                ):
                    receiver_profile["small_inbound_first_seen"] = first_seen
                if last_seen and (
                    receiver_profile["small_inbound_last_seen"] is None
                    or last_seen > receiver_profile["small_inbound_last_seen"]
                ):
                    receiver_profile["small_inbound_last_seen"] = last_seen

        for profile in profiles.values():
            incoming = float(profile["total_incoming_amount"] or 0.0)
            outgoing = float(profile["total_outgoing_amount"] or 0.0)
            profile["pass_through_ratio"] = outgoing / incoming if incoming > 0 else 0.0
            profile["small_inbound_counterparty_count"] = len(profile["small_inbound_counterparties"])
            profile["incoming_counterparty_count"] = len(profile["incoming_counterparties"])
            profile["outgoing_counterparty_count"] = len(profile["outgoing_counterparties"])
            if profile["small_inbound_first_seen"] and profile["small_inbound_last_seen"]:
                profile["small_inbound_window_days"] = max(
                    0,
                    (profile["small_inbound_last_seen"] - profile["small_inbound_first_seen"]).days,
                )
            else:
                profile["small_inbound_window_days"] = None
            ownership_first_seen = profile.get("ownership_first_seen")
            profile["account_age_days"] = (
                (dt.date.today() - ownership_first_seen).days if ownership_first_seen else None
            )

        return profiles

    @staticmethod
    def _clamp_score(value: float) -> float:
        return min(1.0, max(0.0, value))

    @staticmethod
    def _severity(score_contribution: float) -> str:
        if score_contribution >= 0.90:
            return "CRITICAL"
        if score_contribution >= 0.55:
            return "HIGH"
        if score_contribution >= 0.30:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _path_depth(best_path: list[dict], best_depth: int | None) -> int:
        if best_depth is not None:
            return best_depth
        return max(0, len(best_path) - 1)

    @staticmethod
    def _path_semantics(best_path: list[dict]) -> list[str]:
        return [str(node.get("semantic_flow") or "") for node in best_path[1:]]

    @staticmethod
    def _path_reaches_sanctioned(best_path: list[dict]) -> bool:
        return any(str(node.get("risk_level") or "").upper() == "SANCTIONED" for node in best_path)

    @staticmethod
    def _path_has_proxy_behavior(best_path: list[dict]) -> bool:
        if len(best_path) >= 4:
            return True
        return any(str(node.get("edge_type") or "").upper() in {"USES_ACCOUNT", "OWNS"} for node in best_path[1:])

    def _transaction_pattern_factors(self, node_key: str) -> dict[str, Any]:
        profile = self.behavior_profiles_by_key.get(node_key, {})
        small_inbound_counterparty_count = int(profile.get("small_inbound_counterparty_count") or 0)
        small_inbound_total_amount = float(profile.get("small_inbound_total_amount") or 0.0)
        small_inbound_tx_count = int(profile.get("small_inbound_tx_count") or 0)
        largest_outgoing_edge = profile.get("largest_outgoing_edge") or {}
        largest_incoming_edge = profile.get("largest_incoming_edge") or {}
        pass_through_ratio = float(profile.get("pass_through_ratio") or 0.0)
        max_outgoing_concentration = float(profile.get("max_outgoing_concentration") or 0.0)
        max_incoming_concentration = float(profile.get("max_incoming_concentration") or 0.0)
        has_structuring = (
            small_inbound_counterparty_count >= 8
            and small_inbound_total_amount >= 10000.0
            and small_inbound_tx_count >= 100
            and float(profile.get("largest_outgoing_amount") or 0.0) >= 10000.0
            and pass_through_ratio >= 0.70
        )
        has_high_concentration = (
            max_outgoing_concentration >= 0.70
            and float(profile.get("largest_outgoing_amount") or 0.0) >= 10000.0
        ) or (
            max_incoming_concentration >= 0.70
            and float(profile.get("largest_incoming_amount") or 0.0) >= 10000.0
        )
        return {
            "has_structuring": has_structuring,
            "has_high_concentration": has_high_concentration,
            "small_inbound_counterparty_count": small_inbound_counterparty_count,
            "small_inbound_total_amount": round(small_inbound_total_amount, 4),
            "small_inbound_tx_count": small_inbound_tx_count,
            "small_inbound_window_days": profile.get("small_inbound_window_days"),
            "total_incoming_amount": round(float(profile.get("total_incoming_amount") or 0.0), 4),
            "total_outgoing_amount": round(float(profile.get("total_outgoing_amount") or 0.0), 4),
            "pass_through_ratio": round(pass_through_ratio, 4),
            "largest_outgoing_amount": round(float(profile.get("largest_outgoing_amount") or 0.0), 4),
            "largest_outgoing_tx_count": int(profile.get("largest_outgoing_tx_count") or 0),
            "largest_incoming_amount": round(float(profile.get("largest_incoming_amount") or 0.0), 4),
            "largest_incoming_tx_count": int(profile.get("largest_incoming_tx_count") or 0),
            "max_outgoing_concentration": round(max_outgoing_concentration, 6),
            "max_incoming_concentration": round(max_incoming_concentration, 6),
            "largest_outgoing_edge": largest_outgoing_edge,
            "largest_incoming_edge": largest_incoming_edge,
            "account_age_days": profile.get("account_age_days"),
        }

    @staticmethod
    def _path_has_abnormal_value_to_new_counterparty(best_path: list[dict]) -> bool:
        for node in best_path[1:]:
            first_seen = node.get("first_seen")
            last_seen = node.get("last_seen")
            amount = float(node.get("amount") or 0.0)
            tx_count = int(node.get("transaction_count") or 0)
            if not first_seen or not last_seen:
                continue
            try:
                first_seen_date = dt.date.fromisoformat(str(first_seen))
                last_seen_date = dt.date.fromisoformat(str(last_seen))
            except ValueError:
                continue
            if (dt.date.today() - first_seen_date).days <= 30 and (last_seen_date - first_seen_date).days <= 7:
                if amount >= 10000.0 and tx_count <= 3:
                    return True
        return False

    def _path_has_high_risk_corridor(self, source_risk_node: str | None) -> bool:
        source_country = str(self.nodes_by_key.get(source_risk_node or "", {}).get("country") or "").upper()
        return source_country in HIGH_RISK_COUNTRIES

    @staticmethod
    def _path_has_hub_discount(best_path: list[dict]) -> bool:
        if any(str(node.get("edge_type") or "").upper() == "SHARED_IDENTIFIER" for node in best_path[1:]):
            return True
        intermediary_types = {str(node.get("node_type") or "").upper() for node in best_path[1:-1]}
        return bool({"BANK"} & intermediary_types)

    @staticmethod
    def _path_has_old_exposure(best_path: list[dict]) -> bool:
        latest_age = None
        for node in best_path[1:]:
            last_seen = node.get("last_seen")
            if not last_seen:
                continue
            try:
                parsed = dt.date.fromisoformat(str(last_seen))
            except ValueError:
                continue
            age = (dt.date.today() - parsed).days
            if latest_age is None or age > latest_age:
                latest_age = age
        return latest_age is not None and latest_age > 180

    @staticmethod
    def _derived_anchor_context(best_path: list[dict]) -> dict[str, Any] | None:
        if len(best_path) < 2:
            return None
        anchor_step = best_path[1]
        if not anchor_step.get("derived_anchor"):
            return None
        last_seen = anchor_step.get("last_seen")
        time_decay = None
        if last_seen:
            try:
                parsed = dt.date.fromisoformat(str(last_seen))
                age_days = (dt.date.today() - parsed).days
                if age_days <= 30:
                    time_decay = 1.0
                elif age_days <= 90:
                    time_decay = 0.8
                elif age_days <= 180:
                    time_decay = 0.5
                else:
                    time_decay = 0.25
            except ValueError:
                time_decay = None
        return {
            "derived_anchor_node": anchor_step.get("derived_anchor_node") or anchor_step.get("node_key"),
            "derived_anchor_score": float(anchor_step.get("derived_anchor_score") or 0.0),
            "derived_anchor_reason_code": str(anchor_step.get("derived_anchor_reason_code") or ""),
            "derived_anchor_explanation": str(anchor_step.get("derived_anchor_explanation") or ""),
            "derived_anchor_original_score": float(anchor_step.get("derived_anchor_original_score") or 0.0),
            "suppression_reason": anchor_step.get("derived_suppression_reason"),
            "upstream_funding_edge": {
                "edge_type": anchor_step.get("edge_type"),
                "amount": round(float(anchor_step.get("amount") or 0.0), 4),
                "transaction_count": int(anchor_step.get("transaction_count") or 0),
                "flow_concentration": round(float(anchor_step.get("flow_concentration") or 0.0), 6),
                "flow_materiality_weight": round(float(anchor_step.get("flow_materiality_weight") or 0.0), 6),
                "directional_multiplier": round(float(anchor_step.get("directional_multiplier") or 1.0), 6),
                "first_seen": anchor_step.get("first_seen"),
                "last_seen": anchor_step.get("last_seen"),
                "time_decay": time_decay,
            },
        }

    @staticmethod
    def _path_edge_factors(best_path: list[dict]) -> list[dict[str, Any]]:
        factors: list[dict[str, Any]] = []
        for node in best_path[1:]:
            factors.append(
                {
                    "node_key": node.get("node_key"),
                    "edge_type": node.get("edge_type"),
                    "semantic_flow": node.get("semantic_flow"),
                    "amount": round(float(node.get("amount") or 0.0), 4),
                    "transaction_count": int(node.get("transaction_count") or 0),
                    "flow_concentration": round(float(node.get("flow_concentration") or 0.0), 6),
                    "flow_materiality_weight": round(float(node.get("flow_materiality_weight") or 0.0), 6),
                    "directional_multiplier": round(float(node.get("directional_multiplier") or 1.0), 6),
                    "first_seen": node.get("first_seen"),
                    "last_seen": node.get("last_seen"),
                }
            )
        return factors

    def _current_node_derived_anchor_factors(
        self,
        *,
        node_key: str,
        best_path: list[dict],
        primary_reason_code: str | None,
        source_risk_level: str,
    ) -> dict[str, Any] | None:
        if primary_reason_code not in {
            "OUTBOUND_1_HOP_TO_SANCTIONED",
            "OUTBOUND_2_HOP_TO_SANCTIONED",
            "INBOUND_FROM_SANCTIONED",
            "PROXY_ACCOUNT_BEHAVIOR",
        }:
            return None
        if str(source_risk_level or "").upper() != "SANCTIONED":
            return None
        if self._path_has_hub_discount(best_path) or self._path_has_old_exposure(best_path):
            return None
        pattern = self._transaction_pattern_factors(node_key)
        return {
            "derived_anchor_node": node_key,
            "derived_anchor_reason_code": primary_reason_code,
            "derived_anchor_original_score": 0.0,
            "derived_anchor_score": 0.70 if primary_reason_code == "OUTBOUND_1_HOP_TO_SANCTIONED" else (
                0.55 if primary_reason_code in {"OUTBOUND_2_HOP_TO_SANCTIONED", "INBOUND_FROM_SANCTIONED"} else 0.35
            ),
            "derived_anchor_explanation": (
                "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass."
            ),
            "behavior_factors": pattern,
        }

    def _decision_factors(
        self,
        *,
        node_key: str,
        best_path: list[dict],
        primary_reason_code: str | None,
        source_risk_level: str,
    ) -> dict[str, Any]:
        behavior = self._transaction_pattern_factors(node_key)
        payload: dict[str, Any] = {
            **behavior,
            "path_edge_factors": self._path_edge_factors(best_path),
        }
        derived_context = self._derived_anchor_context(best_path)
        if derived_context is not None:
            payload["derived_anchor_context"] = derived_context
        else:
            current_anchor = self._current_node_derived_anchor_factors(
                node_key=node_key,
                best_path=best_path,
                primary_reason_code=primary_reason_code,
                source_risk_level=source_risk_level,
            )
            if current_anchor is not None:
                payload["derived_anchor_context"] = current_anchor
        return payload

    def _primary_path_evidence(
        self,
        *,
        direct_hit: bool,
        risk_level: str | None,
        source_risk_level: str,
        node_key: str,
        best_depth: int | None,
        best_path: list[dict],
    ) -> tuple[str | None, float, str]:
        depth = self._path_depth(best_path, best_depth)
        sanctioned_path = self._path_reaches_sanctioned(best_path)
        semantics = self._path_semantics(best_path)
        all_outbound = bool(semantics) and all(item == "outbound_to_anchor" for item in semantics)
        all_inbound = bool(semantics) and all(item == "inbound_from_anchor" for item in semantics)
        derived_context = self._derived_anchor_context(best_path)
        if direct_hit and str(risk_level or "").upper() == "SANCTIONED":
            return (
                "DIRECT_SANCTIONS_MATCH",
                1.0,
                "Recipient account is directly matched to a sanctioned account.",
            )
        if not best_path:
            return (None, 0.0, "No transaction-graph exposure evidence was found.")
        if derived_context is not None:
            suppression_reason = str(derived_context.get("suppression_reason") or "")
            if suppression_reason:
                return (
                    "DERIVED_RISK_PROPAGATION_SUPPRESSED",
                    0.08,
                    "Upstream funding reached a derived sanctions-proxy account, but the second-pass propagation was suppressed "
                    f"because {suppression_reason.lower().replace('_', ' ')}.",
                )
            anchor_score = float(derived_context.get("derived_anchor_score") or 0.0)
            funding_edge = derived_context.get("upstream_funding_edge") or {}
            base_score = 0.46 if anchor_score >= 0.70 else 0.38 if anchor_score >= 0.55 else 0.24
            return (
                "UPSTREAM_FUNDING_OF_DERIVED_SANCTIONS_PROXY",
                base_score,
                "Beneficiary directly funded an account that was already proven offline to behave like a sanctions proxy "
                f"through {derived_context.get('derived_anchor_reason_code') or 'derived-anchor'} evidence.",
            )
        if is_old_tiny_exposure(best_path):
            return (
                "OLD_EXPOSURE_DISCOUNTED",
                0.05,
                "Only old or immaterial exposure was found, so it was discounted.",
            )
        if sanctioned_path and all_outbound:
            if depth <= 1:
                return (
                    "OUTBOUND_1_HOP_TO_SANCTIONED",
                    0.82,
                    "Beneficiary connects to a sanctioned entity through a direct outbound payment path.",
                )
            return (
                "OUTBOUND_2_HOP_TO_SANCTIONED",
                0.62,
                "Beneficiary connects to a sanctioned entity through a two-hop outbound payment route.",
            )
        if sanctioned_path and all_inbound:
            return (
                "INBOUND_FROM_SANCTIONED",
                0.48,
                "Beneficiary received value through a path originating from a sanctioned entity.",
            )
        if sanctioned_path:
            return (
                "SHARED_INTERMEDIARY_WITH_SANCTIONED",
                0.20,
                "Beneficiary shares an intermediary relationship with a sanctioned entity, but the path is weaker than a clean directional flow.",
            )
        if str(source_risk_level or "NONE").upper() == "SUSPICIOUS":
            return (
                "PROXY_ACCOUNT_BEHAVIOR",
                0.44,
                "Path structure is consistent with proxy or pass-through account behavior near a suspicious anchor.",
            )
        if self._path_has_abnormal_value_to_new_counterparty(best_path):
            return (
                "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
                0.38,
                "A large recent transfer to a newly observed counterparty was detected.",
            )
        if self._path_has_proxy_behavior(best_path):
            return (
                "PROXY_ACCOUNT_BEHAVIOR",
                0.40,
                "Path structure is consistent with proxy or pass-through account behavior.",
            )
        return (
            "HIGH_RISK_CORRIDOR",
            0.34,
            "The strongest route includes a corridor associated with elevated sanctions risk.",
        )

    def _supplemental_evidence(
        self,
        *,
        node_key: str,
        source_risk_level: str,
        source_risk_node: str | None,
        best_path: list[dict],
        primary_reason_code: str | None,
    ) -> list[tuple[str, float, str]]:
        evidence: list[tuple[str, float, str]] = []
        behavior_factors = self._transaction_pattern_factors(node_key)
        derived_context = self._derived_anchor_context(best_path)
        current_anchor = self._current_node_derived_anchor_factors(
            node_key=node_key,
            best_path=best_path,
            primary_reason_code=primary_reason_code,
            source_risk_level=source_risk_level,
        )
        if not best_path and derived_context is None:
            return evidence
        if derived_context is not None and primary_reason_code != "DERIVED_RISK_PROPAGATION_SUPPRESSED":
            evidence.append(
                (
                    "PROXY_CHAIN_FUNDING",
                    0.08,
                    "Funding a derived sanctions-proxy account strengthens the proxy-network evasion hypothesis.",
                )
            )
            evidence.append(
                (
                    "DERIVED_RISK_ANCHOR",
                    0.04,
                    "The immediate counterparty was precomputed offline as a derived sanctions-risk anchor before runtime lookup.",
                )
            )
        elif current_anchor is not None:
            evidence.append(
                (
                    "DERIVED_RISK_ANCHOR",
                    0.04,
                    "This account itself qualifies as a derived sanctions-risk anchor for a later controlled upstream-funding pass.",
                )
            )
        if (
            self._path_has_proxy_behavior(best_path)
            or behavior_factors["has_structuring"]
            or behavior_factors["has_high_concentration"]
        ) and primary_reason_code != "PROXY_ACCOUNT_BEHAVIOR":
            explanation = "Intermediary or pass-through account behavior increases sanctions-evasion concern."
            if behavior_factors["has_structuring"]:
                explanation = (
                    "Many small inbound transfers aggregated into the account before a rapid large outbound transfer, "
                    "which is consistent with proxy pass-through structuring."
                )
            elif behavior_factors["has_high_concentration"]:
                explanation = (
                    "A high share of incoming or outgoing value concentrates through one account relationship, "
                    "which is consistent with proxy routing."
                )
            evidence.append(
                (
                    "PROXY_ACCOUNT_BEHAVIOR",
                    0.10,
                    explanation,
                )
            )
        if self._path_has_abnormal_value_to_new_counterparty(best_path) and primary_reason_code != "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY":
            evidence.append(
                (
                    "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
                    0.08,
                    "A large recent transfer to a new counterparty increases concern.",
                )
            )
        if self._path_has_high_risk_corridor(source_risk_node) and primary_reason_code != "HIGH_RISK_CORRIDOR":
            evidence.append(
                (
                    "HIGH_RISK_CORRIDOR",
                    0.06,
                    "The route touches a jurisdiction associated with elevated sanctions-evasion risk.",
                )
            )
        if self._path_has_hub_discount(best_path):
            evidence.append(
                (
                    "HUB_PATH_DISCOUNTED",
                    -0.12,
                    "A shared hub or identifier weakens the path as direct evidence of sanctions evasion.",
                )
            )
        if self._path_has_old_exposure(best_path):
            evidence.append(
                (
                    "OLD_EXPOSURE_DISCOUNTED",
                    -0.10,
                    "The strongest observed route is stale and therefore discounted.",
                )
            )
        return evidence

    def _build_evidence(
        self,
        *,
        direct_hit: bool,
        risk_level: str | None,
        source_risk_level: str,
        node_key: str,
        source_risk_node: str | None,
        best_depth: int | None,
        best_path: list[dict],
    ) -> tuple[list[dict], float, str]:
        primary_reason_code, primary_score, primary_explanation = self._primary_path_evidence(
            direct_hit=direct_hit,
            risk_level=risk_level,
            source_risk_level=source_risk_level,
            node_key=node_key,
            best_depth=best_depth,
            best_path=best_path,
        )
        evidence: list[dict] = []
        total_score = primary_score
        if primary_reason_code is not None:
            evidence.append(
                {
                    "reason_code": primary_reason_code,
                    "severity": self._severity(primary_score),
                    "score_contribution": round(primary_score, 4),
                    "path": best_path,
                    "explanation": primary_explanation,
                    "decision_factors": self._decision_factors(
                        node_key=node_key,
                        best_path=best_path,
                        primary_reason_code=primary_reason_code,
                        source_risk_level=source_risk_level,
                    )
                    if primary_reason_code is not None
                    else {},
                }
            )
        for reason_code, contribution, explanation in self._supplemental_evidence(
            node_key=node_key,
            source_risk_level=source_risk_level,
            source_risk_node=source_risk_node,
            best_path=best_path,
            primary_reason_code=primary_reason_code,
        ):
            total_score += contribution
            evidence.append(
                {
                    "reason_code": reason_code,
                    "severity": self._severity(abs(contribution)),
                    "score_contribution": round(contribution, 4),
                    "path": best_path,
                    "explanation": explanation,
                    "decision_factors": self._decision_factors(
                        node_key=node_key,
                        best_path=best_path,
                        primary_reason_code=primary_reason_code,
                        source_risk_level=source_risk_level,
                    )
                    if reason_code in {
                        "PROXY_ACCOUNT_BEHAVIOR",
                        "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
                        "DERIVED_RISK_ANCHOR",
                        "PROXY_CHAIN_FUNDING",
                        "DERIVED_RISK_PROPAGATION_SUPPRESSED",
                    }
                    else {},
                }
            )
        total_score = self._clamp_score(total_score)
        primary_reason = primary_explanation if primary_reason_code is not None else "No transaction-graph exposure evidence was found."
        return evidence, total_score, primary_reason

    @staticmethod
    def _build_rule_triggers(evidence: list[dict]) -> list[str]:
        if not evidence:
            return ["NO_EXPOSURE_INDEX_ENTRY"]
        return list(dict.fromkeys(str(item["reason_code"]) for item in evidence))

    def screen_account(self, node_key: str, *, review_threshold: float | None = None) -> AccountScreeningResult:
        """Score one account-like node using only the precomputed exposure index."""
        del review_threshold
        t0 = time.perf_counter()
        node = self.nodes_by_key.get(node_key)
        exposure = self.exposures_by_key.get(node_key)
        node_type = node.get("node_type") if node else None
        risk_level = node.get("risk_level") if node else None
        direct_hit = bool(
            node
            and str(risk_level or "").upper() == "SANCTIONED"
            and str(node_type or "").upper() in ACCOUNT_NODE_TYPES
        )
        graph_score = min(1.0, max(0.0, float(exposure["exposure_score"]) if exposure else 0.0))
        best_depth = exposure["best_depth"] if exposure else None
        best_path = list(exposure["best_path"]) if exposure else []
        source_node = self.nodes_by_key.get(exposure["source_risk_node"], {}) if exposure else {}
        source_risk_level = str(source_node.get("risk_level") or "NONE").upper()
        source_node_type = source_node.get("node_type")
        evidence, risk_score, primary_reason = self._build_evidence(
            direct_hit=direct_hit,
            risk_level=risk_level,
            source_risk_level=source_risk_level,
            node_key=node_key,
            source_risk_node=exposure["source_risk_node"] if exposure else None,
            best_depth=best_depth,
            best_path=best_path,
        )
        verdict = VerdictType.MATCH if direct_hit else (
            VerdictType.REVIEW if risk_score >= REVIEW_RISK_SCORE_THRESHOLD else VerdictType.NO_MATCH
        )
        rule_triggers = self._build_rule_triggers(evidence)
        return AccountScreeningResult(
            module="account_exposure",
            node_key=node_key,
            score=graph_score,
            exposure_score=graph_score,
            graph_exposure_score=graph_score,
            risk_score=risk_score,
            sanctions_evasion_score=risk_score,
            recommended_action=verdict,
            verdict=verdict,
            risk_type=RISK_TYPE,
            evasion_typology=EVASION_TYPOLOGY,
            source_risk_level=source_risk_level,
            source_node_type=source_node_type,
            rule_triggers=rule_triggers,
            best_depth=best_depth,
            direct_hit=direct_hit,
            node_type=node_type,
            risk_level=risk_level,
            source_risk_node=exposure["source_risk_node"] if exposure else None,
            best_path=best_path,
            primary_reason=primary_reason,
            reason=primary_reason,
            evidence=evidence,
            evidence_package=evidence,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


def _print_result(result: AccountScreeningResult) -> None:
    print(f"Module: {result.module}")
    print(f"Recommended action: {result.recommended_action.value}")
    print(f"Graph exposure score: {result.graph_exposure_score:.4f}")
    print(f"Sanctions evasion score: {result.sanctions_evasion_score:.4f}")
    print(f"Risk type: {result.risk_type}")
    print(f"Primary reason: {result.primary_reason}")
    print(f"Source risk level: {result.source_risk_level}")
    print(f"Rule triggers: {', '.join(result.rule_triggers) if result.rule_triggers else '-'}")
    print("Evidence:")
    print(json.dumps(result.evidence, indent=2))
    print(f"Latency: {result.latency_ms:.4f} ms")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iban", default="")
    parser.add_argument("--account-number", default="")
    parser.add_argument("--threshold", type=float, default=DEFAULT_REVIEW_THRESHOLD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    node_key = args.iban or args.account_number
    if not node_key:
        raise SystemExit("Provide --iban or --account-number.")
    lookup = AccountExposureLookup.load()
    _print_result(lookup.screen_account(node_key, review_threshold=args.threshold))


if __name__ == "__main__":
    main()
