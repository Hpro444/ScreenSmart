"""Offline crypto wallet exposure precompute over the aggregated graph.

Run:
    python -m crypto_exposure_graph.exposure.precompute --max-depth 2 --top-k 20 --reset
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import heapq
import itertools
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..db.database import get_engine
from ..db.schema import crypto_exposure_index, crypto_graph_edges, crypto_graph_nodes
from .policy import build_adjacency_entries, is_service_boundary_node
from .scoring import (
    average_transaction_value,
    concentration_score,
    crypto_materiality_weight,
    edge_score,
    exposure_verdict,
    FLOW_EDGE_TYPES,
    hop_decay,
    hub_penalty,
    ignore_isolated_dust_edge,
    path_reaches_sanctioned,
    time_decay,
    source_risk,
)


@dataclass
class SearchStats:
    """Operational counters emitted by the offline propagation job."""

    edges_considered: int = 0
    adjacency_entries_created: int = 0
    reverse_edges_skipped_due_to_directionality: int = 0
    service_boundary_propagation_stops: int = 0
    top_k_truncated_edges: int = 0
    risk_anchors: int = 0
    rows_written: int = 0
    max_depth_reached: int = 0
    expanded_nodes: int = 0
    expanded_neighbors: int = 0
    derived_anchor_candidates: int = 0
    derived_anchor_rows: int = 0
    derived_anchor_suppressed_rows: int = 0

    @property
    def average_neighbors_expanded(self) -> float:
        if self.expanded_nodes == 0:
            return 0.0
        return self.expanded_neighbors / self.expanded_nodes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--min-score", type=float, default=0.03)
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def load_graph(engine, *, today: dt.date) -> tuple[dict[str, dict], dict[str, list[dict]], dict[str, int]]:
    """Load nodes plus a scored adjacency list for offline expansion."""
    nodes: dict[str, dict] = {}
    adjacency: dict[str, list[dict]] = collections.defaultdict(list)
    debug_stats = {
        "edges_considered": 0,
        "adjacency_entries_created": 0,
        "reverse_edges_skipped_due_to_directionality": 0,
    }
    with engine.connect() as conn:
        for row in conn.execute(
            sa.select(
                crypto_graph_nodes.c.node_key,
                crypto_graph_nodes.c.chain,
                crypto_graph_nodes.c.address,
                crypto_graph_nodes.c.node_type,
                crypto_graph_nodes.c.display_name,
                crypto_graph_nodes.c.risk_level,
                crypto_graph_nodes.c.risk_source,
            )
        ):
            nodes[row.node_key] = {
                "node_key": row.node_key,
                "chain": row.chain,
                "address": row.address,
                "node_type": row.node_type,
                "display_name": row.display_name,
                "risk_level": row.risk_level,
                "risk_source": row.risk_source,
            }

        edge_rows = list(conn.execute(
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
        ))
        total_outgoing_value_by_node: collections.defaultdict[str, float] = collections.defaultdict(float)
        total_incoming_value_by_node: collections.defaultdict[str, float] = collections.defaultdict(float)
        node_degree: collections.Counter[str] = collections.Counter()
        for row in edge_rows:
            node_degree[row.from_node_key] += 1
            node_degree[row.to_node_key] += 1
            if row.edge_type not in FLOW_EDGE_TYPES:
                continue
            value = float(row.total_usd_value or 0.0)
            total_outgoing_value_by_node[row.from_node_key] += value
            total_incoming_value_by_node[row.to_node_key] += value

        for row in edge_rows:
            debug_stats["edges_considered"] += 1
            value = float(row.total_usd_value or 0.0)
            outgoing_total = total_outgoing_value_by_node[row.from_node_key]
            incoming_total = total_incoming_value_by_node[row.to_node_key]
            outgoing_concentration = (
                value / outgoing_total
                if row.edge_type in FLOW_EDGE_TYPES and outgoing_total > 0.0
                else 0.0
            )
            incoming_concentration = (
                value / incoming_total
                if row.edge_type in FLOW_EDGE_TYPES and incoming_total > 0.0
                else 0.0
            )
            flow_concentration = max(outgoing_concentration, incoming_concentration)
            base = {
                "edge_type": row.edge_type,
                "total_usd_value": row.total_usd_value,
                "transaction_count": row.transaction_count,
                "first_seen": row.first_seen,
                "last_seen": row.last_seen,
                "confidence": float(row.confidence) if row.confidence is not None else 1.0,
                "from_node_key": row.from_node_key,
                "to_node_key": row.to_node_key,
                "from_node_type": nodes[row.from_node_key]["node_type"],
                "to_node_type": nodes[row.to_node_key]["node_type"],
                "from_node_degree": int(node_degree[row.from_node_key]),
                "to_node_degree": int(node_degree[row.to_node_key]),
                "outgoing_concentration": outgoing_concentration,
                "incoming_concentration": incoming_concentration,
                "flow_concentration": flow_concentration,
            }
            base["average_transaction_value"] = average_transaction_value(base)
            base["crypto_materiality_weight"] = crypto_materiality_weight(
                row.edge_type,
                row.total_usd_value,
                flow_concentration=flow_concentration,
            )
            base["concentration_score"] = concentration_score(flow_concentration)
            base["hub_penalty"] = hub_penalty(base)
            score = edge_score(base, today=today)
            base["edge_score"] = score
            entries, skipped_reverse = build_adjacency_entries(base)
            debug_stats["reverse_edges_skipped_due_to_directionality"] += skipped_reverse
            debug_stats["adjacency_entries_created"] += len(entries)
            for entry in entries:
                source_key = row.from_node_key if entry["path_direction"] == "forward" else row.to_node_key
                adjacency[source_key].append(entry)

    for node_key, neighbors in adjacency.items():
        adjacency[node_key] = sorted(neighbors, key=lambda item: item["edge_score"], reverse=True)
    return nodes, adjacency, debug_stats


def is_direct_sanctioned_wallet(node: dict, source_key: str, depth: int) -> bool:
    return (
        depth == 0
        and node["node_key"] == source_key
        and node.get("risk_level") == "SANCTIONED"
        and node.get("node_type") == "WALLET"
    )


def build_path_json(
    nodes: dict[str, dict],
    path_nodes: tuple[str, ...],
    path_edges: tuple[dict, ...],
) -> list[dict]:
    """Serialize the winning path into the JSON shape stored in `crypto_exposure_index`."""
    rev_nodes = list(reversed(path_nodes))
    rev_edges = list(reversed(path_edges))
    out: list[dict] = []
    for idx, node_key in enumerate(rev_nodes):
        meta = nodes[node_key]
        entry = {
            "node_key": node_key,
            "chain": meta["chain"],
            "address": meta["address"],
            "node_type": meta["node_type"],
        }
        if idx == 0:
            if len(rev_nodes) == 1 and meta.get("risk_level") not in (None, "NONE"):
                entry["risk_level"] = meta["risk_level"]
            out.append(entry)
            continue
        edge = rev_edges[idx - 1]
        entry["edge_type"] = edge["edge_type"]
        entry["total_usd_value"] = float(edge["total_usd_value"] or 0.0)
        entry["transaction_count"] = int(edge["transaction_count"] or 0)
        entry["average_transaction_value"] = round(float(edge.get("average_transaction_value") or 0.0), 6)
        entry["outgoing_concentration"] = round(float(edge.get("outgoing_concentration") or 0.0), 6)
        entry["incoming_concentration"] = round(float(edge.get("incoming_concentration") or 0.0), 6)
        entry["flow_concentration"] = round(float(edge.get("flow_concentration") or 0.0), 6)
        entry["crypto_materiality_weight"] = round(float(edge.get("crypto_materiality_weight") or 0.0), 6)
        entry["concentration_score"] = round(float(edge.get("concentration_score") or 0.0), 6)
        entry["override_allowed"] = bool(edge.get("override_allowed", True))
        entry["semantic_flow"] = str(edge.get("semantic_flow") or "")
        entry["directional_multiplier"] = round(float(edge.get("directional_multiplier") or 1.0), 6)
        entry["hub_penalty"] = round(float(edge.get("hub_penalty") or 0.0), 6)
        entry["confidence"] = float(edge["confidence"] or 1.0)
        entry["edge_from"] = edge["from_node_key"]
        entry["edge_to"] = edge["to_node_key"]
        entry["edge_direction"] = edge["path_direction"]
        entry["first_seen"] = edge["first_seen"].isoformat() if edge.get("first_seen") else None
        entry["last_seen"] = edge["last_seen"].isoformat() if edge.get("last_seen") else None
        if idx == len(rev_nodes) - 1 and meta.get("risk_level") not in (None, "NONE"):
            entry["risk_level"] = meta["risk_level"]
        out.append(entry)
    return out


def build_reason(
    *,
    source_node: dict,
    score: float,
    depth: int,
    direct_hit: bool,
    path_edges: tuple[dict, ...],
) -> str:
    """Build the stored offline explanation string."""
    verdict = exposure_verdict(score, direct_hit=direct_hit)
    if direct_hit:
        return "direct sanctioned wallet anchor"
    if depth == 0:
        return f"{source_node['risk_level'].lower()} anchor node"
    hops = " -> ".join(edge["edge_type"] for edge in path_edges) if path_edges else "anchor"
    return (
        f"{verdict} exposure from {source_node['risk_level'].lower()} anchor "
        f"{source_node['node_key']} at depth {depth} via {hops} (score {score:.3f})"
    )


def classify_derived_anchor(
    record: dict,
    nodes: dict[str, dict],
    *,
    today: dt.date,
    adjacency: dict[str, list[dict]],
) -> dict | None:
    if record["depth"] <= 0:
        return None
    node = nodes[record["node_key"]]
    if str(node.get("node_type") or "").upper() != "WALLET":
        return None
    if is_service_boundary_node(node):
        return None
    path_edges = list(record["path_edges"])
    if not path_edges:
        return None
    if any(ignore_isolated_dust_edge(edge) for edge in path_edges):
        return None
    if any(
        str(nodes.get(edge.get("to_node_key"), {}).get("node_type") or "").upper() in {"EXCHANGE_HOT_WALLET", "BRIDGE", "MIXER", "SMART_CONTRACT"}
        or str(nodes.get(edge.get("from_node_key"), {}).get("node_type") or "").upper() in {"EXCHANGE_HOT_WALLET", "BRIDGE", "MIXER", "SMART_CONTRACT"}
        for edge in path_edges
    ):
        return None

    source_node = nodes[record["source_risk_node"]]
    source_risk_level = str(source_node.get("risk_level") or "NONE").upper()
    semantics = [str(edge.get("semantic_flow") or "") for edge in path_edges]
    all_outbound = bool(semantics) and all(item == "outbound_to_anchor" for item in semantics)
    all_inbound = bool(semantics) and all(item == "inbound_from_anchor" for item in semantics)
    recent_material = any(
        float(edge.get("total_usd_value") or 0.0) >= 1000.0
        and time_decay(edge.get("last_seen"), today=today) >= 0.8
        for edge in path_edges
    )
    strong_concentration = any(float(edge.get("flow_concentration") or 0.0) >= 0.70 for edge in path_edges)
    structuring = any(
        int(edge.get("transaction_count") or 0) >= 100 and float(edge.get("total_usd_value") or 0.0) >= 1000.0
        for edge in path_edges
    )
    if all_outbound and path_reaches_sanctioned(build_path_json(nodes, record["path_nodes"], record["path_edges"])) and record["depth"] == 1:
        return {
            "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
            "weight": 0.70,
            "explanation": "Direct outbound crypto flow to a sanctioned wallet created a strong derived anchor.",
        }
    if all_outbound and path_reaches_sanctioned(build_path_json(nodes, record["path_nodes"], record["path_edges"])) and record["depth"] == 2:
        return {
            "reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
            "weight": 0.55,
            "explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
        }
    if all_inbound and recent_material and source_risk_level in {"SANCTIONED", "RANSOMWARE", "SCAM", "HACK_PROCEEDS"}:
        return {
            "reason_code": "INBOUND_FROM_SANCTIONED",
            "weight": 0.55,
            "explanation": "Recent material inbound crypto flow from a high-risk source created a medium-strength derived anchor.",
        }
    if recent_material and (strong_concentration or structuring) and source_risk_level in {"SANCTIONED", "RANSOMWARE", "SCAM", "HACK_PROCEEDS", "SUSPICIOUS"}:
        return {
            "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
            "weight": 0.35,
            "explanation": "Recent concentrated or structured crypto routing near a risky source created a low-strength derived anchor.",
        }
    return None


def build_derived_best_path(
    nodes: dict[str, dict],
    *,
    funder_key: str,
    upstream_edge: dict,
    derived_anchor_meta: dict,
    derived_anchor_best_path: list[dict],
    suppression_reason: str | None,
) -> list[dict]:
    funder_meta = nodes[funder_key]
    anchor_meta = nodes[upstream_edge["to_node_key"]]
    out: list[dict] = [
        {
            "node_key": funder_key,
            "chain": funder_meta["chain"],
            "address": funder_meta["address"],
            "node_type": funder_meta["node_type"],
        }
    ]
    out.append(
        {
            "node_key": upstream_edge["to_node_key"],
            "chain": anchor_meta["chain"],
            "address": anchor_meta["address"],
            "node_type": anchor_meta["node_type"],
            "edge_type": upstream_edge["edge_type"],
            "total_usd_value": float(upstream_edge["total_usd_value"] or 0.0),
            "transaction_count": int(upstream_edge["transaction_count"] or 0),
            "average_transaction_value": round(float(upstream_edge.get("average_transaction_value") or 0.0), 6),
            "outgoing_concentration": round(float(upstream_edge.get("outgoing_concentration") or 0.0), 6),
            "incoming_concentration": round(float(upstream_edge.get("incoming_concentration") or 0.0), 6),
            "flow_concentration": round(float(upstream_edge.get("flow_concentration") or 0.0), 6),
            "crypto_materiality_weight": round(float(upstream_edge.get("crypto_materiality_weight") or 0.0), 6),
            "concentration_score": round(float(upstream_edge.get("concentration_score") or 0.0), 6),
            "override_allowed": bool(upstream_edge.get("override_allowed", True)),
            "semantic_flow": str(upstream_edge.get("semantic_flow") or ""),
            "directional_multiplier": round(float(upstream_edge.get("directional_multiplier") or 1.0), 6),
            "hub_penalty": round(float(upstream_edge.get("hub_penalty") or 0.0), 6),
            "confidence": float(upstream_edge.get("confidence") or 1.0),
            "edge_from": upstream_edge["from_node_key"],
            "edge_to": upstream_edge["to_node_key"],
            "edge_direction": upstream_edge["path_direction"],
            "first_seen": upstream_edge["first_seen"].isoformat() if upstream_edge.get("first_seen") else None,
            "last_seen": upstream_edge["last_seen"].isoformat() if upstream_edge.get("last_seen") else None,
            "derived_anchor": True,
            "derived_anchor_score": round(float(derived_anchor_meta["weight"]), 4),
            "derived_anchor_reason_code": derived_anchor_meta["reason_code"],
            "derived_anchor_explanation": derived_anchor_meta["explanation"],
            "derived_anchor_original_score": round(float(derived_anchor_meta["original_score"]), 4),
            "derived_anchor_node": upstream_edge["to_node_key"],
            "derived_suppression_reason": suppression_reason,
        }
    )
    out.extend(derived_anchor_best_path[1:])
    return out


def compute_derived_anchor_rows(
    primary_rows_by_key: dict[str, dict],
    primary_results: dict[str, dict],
    nodes: dict[str, dict],
    adjacency: dict[str, list[dict]],
    *,
    today: dt.date,
    stats: SearchStats,
) -> list[dict]:
    rows: list[dict] = []
    for node_key, record in primary_results.items():
        derived_meta = classify_derived_anchor(record, nodes, today=today, adjacency=adjacency)
        if derived_meta is None:
            continue
        stats.derived_anchor_candidates += 1
        derived_meta["original_score"] = record["score"]
        derived_anchor_best_path = primary_rows_by_key[node_key]["best_path"]
        for edge in adjacency.get(node_key, []):
            if str(edge.get("path_direction") or "") != "reverse":
                continue
            if str(edge.get("edge_type") or "").upper() not in {"TRANSFERRED_TO", "BRIDGED_TO"}:
                continue
            funder_key = edge["neighbor"]
            funder_node = nodes[funder_key]
            if funder_key in record["path_nodes"]:
                continue
            suppression_reason = None
            if str(funder_node.get("node_type") or "").upper() != "WALLET":
                suppression_reason = "NON_WALLET_UPSTREAM"
            elif is_service_boundary_node(funder_node):
                suppression_reason = "SERVICE_BOUNDARY"
            elif ignore_isolated_dust_edge(edge):
                suppression_reason = "DUST_EDGE"
            amount = float(edge.get("total_usd_value") or 0.0)
            recency = time_decay(edge.get("last_seen"), today=today)
            incoming_concentration = float(edge.get("incoming_concentration") or 0.0)
            patterned = int(edge.get("transaction_count") or 0) >= 100
            material = amount >= 1000.0 and recency >= 0.8
            concentrated_or_patterned = incoming_concentration >= 0.50 or patterned
            strong_anchor = float(derived_meta["weight"]) >= 0.55
            if not material:
                suppression_reason = suppression_reason or "LOW_MATERIALITY_OR_STALE"
            if not concentrated_or_patterned:
                suppression_reason = suppression_reason or "LOW_CONCENTRATION"
            if not strong_anchor:
                suppression_reason = suppression_reason or "WEAK_DERIVED_ANCHOR"

            score = (
                float(derived_meta["weight"])
                * float(edge["edge_score"])
                * float(edge.get("directional_multiplier") or 1.0)
                * hop_decay(1)
            )
            best_path = build_derived_best_path(
                nodes,
                funder_key=funder_key,
                upstream_edge=edge,
                derived_anchor_meta=derived_meta,
                derived_anchor_best_path=derived_anchor_best_path,
                suppression_reason=suppression_reason,
            )
            row = {
                "node_key": funder_key,
                "exposure_score": round(score if suppression_reason is None else min(score, 0.029), 4),
                "best_depth": len(best_path) - 1,
                "best_path": best_path,
                "source_risk_node": record["source_risk_node"],
                "reason": (
                    f"derived crypto proxy funding from {funder_key} into {node_key} "
                    f"({derived_meta['reason_code']}) score {score:.3f}"
                    if suppression_reason is None
                    else f"derived crypto proxy funding suppressed for {funder_key} into {node_key} because {suppression_reason.lower()}"
                ),
                "computed_at": dt.datetime.combine(today, dt.time(11, 5)),
            }
            if suppression_reason is None:
                stats.derived_anchor_rows += 1
            else:
                stats.derived_anchor_suppressed_rows += 1
            rows.append(row)
    return rows


def compute_exposure(
    nodes: dict[str, dict],
    adjacency: dict[str, list[dict]],
    *,
    max_depth: int,
    top_k: int,
    min_score: float,
    today: dt.date,
) -> tuple[list[dict], SearchStats]:
    """Propagate exposure from all risky anchors and keep one best path per node."""
    anchors = [node for node in nodes.values() if source_risk(node.get("risk_level")) > 0.0]
    stats = SearchStats(risk_anchors=len(anchors))
    best_score_by_node: dict[str, float] = {}
    results: dict[str, dict] = {}
    queue: list[tuple[float, int, str, int, float, tuple[str, ...], tuple[dict, ...], str]] = []
    seq = itertools.count()

    for anchor in anchors:
        key = anchor["node_key"]
        score = source_risk(anchor["risk_level"])
        if score <= best_score_by_node.get(key, 0.0):
            continue
        best_score_by_node[key] = score
        results[key] = {
            "node_key": key,
            "score": score,
            "depth": 0,
            "path_nodes": (key,),
            "path_edges": (),
            "source_risk_node": key,
        }
        heapq.heappush(queue, (-score, next(seq), key, 0, score, (key,), (), key))

    while queue:
        _neg_score, _n, node_key, depth, current_score, path_nodes, path_edges, source_key = heapq.heappop(queue)
        if current_score < best_score_by_node.get(node_key, 0.0):
            continue
        if depth >= max_depth:
            continue
        if is_service_boundary_node(nodes[node_key]):
            stats.service_boundary_propagation_stops += 1
            continue

        neighbors = adjacency.get(node_key, [])
        candidate_edges = neighbors[:top_k]
        stats.top_k_truncated_edges += max(0, len(neighbors) - len(candidate_edges))
        filtered_edges = [edge for edge in candidate_edges if not ignore_isolated_dust_edge(edge)]
        stats.expanded_nodes += 1
        stats.expanded_neighbors += len(filtered_edges)

        for edge in filtered_edges:
            neighbor = edge["neighbor"]
            if neighbor in path_nodes:
                continue
            next_depth = depth + 1
            new_score = current_score * edge["edge_score"] * float(edge.get("directional_multiplier") or 1.0) * hop_decay(next_depth)
            if new_score <= best_score_by_node.get(neighbor, 0.0):
                continue

            next_path_nodes = path_nodes + (neighbor,)
            next_path_edges = path_edges + (edge,)
            best_score_by_node[neighbor] = new_score
            results[neighbor] = {
                "node_key": neighbor,
                "score": new_score,
                "depth": next_depth,
                "path_nodes": next_path_nodes,
                "path_edges": next_path_edges,
                "source_risk_node": source_key,
            }
            stats.max_depth_reached = max(stats.max_depth_reached, next_depth)
            if new_score < min_score:
                continue
            heapq.heappush(
                queue,
                (-new_score, next(seq), neighbor, next_depth, new_score, next_path_nodes, next_path_edges, source_key),
            )

    rows = []
    for record in results.values():
        node = nodes[record["node_key"]]
        source_node = nodes[record["source_risk_node"]]
        direct_hit = is_direct_sanctioned_wallet(node, record["source_risk_node"], record["depth"])
        rows.append(
            {
                "node_key": record["node_key"],
                "exposure_score": round(record["score"], 4),
                "best_depth": record["depth"],
                "best_path": build_path_json(nodes, record["path_nodes"], record["path_edges"]),
                "source_risk_node": record["source_risk_node"],
                "reason": build_reason(
                    source_node=source_node,
                    score=record["score"],
                    depth=record["depth"],
                    direct_hit=direct_hit,
                    path_edges=record["path_edges"],
                ),
                "computed_at": dt.datetime.combine(today, dt.time(11, 0)),
            }
        )
    primary_rows_by_key = {row["node_key"]: row for row in rows}
    derived_rows = compute_derived_anchor_rows(
        primary_rows_by_key,
        results,
        nodes,
        adjacency,
        today=today,
        stats=stats,
    )
    merged_rows = {row["node_key"]: row for row in rows}
    for row in derived_rows:
        existing = merged_rows.get(row["node_key"])
        if existing is not None and int(existing.get("best_depth") or 0) <= 2 and path_reaches_sanctioned(list(existing.get("best_path") or [])):
            continue
        if existing is None or float(row["exposure_score"]) > float(existing["exposure_score"]):
            merged_rows[row["node_key"]] = row
    stats.rows_written = len(merged_rows)
    return list(merged_rows.values()), stats


def write_exposure_rows(engine, rows: list[dict], *, reset: bool) -> None:
    batch_size = 500
    with engine.begin() as conn:
        if reset:
            conn.execute(sa.delete(crypto_exposure_index))
        if not rows:
            return
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            stmt = pg_insert(crypto_exposure_index).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=[crypto_exposure_index.c.node_key],
                set_={
                    "exposure_score": stmt.excluded.exposure_score,
                    "best_depth": stmt.excluded.best_depth,
                    "best_path": stmt.excluded.best_path,
                    "source_risk_node": stmt.excluded.source_risk_node,
                    "reason": stmt.excluded.reason,
                    "computed_at": stmt.excluded.computed_at,
                },
            )
            conn.execute(stmt)


def print_summary(stats: SearchStats) -> None:
    print(f"edges considered: {stats.edges_considered}")
    print(f"adjacency entries created: {stats.adjacency_entries_created}")
    print(f"reverse edges skipped due to policy: {stats.reverse_edges_skipped_due_to_directionality}")
    print(f"service-boundary propagation stops: {stats.service_boundary_propagation_stops}")
    print(f"top-k truncated edges: {stats.top_k_truncated_edges}")
    print(f"risk anchors: {stats.risk_anchors}")
    print(f"exposure rows written: {stats.rows_written}")
    print(f"max depth reached: {stats.max_depth_reached}")
    print(f"derived anchor candidates: {stats.derived_anchor_candidates}")
    print(f"derived anchor rows: {stats.derived_anchor_rows}")
    print(f"derived anchor suppressed rows: {stats.derived_anchor_suppressed_rows}")
    print(f"average neighbors expanded: {stats.average_neighbors_expanded:.2f}")
    print()
    print("SQL check:")
    print("select count(*) from crypto_exposure_index;")


def main() -> None:
    args = parse_args()
    today = dt.date.today()
    engine = get_engine()
    nodes, adjacency, load_debug = load_graph(engine, today=today)
    rows, stats = compute_exposure(
        nodes,
        adjacency,
        max_depth=args.max_depth,
        top_k=args.top_k,
        min_score=args.min_score,
        today=today,
    )
    stats.edges_considered = load_debug["edges_considered"]
    stats.adjacency_entries_created = load_debug["adjacency_entries_created"]
    stats.reverse_edges_skipped_due_to_directionality = load_debug["reverse_edges_skipped_due_to_directionality"]
    write_exposure_rows(engine, rows, reset=args.reset)
    print_summary(stats)


if __name__ == "__main__":
    main()
