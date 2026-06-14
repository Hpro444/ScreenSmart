"""Propagation directionality policy for the crypto wallet exposure graph."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PropagationRule:
    allow_forward: bool
    allow_reverse: bool
    override_allowed_forward: bool
    override_allowed_reverse: bool
    forward_semantic: str
    reverse_semantic: str
    forward_multiplier: float
    reverse_multiplier: float


RULES: dict[str, PropagationRule] = {
    "TRANSFERRED_TO": PropagationRule(True, True, True, True, "inbound_from_anchor", "outbound_to_anchor", 0.85, 1.10),
    "BRIDGED_TO": PropagationRule(True, True, True, True, "inbound_from_anchor", "outbound_to_anchor", 0.80, 1.00),
    "DEPOSITED_TO_EXCHANGE": PropagationRule(True, False, False, False, "service_boundary", "service_boundary", 0.20, 0.0),
    "WITHDREW_FROM_EXCHANGE": PropagationRule(True, False, False, False, "service_boundary", "service_boundary", 0.20, 0.0),
    "USED_MIXER": PropagationRule(True, False, False, False, "proxy_intermediary", "proxy_intermediary", 0.65, 0.0),
    "INTERACTED_WITH_CONTRACT": PropagationRule(False, False, False, False, "service_boundary", "service_boundary", 0.0, 0.0),
}

SERVICE_BOUNDARY_NODE_TYPES = {"BRIDGE", "EXCHANGE_HOT_WALLET", "MIXER", "SMART_CONTRACT"}


def rule_for_edge(edge_type: str) -> PropagationRule:
    return RULES.get(
        (edge_type or "").upper(),
        PropagationRule(True, False, False, False, "relationship", "relationship", 0.80, 0.0),
    )


def build_adjacency_entries(base: dict) -> tuple[list[dict], int]:
    """Build propagation adjacency entries according to edge-type semantics."""
    rule = rule_for_edge(str(base.get("edge_type") or ""))
    entries: list[dict] = []
    if rule.allow_forward:
        entries.append(
            {
                **base,
                "neighbor": base["to_node_key"],
                "path_direction": "forward",
                "override_allowed": rule.override_allowed_forward,
                "semantic_flow": rule.forward_semantic,
                "directional_multiplier": rule.forward_multiplier,
            }
        )
    skipped_reverse = 0
    if rule.allow_reverse:
        entries.append(
            {
                **base,
                "neighbor": base["from_node_key"],
                "path_direction": "reverse",
                "override_allowed": rule.override_allowed_reverse,
                "semantic_flow": rule.reverse_semantic,
                "directional_multiplier": rule.reverse_multiplier,
            }
        )
    else:
        skipped_reverse = 1
    return entries, skipped_reverse


def is_service_boundary_node(node: dict) -> bool:
    return str(node.get("node_type") or "").upper() in SERVICE_BOUNDARY_NODE_TYPES
