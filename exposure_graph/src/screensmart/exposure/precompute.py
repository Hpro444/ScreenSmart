"""Offline exposure precompute over the aggregated counterparty graph.

Run:
    python -m screensmart.exposure.precompute --max-depth 3 --top-k 20 --reset
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
from ..db.schema import exposure_index, graph_edges, graph_nodes
from .scoring import (
    amount_weight,
    concentration_score,
    edge_score,
    exposure_verdict,
    flow_materiality_weight,
    hop_decay,
    ignore_weak_edge,
    source_risk,
)


@dataclass
class SearchStats:
    risk_anchors: int = 0
    rows_written: int = 0
    max_depth_reached: int = 0
    expanded_nodes: int = 0
    expanded_neighbors: int = 0
    hub_nodes_suppressed: int = 0

    @property
    def average_neighbors_expanded(self) -> float:
        if self.expanded_nodes == 0:
            return 0.0
        return self.expanded_neighbors / self.expanded_nodes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--min-score", type=float, default=0.03)
    parser.add_argument("--hub-degree-threshold", type=int, default=200)
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def load_graph(engine, *, today: dt.date) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    nodes: dict[str, dict] = {}
    adjacency: dict[str, list[dict]] = collections.defaultdict(list)
    with engine.connect() as conn:
        node_rows = conn.execute(
            sa.select(
                graph_nodes.c.node_key,
                graph_nodes.c.node_type,
                graph_nodes.c.display_name,
                graph_nodes.c.country,
                graph_nodes.c.risk_level,
                graph_nodes.c.risk_source,
            )
        )
        for row in node_rows:
            nodes[row.node_key] = {
                "node_key": row.node_key,
                "node_type": row.node_type,
                "display_name": row.display_name,
                "country": row.country,
                "risk_level": row.risk_level,
                "risk_source": row.risk_source,
            }

        edge_rows = list(conn.execute(
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
        ))
        total_outgoing_amount_by_node: collections.defaultdict[str, float] = collections.defaultdict(float)
        total_incoming_amount_by_node: collections.defaultdict[str, float] = collections.defaultdict(float)
        for row in edge_rows:
            if row.edge_type != "SENT_TO":
                continue
            amount = float(row.total_amount or 0.0)
            total_outgoing_amount_by_node[row.from_node_key] += amount
            total_incoming_amount_by_node[row.to_node_key] += amount

        for row in edge_rows:
            amount = float(row.total_amount or 0.0)
            outgoing_total = total_outgoing_amount_by_node[row.from_node_key]
            incoming_total = total_incoming_amount_by_node[row.to_node_key]
            outgoing_concentration = (
                amount / outgoing_total
                if row.edge_type == "SENT_TO" and outgoing_total > 0.0
                else 0.0
            )
            incoming_concentration = (
                amount / incoming_total
                if row.edge_type == "SENT_TO" and incoming_total > 0.0
                else 0.0
            )
            flow_concentration = max(outgoing_concentration, incoming_concentration)
            base = {
                "edge_type": row.edge_type,
                "total_amount": row.total_amount,
                "transaction_count": row.transaction_count,
                "first_seen": row.first_seen,
                "last_seen": row.last_seen,
                "confidence": float(row.confidence) if row.confidence is not None else 1.0,
                "from_node_key": row.from_node_key,
                "to_node_key": row.to_node_key,
                "outgoing_concentration": outgoing_concentration,
                "incoming_concentration": incoming_concentration,
                "flow_concentration": flow_concentration,
            }
            base["flow_materiality_weight"] = flow_materiality_weight(
                row.edge_type,
                row.total_amount,
                flow_concentration=flow_concentration,
            )
            base["absolute_amount_weight"] = amount_weight(row.total_amount)
            base["concentration_score"] = concentration_score(flow_concentration)
            score = edge_score(base, today=today)
            forward = {
                **base,
                "neighbor": row.to_node_key,
                "path_direction": "forward",
                "edge_score": score,
            }
            reverse = {
                **base,
                "neighbor": row.from_node_key,
                "path_direction": "reverse",
                "edge_score": score,
            }
            adjacency[row.from_node_key].append(forward)
            adjacency[row.to_node_key].append(reverse)

    for node_key, neighbors in adjacency.items():
        adjacency[node_key] = sorted(neighbors, key=lambda item: item["edge_score"], reverse=True)
    return nodes, adjacency


def is_direct_sanctioned_account(node: dict, source_key: str, depth: int) -> bool:
    return (
        depth == 0
        and node["node_key"] == source_key
        and node.get("risk_level") == "SANCTIONED"
        and node.get("node_type") in {"IBAN", "ACCOUNT", "WALLET"}
    )


def build_path_json(
    nodes: dict[str, dict],
    path_nodes: tuple[str, ...],
    path_edges: tuple[dict, ...],
) -> list[dict]:
    rev_nodes = list(reversed(path_nodes))
    rev_edges = list(reversed(path_edges))
    out: list[dict] = []
    for idx, node_key in enumerate(rev_nodes):
        meta = nodes[node_key]
        entry = {
            "node_key": node_key,
            "node_type": meta["node_type"],
        }
        if idx == 0:
            if len(rev_nodes) == 1 and meta.get("risk_level") not in (None, "NONE"):
                entry["risk_level"] = meta["risk_level"]
            out.append(entry)
            continue
        edge = rev_edges[idx - 1]
        entry["edge_type"] = edge["edge_type"]
        entry["amount"] = float(edge["total_amount"] or 0.0)
        entry["transaction_count"] = int(edge["transaction_count"] or 0)
        entry["confidence"] = float(edge["confidence"] or 1.0)
        entry["edge_from"] = edge["from_node_key"]
        entry["edge_to"] = edge["to_node_key"]
        entry["edge_direction"] = edge["path_direction"]
        entry["first_seen"] = edge["first_seen"].isoformat() if edge.get("first_seen") else None
        entry["last_seen"] = edge["last_seen"].isoformat() if edge.get("last_seen") else None
        if edge.get("outgoing_concentration") is not None:
            entry["outgoing_concentration"] = round(float(edge["outgoing_concentration"]), 6)
        if edge.get("incoming_concentration") is not None:
            entry["incoming_concentration"] = round(float(edge["incoming_concentration"]), 6)
        if edge.get("flow_concentration") is not None:
            entry["flow_concentration"] = round(float(edge["flow_concentration"]), 6)
        if edge.get("flow_materiality_weight") is not None:
            entry["flow_materiality_weight"] = round(float(edge["flow_materiality_weight"]), 6)
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
    verdict = exposure_verdict(score, direct_hit=direct_hit)
    if direct_hit:
        return "direct sanctioned account anchor"
    if depth == 0:
        return f"{source_node['risk_level'].lower()} anchor node"
    hops = " -> ".join(edge["edge_type"] for edge in path_edges) if path_edges else "anchor"
    return (
        f"{verdict} exposure from {source_node['risk_level'].lower()} anchor "
        f"{source_node['node_key']} at depth {depth} via {hops} (score {score:.3f})"
    )


def compute_exposure(
    nodes: dict[str, dict],
    adjacency: dict[str, list[dict]],
    *,
    max_depth: int,
    top_k: int,
    min_score: float,
    hub_degree_threshold: int,
    today: dt.date,
) -> tuple[list[dict], SearchStats]:
    anchors = [node for node in nodes.values() if source_risk(node.get("risk_level")) > 0.0]
    stats = SearchStats(risk_anchors=len(anchors))
    best_score_by_node: dict[str, float] = {}
    results: dict[str, dict] = {}
    suppressed_hubs: set[str] = set()
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
        heapq.heappush(
            queue,
            (-score, next(seq), key, 0, score, (key,), (), key),
        )

    while queue:
        _neg_score, _n, node_key, depth, current_score, path_nodes, path_edges, source_key = heapq.heappop(queue)
        if current_score < best_score_by_node.get(node_key, 0.0):
            continue
        if depth >= max_depth:
            continue

        neighbors = adjacency.get(node_key, [])
        if len(neighbors) > hub_degree_threshold:
            suppressed_hubs.add(node_key)
            continue

        candidate_edges = neighbors[:top_k]
        filtered_edges = [
            edge for edge in candidate_edges
            if not ignore_weak_edge(edge, today=today)
        ]
        stats.expanded_nodes += 1
        stats.expanded_neighbors += len(filtered_edges)

        for edge in filtered_edges:
            neighbor = edge["neighbor"]
            if neighbor in path_nodes:
                continue
            next_depth = depth + 1
            new_score = current_score * edge["edge_score"] * hop_decay(next_depth)
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

    stats.hub_nodes_suppressed = len(suppressed_hubs)
    rows = []
    for record in results.values():
        node = nodes[record["node_key"]]
        source_node = nodes[record["source_risk_node"]]
        direct_hit = is_direct_sanctioned_account(node, record["source_risk_node"], record["depth"])
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
    stats.rows_written = len(rows)
    return rows, stats


def write_exposure_rows(engine, rows: list[dict], *, reset: bool) -> None:
    batch_size = 500
    with engine.begin() as conn:
        if reset:
            conn.execute(sa.delete(exposure_index))
        if not rows:
            return
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            stmt = pg_insert(exposure_index).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=[exposure_index.c.node_key],
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


def print_summary(stats: SearchStats, *, max_depth: int) -> None:
    print(f"risk anchors: {stats.risk_anchors}")
    print(f"exposure rows written: {stats.rows_written}")
    print(f"max depth reached: {stats.max_depth_reached}")
    print(f"hub nodes suppressed: {stats.hub_nodes_suppressed}")
    print(f"average neighbors expanded: {stats.average_neighbors_expanded:.2f}")
    print()
    print("SQL check:")
    print("select count(*) from exposure_index;")
    print()
    print("select node_key, exposure_score, best_depth, reason")
    print("from exposure_index")
    print("order by exposure_score desc")
    print("limit 10;")


def main() -> None:
    args = parse_args()
    today = dt.date.today()
    engine = get_engine()
    nodes, adjacency = load_graph(engine, today=today)
    rows, stats = compute_exposure(
        nodes,
        adjacency,
        max_depth=args.max_depth,
        top_k=args.top_k,
        min_score=args.min_score,
        hub_degree_threshold=args.hub_degree_threshold,
        today=today,
    )
    write_exposure_rows(engine, rows, reset=args.reset)
    print_summary(stats, max_depth=args.max_depth)


if __name__ == "__main__":
    main()
