from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import decimal
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "exposure_graph" / "src"))
sys.path.insert(0, str(ROOT / "crypto_exposure_graph" / "src"))

import sqlalchemy as sa

from screensmart.db.database import get_engine as eg_get_engine
from screensmart.db.schema import exposure_index, graph_edges, graph_nodes, synthetic_payments
from screensmart.exposure.lookup import AccountExposureLookup
from screensmart.exposure.precompute import (
    compute_exposure as eg_compute_exposure,
    load_graph as eg_load_graph,
    write_exposure_rows as eg_write_exposure_rows,
)
from screensmart.exposure.scoring import time_decay as eg_time_decay
from screensmart.exposure.synthetic_graph import (
    SyntheticGraphBuilder,
    insert_dataset as eg_insert_dataset,
    metadata as eg_metadata,
    reset_database as eg_reset_database,
)

from crypto_exposure_graph.db.database import get_engine as ceg_get_engine
from crypto_exposure_graph.db.schema import (
    crypto_exposure_index,
    crypto_graph_edges,
    crypto_graph_nodes,
    crypto_synthetic_screenings,
)
from crypto_exposure_graph.exposure.lookup import CryptoWalletExposureLookup
from crypto_exposure_graph.exposure.precompute import (
    compute_exposure as ceg_compute_exposure,
    load_graph as ceg_load_graph,
    write_exposure_rows as ceg_write_exposure_rows,
)
from crypto_exposure_graph.exposure.scoring import time_decay as ceg_time_decay
from crypto_exposure_graph.exposure.synthetic_graph import (
    SyntheticCryptoGraphBuilder,
    insert_dataset as ceg_insert_dataset,
    metadata as ceg_metadata,
    reset_database as ceg_reset_database,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate sanctions-evasion demo report from synthetic data.")
    parser.add_argument("--regenerate", action="store_true", help="rebuild both synthetic datasets and exposure indexes")
    parser.add_argument(
        "--write-markdown",
        action="store_true",
        help="write sanctions.md at repo root from the live demo outputs",
    )
    return parser.parse_args()


def to_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, decimal.Decimal):
        return float(value)
    return float(value)


def regenerate_exposure_graph(seed: int = 42) -> dict[str, Any]:
    engine = eg_get_engine()
    eg_metadata.create_all(engine)
    eg_reset_database(engine)
    builder = SyntheticGraphBuilder(seed=seed)
    builder.build()
    eg_insert_dataset(builder)
    today = dt.date.today()
    nodes, adjacency, load_debug = eg_load_graph(engine, today=today)
    rows, stats = eg_compute_exposure(
        nodes,
        adjacency,
        max_depth=2,
        top_k=20,
        min_score=0.03,
        hub_degree_threshold=200,
        today=today,
    )
    stats.edges_considered = load_debug["edges_considered"]
    stats.adjacency_entries_created = load_debug["adjacency_entries_created"]
    stats.reverse_edges_skipped_due_to_directionality = load_debug["reverse_edges_skipped_due_to_directionality"]
    eg_write_exposure_rows(engine, rows, reset=True)
    with engine.connect() as conn:
        counts = {
            "graph_nodes": conn.scalar(sa.select(sa.func.count()).select_from(graph_nodes)) or 0,
            "graph_edges": conn.scalar(sa.select(sa.func.count()).select_from(graph_edges)) or 0,
            "exposure_index": conn.scalar(sa.select(sa.func.count()).select_from(exposure_index)) or 0,
            "synthetic_payments": conn.scalar(sa.select(sa.func.count()).select_from(synthetic_payments)) or 0,
        }
    return {"builder": builder, "stats": stats, "counts": counts}


def regenerate_crypto_graph(seed: int = 42) -> dict[str, Any]:
    engine = ceg_get_engine()
    ceg_metadata.create_all(engine)
    ceg_reset_database(engine)
    builder = SyntheticCryptoGraphBuilder(seed=seed)
    builder.build()
    ceg_insert_dataset(builder)
    today = dt.date.today()
    nodes, adjacency, load_debug = ceg_load_graph(engine, today=today)
    rows, stats = ceg_compute_exposure(
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
    ceg_write_exposure_rows(engine, rows, reset=True)
    with engine.connect() as conn:
        counts = {
            "crypto_graph_nodes": conn.scalar(sa.select(sa.func.count()).select_from(crypto_graph_nodes)) or 0,
            "crypto_graph_edges": conn.scalar(sa.select(sa.func.count()).select_from(crypto_graph_edges)) or 0,
            "crypto_exposure_index": conn.scalar(sa.select(sa.func.count()).select_from(crypto_exposure_index)) or 0,
            "crypto_synthetic_screenings": conn.scalar(sa.select(sa.func.count()).select_from(crypto_synthetic_screenings)) or 0,
        }
    return {"builder": builder, "stats": stats, "counts": counts}


FIAT_SCENARIOS = [
    {
        "title": "Direct sanctioned counterparty",
        "module": "fiat",
        "scenario_type": "direct_sanctioned_iban",
        "why": "The beneficiary IBAN itself is sanctioned. This is a hard block, not an indirect proxy-network case.",
        "expected_action": "MATCH",
        "expected_reason_codes": ["DIRECT_SANCTIONS_MATCH"],
    },
    {
        "title": "Outbound payment to sanctioned entity",
        "module": "fiat",
        "scenario_type": "outbound_to_sanctioned",
        "why": "The screened beneficiary previously sent a large recent payment directly to a sanctioned IBAN. Direction matters: this is outbound-to-sanctioned evidence.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["OUTBOUND_1_HOP_TO_SANCTIONED"],
    },
    {
        "title": "Inbound funds from sanctioned entity",
        "module": "fiat",
        "scenario_type": "one_hop_exposure",
        "why": "The beneficiary received funds directly from a sanctioned account. This is directional inbound exposure.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["INBOUND_FROM_SANCTIONED"],
    },
    {
        "title": "Two-hop sanctions exposure",
        "module": "fiat",
        "scenario_type": "two_hop_exposure",
        "why": "Funds route through an intermediary account before reaching the beneficiary. The route is still short and recent enough to justify review.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["INBOUND_FROM_SANCTIONED"],
    },
    {
        "title": "Sanctioned entity to shell company to clean-looking beneficiary",
        "module": "fiat",
        "scenario_type": "sanctioned_entity_to_shell_to_beneficiary",
        "why": "A sanctioned owner controls a shell company account that then pays a clean-looking beneficiary. The path is indirect but operationally suspicious.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["SHARED_INTERMEDIARY_WITH_SANCTIONED", "PROXY_ACCOUNT_BEHAVIOR"],
    },
    {
        "title": "Clean customer to shell company to sanctioned entity",
        "module": "fiat",
        "scenario_type": "clean_customer_to_shell_to_sanctioned",
        "why": "The beneficiary account has outbound history that leads through a shell company to a sanctioned destination. That is stronger than passive inbound contamination.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["OUTBOUND_2_HOP_TO_SANCTIONED"],
    },
    {
        "title": "Shell company pass-through structuring",
        "module": "fiat",
        "scenario_type": "shell_structuring_pass_through",
        "why": "Many small inflows collect in a shell account, followed by a large outbound transfer to a sanctioned destination.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["PROXY_ACCOUNT_BEHAVIOR"],
    },
    {
        "title": "Abnormal value to a new counterparty",
        "module": "fiat",
        "scenario_type": "abnormal_new_counterparty_company",
        "why": "A newly active low-activity company account makes one large recent payment to a sanctioned counterparty.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["OUTBOUND_1_HOP_TO_SANCTIONED", "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY"],
    },
    {
        "title": "High concentration flow into a low-activity shell account",
        "module": "fiat",
        "scenario_type": "high_concentration_to_shell",
        "why": "Most outgoing value from a sanctioned sender concentrates into one suspicious shell account, which is atypical for legitimate commercial behavior.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["PROXY_ACCOUNT_BEHAVIOR"],
    },
    {
        "title": "Shared intermediary false-positive suppression",
        "module": "fiat",
        "scenario_type": "shared_hub_false_positive_prevented",
        "why": "A clean account shares only a downstream hub with a sanctioned sender. The system should discount this as weak shared-hub evidence.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["SHARED_INTERMEDIARY_WITH_SANCTIONED"],
    },
    {
        "title": "Derived anchor precompute: Milica routes directly to sanctioned",
        "module": "fiat",
        "scenario_type": "derived_anchor_milica_to_sanctioned",
        "why": "Milica directly pays a sanctioned endpoint. That makes her account a strong derived-risk anchor candidate for the second offline pass.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["OUTBOUND_1_HOP_TO_SANCTIONED", "DERIVED_RISK_ANCHOR"],
    },
    {
        "title": "Derived anchor precompute: Mateja funds derived anchor",
        "module": "fiat",
        "scenario_type": "mateja_shell_to_derived_anchor",
        "why": "Mateja behaves like a shell account that routes material value into Milica, who already routes directly to sanctions. The account should still be a normal REVIEW, but also qualify as a derived-risk anchor.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["OUTBOUND_2_HOP_TO_SANCTIONED", "DERIVED_RISK_ANCHOR"],
    },
    {
        "title": "Derived anchor precompute: Andrija funds derived proxy",
        "module": "fiat",
        "scenario_type": "andrija_funds_derived_proxy",
        "why": "Andrija does not have a direct 3-hop runtime traversal. He becomes reviewable only because the offline second pass recognized Mateja as a derived sanctions proxy and then evaluated Andrija's direct funding into that proxy account.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["UPSTREAM_FUNDING_OF_DERIVED_SANCTIONS_PROXY", "PROXY_CHAIN_FUNDING"],
    },
    {
        "title": "Derived anchor precompute: tiny upstream funding suppressed",
        "module": "fiat",
        "scenario_type": "tiny_upstream_funding_suppressed",
        "why": "A tiny payment into an otherwise suspicious downstream shell chain should remain suppressed. Derived-anchor propagation should not rescue dust-like funding.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["DERIVED_RISK_PROPAGATION_SUPPRESSED"],
    },
    {
        "title": "Derived anchor precompute: hub-crossing upstream funding suppressed",
        "module": "fiat",
        "scenario_type": "hub_upstream_funding_suppressed",
        "why": "Funding that crosses a bank hub before reaching the shell/proxy chain should remain out of scope for the second pass because the payer is not a direct upstream funder of the derived anchor.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["NO_EXPOSURE_INDEX_ENTRY"],
    },
    {
        "title": "Derived anchor precompute: high concentration without sanctions path control",
        "module": "fiat",
        "scenario_type": "normal_high_concentration_control_no_match",
        "why": "High concentration without any sanctioned or derived-anchor path must stay clean.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["NO_EXPOSURE_INDEX_ENTRY"],
    },
]

CRYPTO_SCENARIOS = [
    {
        "title": "Crypto derived anchor: Milica routes directly to sanctioned wallet",
        "module": "crypto",
        "scenario_type": "crypto_derived_anchor_milica_to_sanctioned",
        "why": "Milica wallet sends material recent value directly to a sanctioned wallet. That makes it a strong derived-risk anchor candidate for the second offline pass.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["OUTBOUND_1_HOP_TO_SANCTIONED", "CRYPTO_DERIVED_RISK_ANCHOR"],
    },
    {
        "title": "Crypto derived anchor: Mateja funds derived anchor",
        "module": "crypto",
        "scenario_type": "crypto_mateja_to_derived_anchor",
        "why": "Mateja wallet materially funds Milica, and Milica already routes directly to a sanctioned wallet. Mateja should remain a normal REVIEW while also becoming a crypto derived-risk anchor.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["OUTBOUND_2_HOP_TO_SANCTIONED", "CRYPTO_DERIVED_RISK_ANCHOR"],
    },
    {
        "title": "Crypto derived anchor: Andrija funds derived proxy",
        "module": "crypto",
        "scenario_type": "crypto_andrija_funds_derived_proxy",
        "why": "Andrija has no direct 3-hop runtime traversal. He becomes reviewable only because the offline second pass recognized Mateja as a derived crypto proxy and then evaluated Andrija's direct funding into that proxy wallet.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY", "CRYPTO_PROXY_CHAIN_FUNDING"],
    },
    {
        "title": "Crypto derived anchor: tiny upstream funding suppressed",
        "module": "crypto",
        "scenario_type": "crypto_tiny_upstream_funding_suppressed",
        "why": "Tiny upstream funding into a downstream proxy chain should remain suppressed even when the downstream wallets connect to sanctions.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED"],
    },
    {
        "title": "Crypto derived anchor: exchange upstream funding suppressed",
        "module": "crypto",
        "scenario_type": "crypto_exchange_upstream_funding_suppressed",
        "why": "An upstream payer that only touches the proxy chain through an exchange hot wallet must stay out of scope for derived-risk propagation.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["NO_EXPOSURE_INDEX_ENTRY"],
    },
    {
        "title": "Crypto derived anchor: bridge or mixer upstream suppressed",
        "module": "crypto",
        "scenario_type": "crypto_bridge_or_mixer_upstream_suppressed",
        "why": "An upstream payer that only reaches the downstream proxy chain through a bridge or mixer service boundary must remain suppressed.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["NO_EXPOSURE_INDEX_ENTRY"],
    },
    {
        "title": "Crypto derived anchor: normal high concentration control",
        "module": "crypto",
        "scenario_type": "crypto_normal_high_concentration_control_no_match",
        "why": "High concentration without any sanctions path must remain a clean control case.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["NO_EXPOSURE_INDEX_ENTRY"],
    },
    {
        "title": "Crypto derived anchor: old weak anchor suppressed",
        "module": "crypto",
        "scenario_type": "crypto_old_weak_derived_anchor_suppressed",
        "why": "Funding into a wallet whose only downstream sanctions relation is old, weak, and dust-like should remain suppressed.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["NO_EXPOSURE_INDEX_ENTRY"],
    },
    {
        "title": "Exchange false-positive suppression",
        "module": "crypto",
        "scenario_type": "exchange_contamination_prevented",
        "why": "A sanctioned wallet touched a shared exchange hot wallet, but unrelated customers withdrawing later should remain clean.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["HUB_PATH_DISCOUNTED"],
    },
    {
        "title": "Dust exposure suppression",
        "module": "crypto",
        "scenario_type": "isolated_dust_exposure",
        "why": "A one-off tiny indirect exposure should be discounted and not escalate to review.",
        "expected_action": "NO_MATCH",
        "expected_reason_codes": ["DUST_EXPOSURE_DISCOUNTED"],
    },
    {
        "title": "Repeated small transfers aggregate into material exposure",
        "module": "crypto",
        "scenario_type": "repeated_small_transfers_to_risky_wallet",
        "why": "Ten thousand small transfers aggregate into a material amount and should not be treated as dust.",
        "expected_action": "REVIEW",
        "expected_reason_codes": ["INBOUND_FROM_SANCTIONED", "PROXY_ACCOUNT_BEHAVIOR"],
    },
]


def _fetch_fiat_cases(scenario_type: str) -> list[dict[str, Any]]:
    engine = eg_get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(
                synthetic_payments.c.case_id,
                synthetic_payments.c.scenario_type,
                synthetic_payments.c.recipient_name,
                synthetic_payments.c.recipient_iban,
                synthetic_payments.c.recipient_country,
                synthetic_payments.c.amount,
                synthetic_payments.c.currency,
                synthetic_payments.c.expected_verdict,
                synthetic_payments.c.ground_truth_reason,
            )
            .where(synthetic_payments.c.scenario_type == scenario_type)
            .order_by(synthetic_payments.c.case_id)
        ).all()
        if not rows:
            raise RuntimeError(f"Missing fiat scenario {scenario_type}")
    return [dict(row._mapping) for row in rows]


def _fetch_crypto_cases(scenario_type: str) -> list[dict[str, Any]]:
    engine = ceg_get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(
                crypto_synthetic_screenings.c.case_id,
                crypto_synthetic_screenings.c.scenario_type,
                crypto_synthetic_screenings.c.chain,
                crypto_synthetic_screenings.c.wallet_address,
                crypto_synthetic_screenings.c.asset,
                crypto_synthetic_screenings.c.amount_usd,
                crypto_synthetic_screenings.c.expected_verdict,
                crypto_synthetic_screenings.c.ground_truth_reason,
            )
            .where(crypto_synthetic_screenings.c.scenario_type == scenario_type)
            .order_by(crypto_synthetic_screenings.c.case_id)
        ).all()
        if not rows:
            raise RuntimeError(f"Missing crypto scenario {scenario_type}")
    return [dict(row._mapping) for row in rows]


def _fetch_fiat_nodes(node_keys: list[str]) -> dict[str, dict]:
    if not node_keys:
        return {}
    engine = eg_get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(
                graph_nodes.c.node_key,
                graph_nodes.c.node_type,
                graph_nodes.c.display_name,
                graph_nodes.c.country,
                graph_nodes.c.risk_level,
            ).where(graph_nodes.c.node_key.in_(node_keys))
        )
        return {row.node_key: dict(row._mapping) for row in rows}


def _fetch_crypto_nodes(node_keys: list[str]) -> dict[str, dict]:
    if not node_keys:
        return {}
    engine = ceg_get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            sa.select(
                crypto_graph_nodes.c.node_key,
                crypto_graph_nodes.c.chain,
                crypto_graph_nodes.c.address,
                crypto_graph_nodes.c.node_type,
                crypto_graph_nodes.c.display_name,
                crypto_graph_nodes.c.risk_level,
            ).where(crypto_graph_nodes.c.node_key.in_(node_keys))
        )
        return {row.node_key: dict(row._mapping) for row in rows}


def _fetch_relevant_fiat_edges(target_iban: str, path_keys: list[str]) -> list[dict]:
    engine = eg_get_engine()
    with engine.connect() as conn:
        immediate_rows = list(
            conn.execute(
                sa.select(
                    graph_edges.c.from_node_key,
                    graph_edges.c.to_node_key,
                    graph_edges.c.edge_type,
                    graph_edges.c.total_amount,
                    graph_edges.c.transaction_count,
                    graph_edges.c.first_seen,
                    graph_edges.c.last_seen,
                    graph_edges.c.confidence,
                ).where(
                    sa.or_(
                        graph_edges.c.from_node_key == target_iban,
                        graph_edges.c.to_node_key == target_iban,
                    )
                )
            )
        )
        related_keys = {target_iban, *path_keys}
        for row in immediate_rows:
            related_keys.add(row.from_node_key)
            related_keys.add(row.to_node_key)
        related_rows = list(
            conn.execute(
                sa.select(
                    graph_edges.c.from_node_key,
                    graph_edges.c.to_node_key,
                    graph_edges.c.edge_type,
                    graph_edges.c.total_amount,
                    graph_edges.c.transaction_count,
                    graph_edges.c.first_seen,
                    graph_edges.c.last_seen,
                    graph_edges.c.confidence,
                ).where(
                    sa.or_(
                        graph_edges.c.from_node_key.in_(related_keys),
                        graph_edges.c.to_node_key.in_(related_keys),
                    )
                )
            )
        )
    merged = {(
        row.from_node_key,
        row.to_node_key,
        row.edge_type,
    ): {
        "from_node_key": row.from_node_key,
        "to_node_key": row.to_node_key,
        "edge_type": row.edge_type,
        "total_amount": to_number(row.total_amount),
        "transaction_count": int(row.transaction_count or 0),
        "first_seen": row.first_seen.isoformat() if row.first_seen else None,
        "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        "confidence": to_number(row.confidence),
    } for row in [*immediate_rows, *related_rows]}
    return sorted(merged.values(), key=lambda item: (-item["total_amount"], item["edge_type"]))[:12]


def _fetch_relevant_crypto_edges(target_key: str, path_keys: list[str]) -> list[dict]:
    engine = ceg_get_engine()
    with engine.connect() as conn:
        immediate_rows = list(
            conn.execute(
                sa.select(
                    crypto_graph_edges.c.from_node_key,
                    crypto_graph_edges.c.to_node_key,
                    crypto_graph_edges.c.edge_type,
                    crypto_graph_edges.c.total_usd_value,
                    crypto_graph_edges.c.transaction_count,
                    crypto_graph_edges.c.first_seen,
                    crypto_graph_edges.c.last_seen,
                    crypto_graph_edges.c.confidence,
                ).where(
                    sa.or_(
                        crypto_graph_edges.c.from_node_key == target_key,
                        crypto_graph_edges.c.to_node_key == target_key,
                    )
                )
            )
        )
        related_keys = {target_key, *path_keys}
        for row in immediate_rows:
            related_keys.add(row.from_node_key)
            related_keys.add(row.to_node_key)
        related_rows = list(
            conn.execute(
                sa.select(
                    crypto_graph_edges.c.from_node_key,
                    crypto_graph_edges.c.to_node_key,
                    crypto_graph_edges.c.edge_type,
                    crypto_graph_edges.c.total_usd_value,
                    crypto_graph_edges.c.transaction_count,
                    crypto_graph_edges.c.first_seen,
                    crypto_graph_edges.c.last_seen,
                    crypto_graph_edges.c.confidence,
                ).where(
                    sa.or_(
                        crypto_graph_edges.c.from_node_key.in_(related_keys),
                        crypto_graph_edges.c.to_node_key.in_(related_keys),
                    )
                )
            )
        )
    merged = {(
        row.from_node_key,
        row.to_node_key,
        row.edge_type,
    ): {
        "from_node_key": row.from_node_key,
        "to_node_key": row.to_node_key,
        "edge_type": row.edge_type,
        "total_usd_value": to_number(row.total_usd_value),
        "transaction_count": int(row.transaction_count or 0),
        "first_seen": row.first_seen.isoformat() if row.first_seen else None,
        "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        "confidence": to_number(row.confidence),
    } for row in [*immediate_rows, *related_rows]}
    return sorted(merged.values(), key=lambda item: (-item["total_usd_value"], item["edge_type"]))[:12]


def _format_runtime_output(result: Any) -> dict[str, Any]:
    return {
        "verdict": result.recommended_action.value,
        "risk_type": result.risk_type,
        "risk_score": round(float(result.risk_score), 4),
        "evasion_typology": result.evasion_typology,
        "primary_reason": result.primary_reason,
        "evidence": result.evidence,
    }


def _edge_math_from_path_entry(module: str, entry: dict) -> dict[str, Any]:
    if module == "fiat":
        last_seen = dt.date.fromisoformat(entry["last_seen"]) if entry.get("last_seen") else None
        return {
            "edge_type": entry.get("edge_type"),
            "semantic_flow": entry.get("semantic_flow"),
            "amount": round(float(entry.get("amount") or 0.0), 4),
            "flow_materiality_weight": round(float(entry.get("flow_materiality_weight") or 0.0), 4),
            "concentration": round(float(entry.get("flow_concentration") or 0.0), 4),
            "time_decay": round(float(eg_time_decay(last_seen, today=dt.date.today())), 4),
            "directional_multiplier": round(float(entry.get("directional_multiplier") or 1.0), 4),
        }
    last_seen = dt.date.fromisoformat(entry["last_seen"]) if entry.get("last_seen") else None
    return {
        "edge_type": entry.get("edge_type"),
        "semantic_flow": entry.get("semantic_flow"),
        "total_usd_value": round(float(entry.get("total_usd_value") or 0.0), 4),
        "crypto_materiality_weight": round(float(entry.get("crypto_materiality_weight") or 0.0), 4),
        "concentration_score": round(float(entry.get("concentration_score") or 0.0), 4),
        "flow_concentration": round(float(entry.get("flow_concentration") or 0.0), 4),
        "time_decay": round(float(ceg_time_decay(last_seen, today=dt.date.today())), 4),
        "hub_penalty": round(float(entry.get("hub_penalty") or 0.0), 4),
        "directional_multiplier": round(float(entry.get("directional_multiplier") or 1.0), 4),
    }


def _involved_entities_from_result(module: str, result: Any, extra_edges: list[dict], target_key: str) -> list[dict]:
    path_keys = [node["node_key"] for node in result.best_path]
    edge_keys = []
    for edge in extra_edges:
        edge_keys.extend([edge["from_node_key"], edge["to_node_key"]])
    keys = list(dict.fromkeys([target_key, *path_keys, *edge_keys]))
    nodes = _fetch_fiat_nodes(keys) if module == "fiat" else _fetch_crypto_nodes(keys)
    ordered = []
    for key in keys:
        node = nodes.get(key)
        if node is None:
            ordered.append({"node_key": key})
        else:
            ordered.append(node)
    return ordered


def _render_example_markdown(example: dict[str, Any]) -> str:
    expected_evidence = [
        {
            "reason_code": code,
            "severity": "EXPECTED",
            "score_contribution": "scenario-dependent",
        }
        for code in example["expected_reason_codes"]
    ]
    scoring_lines = []
    for row in example["intermediate_math"]:
        scoring_lines.append(f"- `{row}`")
    evidence_with_factors = [item for item in example["runtime_output"]["evidence"] if item.get("decision_factors")]
    decision_factor_payload = evidence_with_factors[0]["decision_factors"] if evidence_with_factors else {}
    observed_reason_codes = [
        item["reason_code"] for item in example["runtime_output"]["evidence"]
    ] or ["NO_EXPOSURE_INDEX_ENTRY"]
    derived_context = None
    for item in example["runtime_output"]["evidence"]:
        derived_context = item.get("decision_factors", {}).get("derived_anchor_context")
        if derived_context:
            break
    return "\n".join(
        [
            f"## {example['title']}",
            "",
            f"Scenario source: `{example['scenario_type']}` in `{example['module']}`",
            "",
            "**Why this case is suspicious or clean**",
            "",
            example["why"],
            "",
            "**Expected decision**",
            "",
            f"- `recommended_action`: `{example['expected_action']}`",
            f"- `expected reason codes`: `{', '.join(example['expected_reason_codes'])}`",
            f"- `observed decision`: `{example['observed_verdict']}`",
            f"- `observed reason codes`: `{', '.join(observed_reason_codes)}`",
            "",
            "**Expected evidence package**",
            "",
            "```json",
            json.dumps(expected_evidence, indent=2),
            "```",
            "",
            "**Synthetic transaction rows**",
            "",
            "```json",
            json.dumps(example["synthetic_rows"], indent=2),
            "```",
            "",
            "**Involved accounts, wallets, and entities**",
            "",
            "```json",
            json.dumps(example["involved_entities"], indent=2),
            "```",
            "",
            "**Decision factors**",
            "",
            f"- `base path evidence`: `{example['runtime_output']['evidence'][0]['reason_code'] if example['runtime_output']['evidence'] else 'NONE'}`",
            f"- `transaction pattern evidence`: `{decision_factor_payload}`",
            f"- `derived anchor explanation`: `{derived_context}`",
            f"- `concentration/materiality evidence`: `{example['intermediate_math']}`",
            f"- `final score contribution`: `{[(item['reason_code'], item['score_contribution']) for item in example['runtime_output']['evidence']]}`",
            "",
            "**Intermediate scoring math**",
            "",
            f"- `graph/exposure score`: `{example['graph_score']:.4f}`",
            f"- `risk_score`: `{example['risk_score']:.4f}`",
            f"- `sanctions_evasion_score`: `{example['sanctions_evasion_score']:.4f}`",
            f"- `discounts or uplifts`: `{', '.join(example['discounts']) if example['discounts'] else 'none'}`",
            *scoring_lines,
            "",
            "**Actual CLI/demo output**",
            "",
            "```json",
            json.dumps(example["runtime_output"], indent=2),
            "```",
            "",
        ]
    )


def _collect_fiat_example(spec: dict[str, Any]) -> dict[str, Any]:
    lookup = AccountExposureLookup.load()
    case = None
    result = None
    for candidate in _fetch_fiat_cases(spec["scenario_type"]):
        candidate_result = lookup.screen_account(candidate["recipient_iban"])
        if candidate_result.recommended_action.value != spec["expected_action"]:
            continue
        missing_codes = [code for code in spec["expected_reason_codes"] if code not in candidate_result.rule_triggers]
        if missing_codes:
            continue
        case = candidate
        result = candidate_result
        break
    if case is None or result is None:
        raise RuntimeError(f"{spec['scenario_type']} did not produce the expected decision and reason-code package")
    path_keys = [node["node_key"] for node in result.best_path]
    synthetic_rows = _fetch_relevant_fiat_edges(case["recipient_iban"], path_keys)
    involved_entities = _involved_entities_from_result("fiat", result, synthetic_rows, case["recipient_iban"])
    intermediate_math = [_edge_math_from_path_entry("fiat", node) for node in result.best_path[1:]]
    discounts = [item["reason_code"] for item in result.evidence if float(item["score_contribution"]) < 0]
    return {
        "title": spec["title"],
        "module": "transaction_graph_exposure",
        "scenario_type": spec["scenario_type"],
        "why": spec["why"],
        "expected_action": spec["expected_action"],
        "expected_reason_codes": spec["expected_reason_codes"],
        "synthetic_rows": synthetic_rows,
        "involved_entities": involved_entities,
        "graph_score": float(result.graph_exposure_score),
        "risk_score": float(result.risk_score),
        "sanctions_evasion_score": float(result.sanctions_evasion_score),
        "intermediate_math": intermediate_math,
        "discounts": discounts,
        "runtime_output": _format_runtime_output(result),
        "expected_verdict": case["expected_verdict"],
        "observed_verdict": result.recommended_action.value,
    }


def _collect_crypto_example(spec: dict[str, Any]) -> dict[str, Any]:
    lookup = CryptoWalletExposureLookup.load()
    case = None
    result = None
    for candidate in _fetch_crypto_cases(spec["scenario_type"]):
        candidate_result = lookup.screen_wallet(
            candidate["chain"],
            candidate["wallet_address"],
            asset=candidate["asset"],
            amount_usd=to_number(candidate["amount_usd"]),
        )
        if candidate_result.recommended_action.value != spec["expected_action"]:
            continue
        missing_codes = [code for code in spec["expected_reason_codes"] if code not in candidate_result.rule_triggers]
        if missing_codes:
            continue
        case = candidate
        result = candidate_result
        break
    if case is None or result is None:
        raise RuntimeError(f"{spec['scenario_type']} did not produce the expected decision and reason-code package")
    target_key = f"{case['chain'].upper()}:{case['wallet_address'].lower()}"
    path_keys = [node["node_key"] for node in result.best_path]
    synthetic_rows = _fetch_relevant_crypto_edges(target_key, path_keys)
    involved_entities = _involved_entities_from_result("crypto", result, synthetic_rows, target_key)
    intermediate_math = [_edge_math_from_path_entry("crypto", node) for node in result.best_path[1:]]
    discounts = [item["reason_code"] for item in result.evidence if float(item["score_contribution"]) < 0]
    return {
        "title": spec["title"],
        "module": "crypto_wallet_exposure",
        "scenario_type": spec["scenario_type"],
        "why": spec["why"],
        "expected_action": spec["expected_action"],
        "expected_reason_codes": spec["expected_reason_codes"],
        "synthetic_rows": synthetic_rows,
        "involved_entities": involved_entities,
        "graph_score": float(result.graph_exposure_score),
        "risk_score": float(result.risk_score),
        "sanctions_evasion_score": float(result.sanctions_evasion_score),
        "intermediate_math": intermediate_math,
        "discounts": discounts,
        "runtime_output": _format_runtime_output(result),
        "expected_verdict": case["expected_verdict"],
        "observed_verdict": result.recommended_action.value,
    }


def build_examples() -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for spec in FIAT_SCENARIOS:
        examples.append(_collect_fiat_example(spec))
    for spec in CRYPTO_SCENARIOS:
        examples.append(_collect_crypto_example(spec))
    return examples


def write_markdown(examples: list[dict[str, Any]], *, path: Path) -> None:
    lines = [
        "# Sanctions Evasion Demo",
        "",
        "This document is generated from live synthetic data and live runtime lookup output.",
        "",
        "Regenerate it with:",
        "",
        "```powershell",
        "python scripts/generate_sanctions_report.py --regenerate --write-markdown",
        "```",
        "",
        "Every example below contains:",
        "",
        "- synthetic transaction rows from the graph",
        "- involved accounts, wallets, and entities",
        "- expected decision and reason codes",
        "- actual runtime output",
        "- intermediate scoring math",
        "",
        "Reason-code implementation audit:",
        "",
        "- `DIRECT_SANCTIONS_MATCH` and `SANCTIONED_WALLET_MATCH` are implemented from direct sanctioned entity or wallet hits.",
        "- `OUTBOUND_1_HOP_TO_SANCTIONED` and `OUTBOUND_2_HOP_TO_SANCTIONED` are implemented from policy-valid reverse flow evidence on directed payment edges.",
        "- `INBOUND_FROM_SANCTIONED` is implemented from direct forward flow from sanctioned sources.",
        "- `SHARED_INTERMEDIARY_WITH_SANCTIONED` is implemented for indirect sanctioned paths that are not clean directional inbound or outbound routes.",
        "- `PROXY_ACCOUNT_BEHAVIOR` is implemented from intermediary routing, pass-through structure, or proxy-like account chains.",
        "- `ABNORMAL_VALUE_TO_NEW_COUNTERPARTY` is implemented from large recent transfers to newly observed counterparties.",
        "- `HIGH_RISK_CORRIDOR` is implemented in the fiat graph from source-country corridor risk and in the crypto graph from bridge-route usage.",
        "- `HUB_PATH_DISCOUNTED` is implemented from shared hub, exchange, or service-boundary suppression.",
        "- `OLD_EXPOSURE_DISCOUNTED` is implemented from stale historical exposure.",
        "- `DUST_EXPOSURE_DISCOUNTED` is implemented in crypto from isolated dust exposure.",
        "- `CRYPTO_DERIVED_RISK_ANCHOR` is implemented when a wallet already has strong direct crypto sanctions-evasion evidence and becomes eligible for the offline second-pass upstream-funding check.",
        "- `UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY` and `CRYPTO_PROXY_CHAIN_FUNDING` are implemented only from the offline derived-anchor precompute pass, never from runtime traversal.",
        "- `CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED` is implemented when a direct upstream funder exists but materiality, recency, or service-boundary rules suppress the second-pass escalation.",
        "- High concentration and repeated structuring are implemented as scoring inputs and evidence context, not as standalone reason codes in the current sanctions model.",
        "- No demo reason code below is a placeholder string without backing logic.",
        "",
    ]
    grouped = {
        "Fiat Transaction Graph Scenarios": [],
        "Derived Risk Anchor Precompute": [],
        "Crypto Derived Risk Anchor Precompute": [],
        "Crypto Wallet Scenarios": [],
    }
    for example in examples:
        scenario_type = example["scenario_type"]
        if scenario_type in {
            "derived_anchor_milica_to_sanctioned",
            "mateja_shell_to_derived_anchor",
            "andrija_funds_derived_proxy",
            "tiny_upstream_funding_suppressed",
            "hub_upstream_funding_suppressed",
            "normal_high_concentration_control_no_match",
        }:
            grouped["Derived Risk Anchor Precompute"].append(example)
        elif scenario_type in {
            "crypto_derived_anchor_milica_to_sanctioned",
            "crypto_mateja_to_derived_anchor",
            "crypto_andrija_funds_derived_proxy",
            "crypto_tiny_upstream_funding_suppressed",
            "crypto_exchange_upstream_funding_suppressed",
            "crypto_bridge_or_mixer_upstream_suppressed",
            "crypto_normal_high_concentration_control_no_match",
            "crypto_old_weak_derived_anchor_suppressed",
        }:
            grouped["Crypto Derived Risk Anchor Precompute"].append(example)
        elif example["module"] == "crypto_wallet_exposure":
            grouped["Crypto Wallet Scenarios"].append(example)
        else:
            grouped["Fiat Transaction Graph Scenarios"].append(example)

    for section, section_examples in grouped.items():
        lines.extend([f"# {section}", ""])
        for example in section_examples:
            lines.append(_render_example_markdown(example))
    path.write_text("\n".join(lines), encoding="utf-8")


def print_expected_vs_observed(examples: list[dict[str, Any]]) -> None:
    print("Sanctions Evasion Expected vs Observed")
    print()
    for example in examples:
        print(
            f"{example['scenario_type']}: expected={example['expected_verdict']} "
            f"observed={example['observed_verdict']} "
            f"reason_codes={','.join(dict.fromkeys(item['reason_code'] for item in example['runtime_output']['evidence'])) or '-'}"
        )


def main() -> None:
    args = parse_args()
    if args.regenerate:
        regenerate_exposure_graph()
        regenerate_crypto_graph()
    examples = build_examples()
    print_expected_vs_observed(examples)
    if args.write_markdown:
        write_markdown(examples, path=ROOT / "sanctions.md")
        print()
        print(f"Wrote {(ROOT / 'sanctions.md')}")


if __name__ == "__main__":
    main()
