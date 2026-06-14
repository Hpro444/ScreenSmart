"""Postgres store for accumulated verdicts (the analyst dossier + live-feed history).

One table: `pipeline_verdict`. Key columns are denormalised for fast querying of the
review queue / landing feed; the full dossier (both modules + reasons + original txn) is
kept as JSONB so the analyst view has everything without extra joins.
"""
from __future__ import annotations
import functools
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Text, Float, DateTime, JSON, text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

metadata = MetaData()

pipeline_verdict = Table(
    "pipeline_verdict", metadata,
    Column("txn_id", Text, primary_key=True),
    Column("decided_at", DateTime(timezone=True), server_default=func.now()),
    Column("combined_verdict", Text, nullable=False, index=True),  # MATCH|REVIEW|NO_MATCH
    Column("status", Text, nullable=False, index=True),            # blocked|review|allowed
    Column("bene_name", Text),
    Column("channel", Text),
    Column("amount", Float),
    Column("dossier", JSONB().with_variant(JSON, "sqlite"), nullable=False),
)

# Audit trail of analyst triage decisions (clear / escalate / block). This is the
# human-in-the-loop record; block/escalate also flag the payee account in graph_nodes so
# the exposure engine can treat it as a derived bad node on the next precompute.
analyst_decision = Table(
    "analyst_decision", metadata,
    Column("txn_id", Text, primary_key=True),
    Column("decision", Text, nullable=False),                      # clear|escalate|block
    Column("analyst", Text),
    Column("account", Text),                                       # bene_account flagged (if any)
    Column("decided_at", DateTime(timezone=True), server_default=func.now()),
)


@functools.lru_cache(maxsize=2)
def get_engine(url: str) -> Engine:
    return create_engine(url, future=True, pool_pre_ping=True)


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)


def upsert_verdict(engine: Engine, rec: dict) -> None:
    """Idempotent upsert keyed by txn_id (at-least-once delivery → exactly-once row)."""
    row = {
        "txn_id": rec["txn_id"],
        "combined_verdict": rec["combined_verdict"],
        "status": rec["status"],
        "bene_name": rec["txn"].get("bene_name") or rec["txn"].get("wallet"),
        "channel": rec["txn"].get("channel"),
        "amount": rec["txn"].get("amount"),
        "dossier": rec,
    }
    stmt = text(
        "INSERT INTO pipeline_verdict (txn_id, combined_verdict, status, bene_name, channel, amount, dossier) "
        "VALUES (:txn_id, :combined_verdict, :status, :bene_name, :channel, :amount, CAST(:dossier AS JSONB)) "
        "ON CONFLICT (txn_id) DO UPDATE SET combined_verdict=EXCLUDED.combined_verdict, "
        "status=EXCLUDED.status, dossier=EXCLUDED.dossier, decided_at=now()"
    )
    import json
    with engine.begin() as conn:
        conn.execute(stmt, {**row, "dossier": json.dumps(row["dossier"], default=str)})


def list_by_status(engine: Engine, status: str, limit: int = 200) -> list[dict]:
    sql = text("SELECT dossier FROM pipeline_verdict WHERE status = :s "
               "ORDER BY decided_at DESC LIMIT :n")
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(sql, {"s": status, "n": limit})]


def get_dossier(engine: Engine, txn_id: str) -> dict | None:
    sql = text("SELECT dossier FROM pipeline_verdict WHERE txn_id = :t")
    with engine.connect() as conn:
        row = conn.execute(sql, {"t": txn_id}).first()
    return row[0] if row else None


def counts(engine: Engine) -> dict:
    sql = text("SELECT status, count(*) FROM pipeline_verdict GROUP BY status")
    with engine.connect() as conn:
        return {s: n for s, n in conn.execute(sql)}


# escalate/block → the engine's anchor levels; clear leaves the graph untouched.
_DECISION_RISK = {"block": "SANCTIONED", "escalate": "SUSPICIOUS"}


def record_decision(engine: Engine, *, txn_id: str, decision: str, analyst: str,
                    account: str | None, account_type: str | None,
                    display_name: str | None, country: str | None) -> dict:
    """Persist an analyst triage decision and, for block/escalate, flag the payee account as
    a risk node in graph_nodes so future exposure precompute propagates from it.

    The flag is marked `risk_source='analyst:<user>'` and never downgrades a real SANCTIONED
    node. Returns {flagged: bool, risk_level: str|None}."""
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO analyst_decision (txn_id, decision, analyst, account) "
            "VALUES (:t, :d, :a, :acc) "
            "ON CONFLICT (txn_id) DO UPDATE SET decision=EXCLUDED.decision, "
            "analyst=EXCLUDED.analyst, account=EXCLUDED.account, decided_at=now()"),
            {"t": txn_id, "d": decision, "a": analyst, "acc": account})

        risk = _DECISION_RISK.get(decision)
        if not (risk and account):
            return {"flagged": False, "risk_level": None}

        # upsert the node; create it if the account isn't yet in the graph. Never downgrade a
        # real sanctions listing. `block` outranks `escalate`; an existing SANCTIONED stays.
        conn.execute(text(
            "INSERT INTO graph_nodes (id, node_key, node_type, display_name, country, "
            "risk_level, risk_source) VALUES (gen_random_uuid(), :k, :nt, :dn, :c, :rl, :src) "
            "ON CONFLICT (node_key) DO UPDATE SET "
            "risk_level = CASE WHEN graph_nodes.risk_level = 'SANCTIONED' THEN 'SANCTIONED' "
            "  WHEN :rl = 'SANCTIONED' THEN 'SANCTIONED' ELSE 'SUSPICIOUS' END, "
            "risk_source = :src"),
            {"k": account, "nt": (account_type or "ACCOUNT"), "dn": display_name,
             "c": country, "rl": risk, "src": f"analyst:{analyst}"})
        return {"flagged": True, "risk_level": risk}


def _graph_and_chain(node_key: str, best_path: list[dict], labels: dict[str, dict]) -> tuple[dict, list]:
    """Rebuild the same {nodes,edges} graph + step-by-step chain the exposure worker emits,
    from a stored best_path enriched with graph_nodes metadata."""
    nodes, edges, chain = [], [], []
    n = len(best_path)
    for i, step in enumerate(best_path):
        nk = step.get("node_key")
        m = labels.get(nk, {})
        risk = str(step.get("risk_level") or m.get("risk_level") or "NONE").upper()
        role = "account" if i == 0 else ("source" if i == n - 1 else "hop")
        ntype = step.get("node_type") or m.get("node_type")
        nodes.append({"id": nk, "label": m.get("display_name") or nk, "type": ntype,
                      "risk": risk, "country": m.get("country"), "role": role})
        flow = str(step.get("semantic_flow") or "")
        edge = step.get("edge_type")
        if i == 0:
            via = "starting account (the payee)"
        elif flow == "outbound_to_anchor":
            via = f"sent funds ({edge}) onward toward the risk source"
        elif flow == "inbound_from_anchor":
            via = f"received funds ({edge}) from upstream"
        else:
            via = f"linked via {edge}" if edge else "linked"
        if i > 0:
            edges.append({"from": best_path[i - 1].get("node_key"), "to": nk,
                          "type": edge, "amount": step.get("amount"), "flow": flow})
        chain.append({"step": i, "node_key": nk, "label": m.get("display_name") or nk,
                      "type": ntype, "risk": risk, "country": m.get("country"),
                      "edge_type": edge, "amount": step.get("amount"), "flow": flow, "via": via})
    graph = {"nodes": nodes, "edges": edges, "depth": max(0, n - 1),
             "source": best_path[-1].get("node_key") if best_path else node_key}
    return graph, chain


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _node_relationships(conn, node_key: str) -> dict:
    """Everything we can say about a node from graph_edges: who it belongs to (holders/
    owners), what it controls, its top counterparties, and aggregate activity."""
    edge_rows = list(conn.execute(text(
        "SELECT from_node_key, to_node_key, edge_type, total_amount, transaction_count, "
        "first_seen, last_seen FROM graph_edges "
        "WHERE from_node_key = :k OR to_node_key = :k"), {"k": node_key}).mappings())

    # collect every counterparty key so we can label them in one query
    other_keys = set()
    for e in edge_rows:
        other_keys.add(e["to_node_key"] if e["from_node_key"] == node_key else e["from_node_key"])
    meta: dict[str, dict] = {}
    if other_keys:
        meta = {r["node_key"]: dict(r) for r in conn.execute(text(
            "SELECT node_key, display_name, country, risk_level, node_type "
            "FROM graph_nodes WHERE node_key = ANY(:ks)"), {"ks": list(other_keys)}).mappings()}

    def label(k):
        m = meta.get(k, {})
        return {"id": k, "label": m.get("display_name") or k, "type": m.get("node_type"),
                "risk": str(m.get("risk_level") or "NONE").upper(), "country": m.get("country")}

    belongs_to, controls, shared = [], [], []
    sent, received = [], []
    out_amt = in_amt = 0.0
    out_tx = in_tx = 0
    first_seen = last_seen = None

    for e in edge_rows:
        et = (e["edge_type"] or "").upper()
        amt = _f(e["total_amount"]); txc = int(e["transaction_count"] or 0)
        fs, ls = e["first_seen"], e["last_seen"]
        if fs and (first_seen is None or fs < first_seen): first_seen = fs
        if ls and (last_seen is None or ls > last_seen): last_seen = ls
        is_from = e["from_node_key"] == node_key
        other = e["to_node_key"] if is_from else e["from_node_key"]

        if et in ("USES_ACCOUNT", "OWNS"):
            if is_from:                                   # this node controls `other`
                controls.append({**label(other), "relation": et})
            else:                                         # `other` holds/owns this node
                belongs_to.append({**label(other), "relation": et})
        elif et == "SHARED_IDENTIFIER":
            shared.append(label(other))
        elif et == "SENT_TO":
            row = {**label(other), "amount": amt, "transaction_count": txc,
                   "first_seen": _iso(fs), "last_seen": _iso(ls)}
            if is_from:
                sent.append(row); out_amt += amt; out_tx += txc
            else:
                received.append(row); in_amt += amt; in_tx += txc

    sent.sort(key=lambda x: x["amount"], reverse=True)
    received.sort(key=lambda x: x["amount"], reverse=True)
    return {
        "belongs_to": belongs_to,
        "controls": controls[:20],
        "shared_identifiers": shared[:20],
        "counterparties": {"sent_to": sent[:8], "received_from": received[:8]},
        "activity": {
            "total_sent": round(out_amt, 2), "total_received": round(in_amt, 2),
            "sent_tx": out_tx, "received_tx": in_tx,
            "counterparties_out": len(sent), "counterparties_in": len(received),
            "first_seen": _iso(first_seen), "last_seen": _iso(last_seen),
        },
    }


def node_view(engine: Engine, node_key: str) -> dict | None:
    """A single graph node's full view: identity + who it belongs to, its counterparties and
    activity, its exposure row (score/depth/reason), and the rebuilt path graph + chain."""
    with engine.connect() as conn:
        meta = conn.execute(text(
            "SELECT node_key, node_type, display_name, country, risk_level, risk_source, created_at "
            "FROM graph_nodes WHERE node_key = :k"), {"k": node_key}).mappings().first()
        if not meta:
            return None
        node = dict(meta)
        node["created_at"] = _iso(node.get("created_at"))
        degree = int(conn.execute(text(
            "SELECT count(*) FROM graph_edges WHERE from_node_key = :k OR to_node_key = :k"),
            {"k": node_key}).scalar() or 0)
        rel = _node_relationships(conn, node_key)
        exp = conn.execute(text(
            "SELECT exposure_score, best_depth, best_path, source_risk_node, reason "
            "FROM exposure_index WHERE node_key = :k"), {"k": node_key}).mappings().first()
        graph, chain, exposure = None, [], None
        if exp:
            best_path = list(exp["best_path"] or [])
            keys = [s.get("node_key") for s in best_path if s.get("node_key")]
            labels: dict[str, dict] = {}
            if keys:
                rows = conn.execute(text(
                    "SELECT node_key, display_name, country, risk_level, node_type "
                    "FROM graph_nodes WHERE node_key = ANY(:ks)"), {"ks": keys}).mappings()
                labels = {r["node_key"]: dict(r) for r in rows}
            graph, chain = _graph_and_chain(node_key, best_path, labels)
            exposure = {"score": float(exp["exposure_score"]), "depth": exp["best_depth"],
                        "reason": exp["reason"], "source": exp["source_risk_node"]}
    return {"node": node, "exposure": exposure, "graph": graph, "chain": chain,
            "degree": degree, **rel}


def flagged_count(engine: Engine) -> int:
    sql = text("SELECT count(*) FROM graph_nodes WHERE risk_source LIKE 'analyst:%'")
    with engine.connect() as conn:
        try:
            return int(conn.execute(sql).scalar() or 0)
        except Exception:
            return 0
