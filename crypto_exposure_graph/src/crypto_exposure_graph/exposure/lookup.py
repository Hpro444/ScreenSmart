"""Realtime crypto wallet exposure lookup over precomputed data only.

This module performs O(1)-style lookups against `crypto_graph_nodes` and
`crypto_exposure_index`. It does not traverse `crypto_graph_edges` and does not
run BFS online.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import json
import time

import sqlalchemy as sa

from ..db.database import get_engine
from ..db.schema import crypto_exposure_index, crypto_graph_edges, crypto_graph_nodes
from ..domain.enums import VerdictType
from .policy import SERVICE_BOUNDARY_NODE_TYPES
from .scoring import (
    DEFAULT_REVIEW_THRESHOLD,
    HIGH_DEGREE_SMART_CONTRACT_THRESHOLD,
    ignore_isolated_dust_edge,
    is_low_value_structuring_pattern,
    source_risk,
)

RISK_TYPE = "SANCTIONS_EVASION"
EVASION_TYPOLOGY = "PROXY_NETWORK"
REVIEW_RISK_SCORE_THRESHOLD = 0.30


@dataclasses.dataclass(frozen=True)
class CryptoWalletScreeningResult:
    """Final payload returned by the realtime crypto wallet lookup path."""

    module: str
    chain: str
    wallet_address: str
    score: float
    graph_exposure_score: float
    risk_score: float
    sanctions_evasion_score: float
    recommended_action: VerdictType
    verdict: VerdictType
    risk_type: str
    evasion_typology: str
    direct_hit: bool
    source_risk_level: str
    source_risk_node: str | None
    best_depth: int | None
    best_path: list[dict]
    rule_triggers: list[str]
    primary_reason: str
    reason: str
    evidence: list[dict]
    evidence_package: list[dict]
    latency_ms: float


class CryptoWalletExposureLookup:
    """Realtime reader over precomputed crypto wallet exposure data."""

    def __init__(
        self,
        nodes_by_key: dict[str, dict],
        exposures_by_key: dict[str, dict],
        guard_hints_by_key: dict[str, set[str]],
    ) -> None:
        self.nodes_by_key = nodes_by_key
        self.exposures_by_key = exposures_by_key
        self.guard_hints_by_key = guard_hints_by_key

    @staticmethod
    def _node_key(chain: str, wallet_address: str) -> str:
        return f"{str(chain or '').upper()}:{str(wallet_address or '').lower()}"

    @classmethod
    def load(cls, engine=None) -> "CryptoWalletExposureLookup":
        """Hydrate the in-memory lookup tables from Postgres."""
        engine = engine or get_engine()
        nodes_by_key: dict[str, dict] = {}
        exposures_by_key: dict[str, dict] = {}
        edge_rows: list[dict] = []
        with engine.connect() as conn:
            for row in conn.execute(
                sa.select(
                    crypto_graph_nodes.c.node_key,
                    crypto_graph_nodes.c.chain,
                    crypto_graph_nodes.c.address,
                    crypto_graph_nodes.c.node_type,
                    crypto_graph_nodes.c.display_name,
                    crypto_graph_nodes.c.risk_level,
                )
            ):
                nodes_by_key[row.node_key] = {
                    "node_key": row.node_key,
                    "chain": row.chain,
                    "address": row.address,
                    "node_type": row.node_type,
                    "display_name": row.display_name,
                    "risk_level": row.risk_level,
                }

            for row in conn.execute(
                sa.select(
                    crypto_exposure_index.c.node_key,
                    crypto_exposure_index.c.exposure_score,
                    crypto_exposure_index.c.best_depth,
                    crypto_exposure_index.c.best_path,
                    crypto_exposure_index.c.source_risk_node,
                    crypto_exposure_index.c.reason,
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
                    crypto_graph_edges.c.from_node_key,
                    crypto_graph_edges.c.to_node_key,
                    crypto_graph_edges.c.edge_type,
                    crypto_graph_edges.c.total_usd_value,
                    crypto_graph_edges.c.transaction_count,
                    crypto_graph_edges.c.first_seen,
                    crypto_graph_edges.c.last_seen,
                    crypto_graph_edges.c.confidence,
                )
            ):
                edge_rows.append(
                    {
                        "from_node_key": row.from_node_key,
                        "to_node_key": row.to_node_key,
                        "edge_type": row.edge_type,
                        "total_usd_value": float(row.total_usd_value or 0.0),
                        "transaction_count": int(row.transaction_count or 0),
                        "first_seen": row.first_seen,
                        "last_seen": row.last_seen,
                        "confidence": float(row.confidence or 1.0),
                    }
                )

        guard_hints_by_key = cls._build_guard_hints(nodes_by_key, edge_rows)
        return cls(nodes_by_key, exposures_by_key, guard_hints_by_key)

    @staticmethod
    def _build_guard_hints(nodes_by_key: dict[str, dict], edge_rows: list[dict]) -> dict[str, set[str]]:
        """Build O(1) hints for guarded no-exposure cases."""
        guard_hints_by_key: dict[str, set[str]] = collections.defaultdict(set)
        node_degree: collections.Counter[str] = collections.Counter()
        for edge in edge_rows:
            node_degree[edge["from_node_key"]] += 1
            node_degree[edge["to_node_key"]] += 1

        risky_service_nodes: set[str] = set()
        for edge in edge_rows:
            from_node = nodes_by_key.get(edge["from_node_key"], {})
            to_node = nodes_by_key.get(edge["to_node_key"], {})
            from_risk = source_risk(str(from_node.get("risk_level") or "NONE"))
            to_risk = source_risk(str(to_node.get("risk_level") or "NONE"))
            if str(to_node.get("node_type") or "").upper() in SERVICE_BOUNDARY_NODE_TYPES and from_risk > 0.0:
                risky_service_nodes.add(edge["to_node_key"])
            if str(from_node.get("node_type") or "").upper() in SERVICE_BOUNDARY_NODE_TYPES and to_risk > 0.0:
                risky_service_nodes.add(edge["from_node_key"])
            if (
                from_risk > 0.0
                and str(to_node.get("node_type") or "").upper() == "WALLET"
                and ignore_isolated_dust_edge(edge)
            ):
                guard_hints_by_key[edge["to_node_key"]].add("DUST_EXPOSURE_IGNORED")

        def add_service_hints(wallet_key: str, service_key: str) -> None:
            service_node = nodes_by_key.get(service_key, {})
            service_type = str(service_node.get("node_type") or "").upper()
            guard_hints_by_key[wallet_key].add("SERVICE_NODE_PROPAGATION_STOPPED")
            if service_type == "EXCHANGE_HOT_WALLET":
                guard_hints_by_key[wallet_key].add("EXCHANGE_CONTAMINATION_PREVENTED")
            if service_type == "SMART_CONTRACT" and node_degree[service_key] >= HIGH_DEGREE_SMART_CONTRACT_THRESHOLD:
                guard_hints_by_key[wallet_key].add("HUB_PROPAGATION_SUPPRESSED")

        for edge in edge_rows:
            from_type = str(nodes_by_key.get(edge["from_node_key"], {}).get("node_type") or "").upper()
            to_type = str(nodes_by_key.get(edge["to_node_key"], {}).get("node_type") or "").upper()
            if edge["from_node_key"] in risky_service_nodes and to_type == "WALLET":
                add_service_hints(edge["to_node_key"], edge["from_node_key"])
            if edge["to_node_key"] in risky_service_nodes and from_type == "WALLET":
                add_service_hints(edge["from_node_key"], edge["to_node_key"])

        return guard_hints_by_key

    @staticmethod
    def _path_depth(best_path: list[dict], best_depth: int | None) -> int:
        if best_depth is not None:
            return best_depth
        return max(0, len(best_path) - 1)

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
    def _path_semantics(best_path: list[dict]) -> list[str]:
        return [str(node.get("semantic_flow") or "") for node in best_path[1:]]

    def _path_has_old_exposure(self, best_path: list[dict]) -> bool:
        oldest_recent_days = None
        for node in best_path[1:]:
            last_seen = node.get("last_seen")
            if not last_seen:
                continue
            try:
                parsed = dt.date.fromisoformat(str(last_seen))
                age = (dt.date.today() - parsed).days
            except ValueError:
                continue
            if oldest_recent_days is None or age > oldest_recent_days:
                oldest_recent_days = age
        return oldest_recent_days is not None and oldest_recent_days > 180

    @staticmethod
    def _derived_anchor_context(best_path: list[dict]) -> dict | None:
        if len(best_path) < 2:
            return None
        anchor_step = best_path[1]
        if not anchor_step.get("derived_anchor"):
            return None
        time_decay = None
        last_seen = anchor_step.get("last_seen")
        if last_seen:
            try:
                parsed = dt.date.fromisoformat(str(last_seen))
                age_days = (dt.date.today() - parsed).days
                if age_days <= 7:
                    time_decay = 1.0
                elif age_days <= 30:
                    time_decay = 0.8
                elif age_days <= 180:
                    time_decay = 0.4
                else:
                    time_decay = 0.1
            except ValueError:
                time_decay = None
        return {
            "derived_anchor_wallet": anchor_step.get("derived_anchor_node") or anchor_step.get("node_key"),
            "derived_anchor_score": float(anchor_step.get("derived_anchor_score") or 0.0),
            "derived_anchor_reason_code": str(anchor_step.get("derived_anchor_reason_code") or ""),
            "derived_anchor_explanation": str(anchor_step.get("derived_anchor_explanation") or ""),
            "derived_anchor_original_score": float(anchor_step.get("derived_anchor_original_score") or 0.0),
            "suppression_reason": anchor_step.get("derived_suppression_reason"),
            "upstream_funding_edge": {
                "edge_type": anchor_step.get("edge_type"),
                "amount_usd": round(float(anchor_step.get("total_usd_value") or 0.0), 4),
                "transaction_count": int(anchor_step.get("transaction_count") or 0),
                "average_transaction_value": round(float(anchor_step.get("average_transaction_value") or 0.0), 6),
                "flow_concentration": round(float(anchor_step.get("flow_concentration") or 0.0), 6),
                "crypto_materiality_weight": round(float(anchor_step.get("crypto_materiality_weight") or 0.0), 6),
                "concentration_score": round(float(anchor_step.get("concentration_score") or 0.0), 6),
                "hub_penalty": round(float(anchor_step.get("hub_penalty") or 0.0), 6),
                "directional_multiplier": round(float(anchor_step.get("directional_multiplier") or 1.0), 6),
                "chain": anchor_step.get("chain"),
                "asset": anchor_step.get("asset"),
                "first_seen": anchor_step.get("first_seen"),
                "last_seen": anchor_step.get("last_seen"),
                "time_decay": time_decay,
            },
        }

    @staticmethod
    def _path_edge_factors(best_path: list[dict]) -> list[dict]:
        return [
            {
                "node_key": node.get("node_key"),
                "edge_type": node.get("edge_type"),
                "semantic_flow": node.get("semantic_flow"),
                "total_usd_value": round(float(node.get("total_usd_value") or 0.0), 4),
                "transaction_count": int(node.get("transaction_count") or 0),
                "average_transaction_value": round(float(node.get("average_transaction_value") or 0.0), 6),
                "flow_concentration": round(float(node.get("flow_concentration") or 0.0), 6),
                "crypto_materiality_weight": round(float(node.get("crypto_materiality_weight") or 0.0), 6),
                "concentration_score": round(float(node.get("concentration_score") or 0.0), 6),
                "hub_penalty": round(float(node.get("hub_penalty") or 0.0), 6),
                "directional_multiplier": round(float(node.get("directional_multiplier") or 1.0), 6),
                "first_seen": node.get("first_seen"),
                "last_seen": node.get("last_seen"),
            }
            for node in best_path[1:]
        ]

    def _current_node_derived_anchor_factors(
        self,
        *,
        node_key: str,
        best_path: list[dict],
        primary_reason_code: str | None,
        source_risk_level: str,
    ) -> dict | None:
        if primary_reason_code not in {
            "OUTBOUND_1_HOP_TO_SANCTIONED",
            "OUTBOUND_2_HOP_TO_SANCTIONED",
            "INBOUND_FROM_SANCTIONED",
            "PROXY_ACCOUNT_BEHAVIOR",
        }:
            return None
        if str(self.nodes_by_key.get(node_key, {}).get("node_type") or "").upper() != "WALLET":
            return None
        if self._path_has_hub_discount(best_path, node_key) or self._path_has_old_exposure(best_path):
            return None
        if str(source_risk_level or "").upper() not in {"SANCTIONED", "RANSOMWARE", "SCAM", "HACK_PROCEEDS", "SUSPICIOUS"}:
            return None
        return {
            "derived_anchor_wallet": node_key,
            "derived_anchor_reason_code": primary_reason_code,
            "derived_anchor_original_score": 0.0,
            "derived_anchor_score": 0.70 if primary_reason_code == "OUTBOUND_1_HOP_TO_SANCTIONED" else (
                0.55 if primary_reason_code in {"OUTBOUND_2_HOP_TO_SANCTIONED", "INBOUND_FROM_SANCTIONED"} else 0.35
            ),
            "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass.",
        }

    def _decision_factors(
        self,
        *,
        node_key: str,
        best_path: list[dict],
        primary_reason_code: str | None,
        source_risk_level: str,
        chain: str | None,
        asset: str | None,
        amount_usd: float | None,
    ) -> dict:
        payload = {
            "path_edge_factors": self._path_edge_factors(best_path),
            "chain": str(chain or "").upper() if chain else None,
            "asset": asset,
            "amount_usd": round(float(amount_usd or 0.0), 4) if amount_usd is not None else None,
            "guard_hints": sorted(self.guard_hints_by_key.get(node_key, set())),
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

    def _path_has_hub_discount(self, best_path: list[dict], node_key: str) -> bool:
        guard_hints = self.guard_hints_by_key.get(node_key, set())
        if {"EXCHANGE_CONTAMINATION_PREVENTED", "HUB_PROPAGATION_SUPPRESSED", "SERVICE_NODE_PROPAGATION_STOPPED"} & guard_hints:
            return True
        for node in best_path:
            if str(node.get("node_type") or "").upper() in SERVICE_BOUNDARY_NODE_TYPES:
                return True
        return any(str(node.get("semantic_flow") or "") == "service_boundary" for node in best_path[1:])

    @staticmethod
    def _path_has_proxy_behavior(best_path: list[dict]) -> bool:
        if len(best_path) >= 3:
            return True
        for node in best_path[1:]:
            edge_type = str(node.get("edge_type") or "").upper()
            if edge_type in {"USED_MIXER", "BRIDGED_TO"}:
                return True
            if is_low_value_structuring_pattern(node):
                return True
        return False

    @staticmethod
    def _path_has_abnormal_value_to_new_counterparty(best_path: list[dict]) -> bool:
        import datetime as dt

        for node in best_path[1:]:
            first_seen = node.get("first_seen")
            last_seen = node.get("last_seen")
            amount = float(node.get("total_usd_value") or 0.0)
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

    @staticmethod
    def _path_has_high_risk_corridor(best_path: list[dict]) -> bool:
        return any(str(node.get("edge_type") or "").upper() == "BRIDGED_TO" for node in best_path[1:])

    @staticmethod
    def _path_reaches_sanctioned(best_path: list[dict]) -> bool:
        return any(str(node.get("risk_level") or "").upper() == "SANCTIONED" for node in best_path)

    def _primary_path_evidence(
        self,
        *,
        node_key: str,
        direct_hit: bool,
        risk_level: str | None,
        source_risk_level: str,
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
                "SANCTIONED_WALLET_MATCH",
                1.0,
                "Wallet is directly listed as a sanctioned wallet.",
            )
        if not best_path:
            guard_hints = self.guard_hints_by_key.get(node_key, set())
            if "DUST_EXPOSURE_IGNORED" in guard_hints:
                return (
                    "DUST_EXPOSURE_DISCOUNTED",
                    0.02,
                    "Only isolated dust-level crypto exposure was observed and discounted.",
                )
            if guard_hints:
                return (
                    "HUB_PATH_DISCOUNTED",
                    0.06,
                    "Only shared service or hub connectivity was observed, so the path was discounted.",
                )
            return (None, 0.0, "No crypto exposure evidence was found.")
        if derived_context is not None:
            suppression_reason = str(derived_context.get("suppression_reason") or "")
            if suppression_reason:
                return (
                    "CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED",
                    0.08,
                    "Upstream funding reached a derived crypto sanctions-proxy wallet, but second-pass propagation was suppressed "
                    f"because {suppression_reason.lower().replace('_', ' ')}.",
                )
            anchor_score = float(derived_context.get("derived_anchor_score") or 0.0)
            base_score = 0.46 if anchor_score >= 0.70 else 0.38 if anchor_score >= 0.55 else 0.24
            return (
                "UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY",
                base_score,
                "Wallet directly funded a wallet that was already proven offline to behave like a crypto sanctions proxy "
                f"through {derived_context.get('derived_anchor_reason_code') or 'derived-anchor'} evidence.",
            )
        if sanctioned_path and all_outbound:
            if depth <= 1:
                return (
                    "OUTBOUND_1_HOP_TO_SANCTIONED",
                    0.82,
                    "Wallet is one hop away from a sanctioned counterparty through an outbound payment path.",
                )
            return (
                "OUTBOUND_2_HOP_TO_SANCTIONED",
                0.62,
                "Wallet is connected to a sanctioned counterparty through a two-hop outbound route.",
            )
        if sanctioned_path and all_inbound:
            return (
                "INBOUND_FROM_SANCTIONED",
                0.48,
                "Wallet received funds through a path originating from a sanctioned source.",
            )
        if sanctioned_path:
            return (
                "SHARED_INTERMEDIARY_WITH_SANCTIONED",
                0.20,
                "Wallet shares an intermediary path with a sanctioned source, but the evidence is weaker than a direct directional route.",
            )
        if str(source_risk_level or "NONE").upper() in {"RANSOMWARE", "HACK_PROCEEDS", "SCAM", "SUSPICIOUS", "MIXER"}:
            return (
                "PROXY_ACCOUNT_BEHAVIOR",
                0.44,
                "Wallet behavior is consistent with proxy or pass-through routing near a high-risk crypto source.",
            )
        if self._path_has_abnormal_value_to_new_counterparty(best_path):
            return (
                "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
                0.38,
                "A large value movement to a newly observed counterparty was detected near the risky source.",
            )
        if self._path_has_high_risk_corridor(best_path):
            return (
                "HIGH_RISK_CORRIDOR",
                0.36,
                "The path uses a cross-bridge corridor associated with elevated sanctions-evasion risk.",
            )
        return (
            "PROXY_ACCOUNT_BEHAVIOR",
            0.32,
            "Wallet is close to a risky cluster through behavior consistent with proxy-network routing.",
        )

    def _supplemental_evidence(
        self,
        *,
        node_key: str,
        source_risk_level: str,
        best_path: list[dict],
        primary_reason_code: str | None,
    ) -> list[tuple[str, float, str]]:
        evidence: list[tuple[str, float, str]] = []
        derived_context = self._derived_anchor_context(best_path)
        current_anchor = self._current_node_derived_anchor_factors(
            node_key=node_key,
            best_path=best_path,
            primary_reason_code=primary_reason_code,
            source_risk_level=source_risk_level,
        )
        if not best_path and derived_context is None:
            return evidence
        if derived_context is not None and primary_reason_code != "CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED":
            evidence.append(
                (
                    "CRYPTO_PROXY_CHAIN_FUNDING",
                    0.08,
                    "Funding a derived crypto sanctions-proxy wallet strengthens the proxy-network evasion hypothesis.",
                )
            )
            evidence.append(
                (
                    "CRYPTO_DERIVED_RISK_ANCHOR",
                    0.04,
                    "The immediate counterparty was precomputed offline as a derived crypto sanctions-risk anchor.",
                )
            )
        elif current_anchor is not None:
            evidence.append(
                (
                    "CRYPTO_DERIVED_RISK_ANCHOR",
                    0.04,
                    "This wallet itself qualifies as a derived crypto sanctions-risk anchor for a later controlled upstream-funding pass.",
                )
            )
        if self._path_has_proxy_behavior(best_path) and primary_reason_code != "PROXY_ACCOUNT_BEHAVIOR":
            evidence.append(
                (
                    "PROXY_ACCOUNT_BEHAVIOR",
                    0.10,
                    "Intermediary routing, bridge usage, or pass-through behavior increases sanctions-evasion concern.",
                )
            )
        if self._path_has_abnormal_value_to_new_counterparty(best_path) and primary_reason_code != "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY":
            evidence.append(
                (
                    "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
                    0.08,
                    "A large recent transfer to a newly observed counterparty increases concern.",
                )
            )
        if self._path_has_high_risk_corridor(best_path) and primary_reason_code != "HIGH_RISK_CORRIDOR":
            evidence.append(
                (
                    "HIGH_RISK_CORRIDOR",
                    0.06,
                    "A bridge or corridor element in the route increases evasion concern.",
                )
            )
        if self._path_has_hub_discount(best_path, node_key) and primary_reason_code != "HUB_PATH_DISCOUNTED":
            evidence.append(
                (
                    "HUB_PATH_DISCOUNTED",
                    -0.12,
                    "Shared infrastructure in the path reduces confidence that the route reflects direct sanctions evasion.",
                )
            )
        if self._path_has_old_exposure(best_path):
            evidence.append(
                (
                    "OLD_EXPOSURE_DISCOUNTED",
                    -0.10,
                    "The strongest observed exposure is stale and therefore discounted.",
                )
            )
        guard_hints = self.guard_hints_by_key.get(node_key, set())
        if "DUST_EXPOSURE_IGNORED" in guard_hints and primary_reason_code != "DUST_EXPOSURE_DISCOUNTED":
            evidence.append(
                (
                    "DUST_EXPOSURE_DISCOUNTED",
                    -0.15,
                    "Only dust-level indirect exposure was observed and discounted.",
                )
            )
        return evidence

    def _build_evidence(
        self,
        *,
        node_key: str,
        chain: str | None,
        asset: str | None,
        amount_usd: float | None,
        direct_hit: bool,
        risk_level: str | None,
        source_risk_level: str,
        best_depth: int | None,
        best_path: list[dict],
    ) -> tuple[list[dict], float, str]:
        primary_reason_code, primary_score, primary_explanation = self._primary_path_evidence(
            node_key=node_key,
            direct_hit=direct_hit,
            risk_level=risk_level,
            source_risk_level=source_risk_level,
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
                        chain=chain,
                        asset=asset,
                        amount_usd=amount_usd,
                    ) if primary_reason_code is not None else {},
                }
            )
        for reason_code, contribution, explanation in self._supplemental_evidence(
            node_key=node_key,
            source_risk_level=source_risk_level,
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
                        chain=chain,
                        asset=asset,
                        amount_usd=amount_usd,
                    ) if reason_code in {
                        "PROXY_ACCOUNT_BEHAVIOR",
                        "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
                        "CRYPTO_DERIVED_RISK_ANCHOR",
                        "CRYPTO_PROXY_CHAIN_FUNDING",
                        "CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED",
                    } else {},
                }
            )
        total_score = self._clamp_score(total_score)
        primary_reason = primary_explanation if primary_reason_code is not None else "No crypto exposure evidence was found."
        return evidence, total_score, primary_reason

    def _build_rule_triggers(self, evidence: list[dict], node_key: str) -> list[str]:
        triggers: list[str] = [str(item["reason_code"]) for item in evidence]
        if not triggers:
            guard_hints = sorted(self.guard_hints_by_key.get(node_key, set()))
            if guard_hints:
                triggers.extend(guard_hints)
            else:
                triggers.append("NO_EXPOSURE_INDEX_ENTRY")
        return list(dict.fromkeys(triggers))

    def screen_wallet(
        self,
        chain: str,
        wallet_address: str,
        *,
        asset: str | None = None,
        amount_usd: float | None = None,
        review_threshold: float | None = None,
    ) -> CryptoWalletScreeningResult:
        """Screen one wallet using only the precomputed exposure index."""
        del review_threshold
        t0 = time.perf_counter()
        node_key = self._node_key(chain, wallet_address)
        node = self.nodes_by_key.get(node_key)
        exposure = self.exposures_by_key.get(node_key)
        risk_level = node.get("risk_level") if node else None
        node_type = node.get("node_type") if node else None
        direct_hit = bool(
            node
            and str(risk_level or "").upper() == "SANCTIONED"
            and str(node_type or "").upper() == "WALLET"
        )
        graph_score = min(1.0, max(0.0, float(exposure["exposure_score"]) if exposure else 0.0))
        best_depth = exposure["best_depth"] if exposure else None
        best_path = list(exposure["best_path"]) if exposure else []
        source_node = self.nodes_by_key.get(exposure["source_risk_node"], {}) if exposure else {}
        source_risk_level = str(source_node.get("risk_level") or "NONE").upper()
        evidence, risk_score, primary_reason = self._build_evidence(
            node_key=node_key,
            chain=chain,
            asset=asset,
            amount_usd=amount_usd,
            direct_hit=direct_hit,
            risk_level=risk_level,
            source_risk_level=source_risk_level,
            best_depth=best_depth,
            best_path=best_path,
        )
        verdict = VerdictType.MATCH if direct_hit else (
            VerdictType.REVIEW if risk_score >= REVIEW_RISK_SCORE_THRESHOLD else VerdictType.NO_MATCH
        )
        rule_triggers = self._build_rule_triggers(evidence, node_key)
        return CryptoWalletScreeningResult(
            module="crypto_wallet_exposure",
            chain=str(chain or "").upper(),
            wallet_address=str(wallet_address or "").lower(),
            score=graph_score,
            graph_exposure_score=graph_score,
            risk_score=risk_score,
            sanctions_evasion_score=risk_score,
            recommended_action=verdict,
            verdict=verdict,
            risk_type=RISK_TYPE,
            evasion_typology=EVASION_TYPOLOGY,
            direct_hit=direct_hit,
            source_risk_level=source_risk_level,
            source_risk_node=exposure["source_risk_node"] if exposure else None,
            best_depth=best_depth,
            best_path=best_path,
            rule_triggers=rule_triggers,
            primary_reason=primary_reason,
            reason=primary_reason,
            evidence=evidence,
            evidence_package=evidence,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


def _print_result(result: CryptoWalletScreeningResult) -> None:
    print(f"Module: {result.module}")
    print(f"Chain: {result.chain}")
    print(f"Wallet: {result.wallet_address}")
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
    parser.add_argument("--chain", required=True)
    parser.add_argument("--wallet-address", required=True)
    parser.add_argument("--asset", default="")
    parser.add_argument("--amount-usd", type=float, default=0.0)
    parser.add_argument("--threshold", type=float, default=DEFAULT_REVIEW_THRESHOLD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lookup = CryptoWalletExposureLookup.load()
    _print_result(
        lookup.screen_wallet(
            args.chain,
            args.wallet_address,
            asset=args.asset or None,
            amount_usd=args.amount_usd or None,
            review_threshold=args.threshold,
        )
    )


if __name__ == "__main__":
    main()
