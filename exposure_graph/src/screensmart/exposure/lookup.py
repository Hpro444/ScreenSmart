"""Realtime account exposure lookup over precomputed data only.

This module performs O(1)-style lookups against `graph_nodes` and `exposure_index`.
It does not traverse `graph_edges` and does not run BFS online.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time

import sqlalchemy as sa

from ..db.database import get_engine
from ..db.schema import exposure_index, graph_nodes
from ..domain.enums import VerdictType
from .scoring import (
    DEFAULT_REVIEW_THRESHOLD,
    exposure_verdict,
    is_old_tiny_exposure,
    path_reaches_sanctioned,
)

ACCOUNT_NODE_TYPES = {"IBAN", "ACCOUNT", "WALLET", "PERSON", "COMPANY", "BANK"}


@dataclasses.dataclass(frozen=True)
class AccountScreeningResult:
    module: str
    node_key: str
    score: float
    recommended_action: VerdictType
    verdict: VerdictType
    source_risk_level: str
    source_node_type: str | None
    rule_triggers: list[str]
    exposure_score: float
    best_depth: int | None
    direct_hit: bool
    node_type: str | None
    risk_level: str | None
    source_risk_node: str | None
    best_path: list[dict]
    reason: str
    latency_ms: float


class AccountExposureLookup:
    """In-memory lookup table over `graph_nodes` and `exposure_index`."""

    def __init__(self, nodes_by_key: dict[str, dict], exposures_by_key: dict[str, dict]) -> None:
        self.nodes_by_key = nodes_by_key
        self.exposures_by_key = exposures_by_key

    @classmethod
    def load(cls, engine=None) -> "AccountExposureLookup":
        engine = engine or get_engine()
        nodes_by_key: dict[str, dict] = {}
        exposures_by_key: dict[str, dict] = {}
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
        return cls(nodes_by_key, exposures_by_key)

    def _build_reason(
        self,
        *,
        verdict: VerdictType,
        score: float,
        best_depth: int | None,
        direct_hit: bool,
        source_risk_node: str | None,
        best_path: list[dict],
        review_threshold: float,
    ) -> str:
        if direct_hit:
            return "MATCH: recipient account is directly sanctioned."

        if not best_path:
            return "NO_MATCH: no exposure index entry found for recipient account."

        depth = best_depth if best_depth is not None else max(0, len(best_path) - 1)
        edge_types = " -> ".join(
            str(node.get("edge_type", "")).upper() for node in best_path[1:] if node.get("edge_type")
        ) or "anchor"
        source_node = self.nodes_by_key.get(source_risk_node or "", {})
        source_risk = str(source_node.get("risk_level") or "unknown").lower()
        source_label = source_risk_node or best_path[-1]["node_key"]
        sanctioned_override = (
            verdict is VerdictType.REVIEW
            and score < review_threshold
            and best_depth is not None
            and best_depth <= 2
            and path_reaches_sanctioned(best_path)
            and not is_old_tiny_exposure(best_path)
        )

        if verdict is VerdictType.REVIEW and sanctioned_override:
            return (
                f"REVIEW: recipient account is {depth} hops from a sanctioned account via {edge_types}; "
                f"routed to review despite low decayed exposure score {score:.4f}."
            )
        if verdict is VerdictType.REVIEW:
            return (
                f"REVIEW: recipient account has exposure score {score:.4f} from "
                f"{source_risk} anchor {source_label} at depth {depth} via {edge_types}."
            )
        if is_old_tiny_exposure(best_path):
            return "NO_MATCH: only weak historical exposure below threshold."
        return (
            f"NO_MATCH: exposure score {score:.4f} is below threshold {review_threshold:.2f} "
            f"for source {source_label} at depth {depth}."
        )

    def _build_rule_triggers(
        self,
        *,
        verdict: VerdictType,
        score: float,
        best_depth: int | None,
        direct_hit: bool,
        risk_level: str | None,
        exposure_found: bool,
        best_path: list[dict],
        review_threshold: float,
    ) -> list[str]:
        triggers: list[str] = []
        has_high_counterparty_concentration = any(
            float(node.get("flow_concentration") or 0.0) >= 0.70
            and float(node.get("amount") or 0.0) >= 1000.0
            for node in best_path[1:]
        )
        if direct_hit and str(risk_level or "").upper() == "SANCTIONED":
            triggers.append("DIRECT_SANCTIONED_HIT")
        elif not exposure_found:
            triggers.append("NO_EXPOSURE_INDEX_ENTRY")
        else:
            sanctioned_override = (
                verdict is VerdictType.REVIEW
                and score < review_threshold
                and best_depth is not None
                and best_depth <= 2
                and path_reaches_sanctioned(best_path)
                and not is_old_tiny_exposure(best_path)
            )
            if sanctioned_override:
                triggers.append("SANCTIONED_PATH_WITHIN_2_HOPS")
            elif verdict is VerdictType.REVIEW and score >= review_threshold:
                triggers.append("SCORE_AT_OR_ABOVE_THRESHOLD")
            elif score < review_threshold:
                triggers.append("WEAK_EXPOSURE_BELOW_THRESHOLD")
        if has_high_counterparty_concentration and exposure_found:
            triggers.append("HIGH_COUNTERPARTY_CONCENTRATION")
        return triggers

    def screen_account(self, node_key: str, *, review_threshold: float | None = None) -> AccountScreeningResult:
        t0 = time.perf_counter()
        threshold = DEFAULT_REVIEW_THRESHOLD if review_threshold is None else review_threshold
        node = self.nodes_by_key.get(node_key)
        exposure = self.exposures_by_key.get(node_key)
        node_type = node.get("node_type") if node else None
        risk_level = node.get("risk_level") if node else None
        direct_hit = bool(
            node
            and str(risk_level or "").upper() == "SANCTIONED"
            and str(node_type or "").upper() in ACCOUNT_NODE_TYPES
        )
        raw_score = float(exposure["exposure_score"]) if exposure else 0.0
        score = min(1.0, max(0.0, raw_score))
        best_depth = exposure["best_depth"] if exposure else None
        best_path = list(exposure["best_path"]) if exposure else []
        recommended_action = VerdictType(
            exposure_verdict(
                score,
                direct_hit=direct_hit,
                review_threshold=threshold,
                best_depth=best_depth,
                best_path=best_path,
            )
        )
        verdict = recommended_action
        source_node = self.nodes_by_key.get(exposure["source_risk_node"], {}) if exposure else {}
        source_risk_level = str(source_node.get("risk_level") or "NONE").upper()
        source_node_type = source_node.get("node_type")
        rule_triggers = self._build_rule_triggers(
            verdict=verdict,
            score=score,
            best_depth=best_depth,
            direct_hit=direct_hit,
            risk_level=risk_level,
            exposure_found=exposure is not None,
            best_path=best_path,
            review_threshold=threshold,
        )
        reason = self._build_reason(
            verdict=verdict,
            score=score,
            best_depth=best_depth,
            direct_hit=direct_hit,
            source_risk_node=exposure["source_risk_node"] if exposure else None,
            best_path=best_path,
            review_threshold=threshold,
        )
        return AccountScreeningResult(
            module="account_exposure",
            node_key=node_key,
            score=score,
            recommended_action=recommended_action,
            verdict=verdict,
            source_risk_level=source_risk_level,
            source_node_type=source_node_type,
            rule_triggers=rule_triggers,
            exposure_score=score,
            best_depth=best_depth,
            direct_hit=direct_hit,
            node_type=node_type,
            risk_level=risk_level,
            source_risk_node=exposure["source_risk_node"] if exposure else None,
            best_path=best_path,
            reason=reason,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


def _print_result(result: AccountScreeningResult) -> None:
    print(f"Module: {result.module}")
    print(f"Recommended action: {result.recommended_action.value}")
    print(f"Score: {result.score:.4f}")
    print(f"Risk level: {result.risk_level or 'NONE'}")
    print(f"Source risk level: {result.source_risk_level}")
    print(f"Rule triggers: {', '.join(result.rule_triggers) if result.rule_triggers else '-'}")
    print(f"Depth: {result.best_depth if result.best_depth is not None else '-'}")
    print("Reason:")
    print(result.reason)
    print("Path:")
    print(json.dumps(result.best_path, indent=2))
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
