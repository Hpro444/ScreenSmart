"""Generate a synthetic crypto wallet exposure graph and load it into Postgres.

Run:
    python -m crypto_exposure_graph.exposure.synthetic_graph --seed 42 --reset
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import decimal
import random
import uuid

import sqlalchemy as sa

from ..db.database import get_engine
from ..db.schema import (
    crypto_exposure_index,
    crypto_graph_edges,
    crypto_graph_nodes,
    crypto_synthetic_screenings,
    metadata,
)

TODAY = dt.date(2026, 6, 13)
CHAINS = ["ETH", "TRON", "BSC", "ARB", "BTC"]
ASSETS = ["ETH", "USDT", "USDC", "BTC", "BNB"]

SCENARIO_COUNTS = {
    "direct_sanctioned_wallet": 30,
    "one_hop_wallet_exposure": 40,
    "two_hop_wallet_exposure": 40,
    "crypto_derived_anchor_milica_to_sanctioned": 20,
    "crypto_mateja_to_derived_anchor": 20,
    "crypto_andrija_funds_derived_proxy": 20,
    "crypto_tiny_upstream_funding_suppressed": 20,
    "crypto_exchange_upstream_funding_suppressed": 20,
    "crypto_bridge_or_mixer_upstream_suppressed": 20,
    "crypto_normal_high_concentration_control_no_match": 20,
    "crypto_old_weak_derived_anchor_suppressed": 20,
    "repeated_small_transfers_to_risky_wallet": 30,
    "isolated_dust_exposure": 30,
    "exchange_contamination_prevented": 30,
    "bridge_contamination_prevented": 30,
    "mixer_route": 20,
    "bridge_route": 20,
    "ransomware_cluster": 20,
    "exchange_hot_wallet_noise": 20,
    "smart_contract_noise": 20,
    "clean_wallet": 60,
}

MIN_GRAPH_NODES = 250
MIN_GRAPH_EDGES = 220
MIN_SYNTHETIC_SCREENINGS = 150


def money(value: float | int) -> decimal.Decimal:
    return decimal.Decimal(str(round(float(value), 2)))


class SyntheticCryptoGraphBuilder:
    """Build a deterministic synthetic crypto graph for Phase 2 wallet exposure.

    This generator mirrors the structure of the fiat `exposure_graph` module:

    - create graph nodes and aggregated edges
    - create labeled lookup requests for the demo
    - rely on offline precompute to materialize `crypto_exposure_index`

    Phase 2 keeps the same architecture, but expands synthetic coverage for:

    - concentration-aware scoring
    - dust vs structuring separation
    - mixer and bridge routes
    - exchange / bridge / smart-contract contamination suppression
    - ransomware-style risk anchors
    """

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.run_tag = f"s{seed}"
        self.node_seq = 0
        self.case_seq = 0
        self.nodes: list[dict] = []
        self.node_keys: set[str] = set()
        self.edges_by_key: dict[tuple[str, str, str], dict] = {}
        self.screenings: list[dict] = []

    def _uuid(self, kind: str, key: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"crypto-exposure:{self.seed}:{kind}:{key}")

    def _normalize_chain(self, chain: str) -> str:
        return str(chain or "ETH").upper()

    def _normalize_address(self, address: str) -> str:
        return str(address or "").lower()

    def _node_key(self, chain: str, address: str) -> str:
        return f"{self._normalize_chain(chain)}:{self._normalize_address(address)}"

    def _new_address(self, chain: str, *, node_type: str) -> str:
        self.node_seq += 1
        chain = self._normalize_chain(chain)
        if chain == "BTC":
            return f"bc1q{self.seed:02d}{self.node_seq:034d}"[:42]
        if node_type == "RISK_CLUSTER":
            return f"cluster-{self.run_tag}-{self.node_seq:06d}"
        return f"0x{self.seed:02d}{self.node_seq:038d}"[-42:]

    def add_node(
        self,
        *,
        chain: str,
        address: str,
        node_type: str,
        display_name: str | None = None,
        risk_level: str = "NONE",
        risk_source: str | None = None,
    ) -> str:
        """Insert a graph node once and return its stable node key."""
        chain = self._normalize_chain(chain)
        address = self._normalize_address(address)
        node_key = self._node_key(chain, address)
        if node_key in self.node_keys:
            return node_key
        self.node_keys.add(node_key)
        self.nodes.append(
            {
                "id": self._uuid("node", node_key),
                "node_key": node_key,
                "chain": chain,
                "address": address,
                "node_type": node_type,
                "display_name": display_name or address,
                "risk_level": risk_level,
                "risk_source": risk_source,
                "created_at": dt.datetime.combine(TODAY, dt.time(9, 0)),
            }
        )
        return node_key

    def add_edge(
        self,
        from_node_key: str,
        to_node_key: str,
        edge_type: str,
        *,
        total_usd_value: float | int,
        tx_count: int,
        first_seen_days_ago: int,
        last_seen_days_ago: int,
        confidence: float,
    ) -> None:
        """Insert or aggregate a relationship edge."""
        key = (from_node_key, to_node_key, edge_type)
        first_seen = TODAY - dt.timedelta(days=max(first_seen_days_ago, last_seen_days_ago))
        last_seen = TODAY - dt.timedelta(days=min(first_seen_days_ago, last_seen_days_ago))
        if key not in self.edges_by_key:
            self.edges_by_key[key] = {
                "id": self._uuid("edge", "|".join(key)),
                "from_node_key": from_node_key,
                "to_node_key": to_node_key,
                "edge_type": edge_type,
                "total_usd_value": money(total_usd_value),
                "transaction_count": tx_count,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "confidence": decimal.Decimal(f"{confidence:.4f}"),
                "created_at": dt.datetime.combine(TODAY, dt.time(9, 5)),
            }
            return

        edge = self.edges_by_key[key]
        edge["total_usd_value"] += money(total_usd_value)
        edge["transaction_count"] += tx_count
        edge["first_seen"] = min(edge["first_seen"], first_seen)
        edge["last_seen"] = max(edge["last_seen"], last_seen)
        edge["confidence"] = max(edge["confidence"], decimal.Decimal(f"{confidence:.4f}"))

    def add_screening_request(
        self,
        scenario_type: str,
        *,
        chain: str,
        wallet_address: str,
        asset: str,
        amount_usd: float | int,
        expected_verdict: str,
        ground_truth_reason: str,
    ) -> None:
        """Store a synthetic runtime screening input for the demo CLI."""
        self.case_seq += 1
        case_id = f"{scenario_type}-{self.run_tag}-{self.case_seq:04d}"
        self.screenings.append(
            {
                "id": self._uuid("screening", case_id),
                "case_id": case_id,
                "scenario_type": scenario_type,
                "chain": self._normalize_chain(chain),
                "wallet_address": self._normalize_address(wallet_address),
                "asset": asset,
                "amount_usd": money(amount_usd),
                "expected_verdict": expected_verdict,
                "ground_truth_reason": ground_truth_reason,
                "created_at": dt.datetime.combine(TODAY, dt.time(10, 0)),
            }
        )

    def _new_node(
        self,
        *,
        node_type: str,
        chain: str | None = None,
        risk_level: str = "NONE",
        risk_source: str | None = None,
        label: str,
    ) -> tuple[str, str, str]:
        chain = self._normalize_chain(chain or self.rng.choice(CHAINS))
        address = self._new_address(chain, node_type=node_type)
        display_name = f"{node_type}:{label}:{self.node_seq:04d}"
        node_key = self.add_node(
            chain=chain,
            address=address,
            node_type=node_type,
            display_name=display_name,
            risk_level=risk_level,
            risk_source=risk_source,
        )
        return node_key, chain, address

    def build(self) -> None:
        """Assemble the complete synthetic Phase 2 dataset."""
        self._build_direct_sanctioned_wallet()
        self._build_one_hop_wallet_exposure()
        self._build_two_hop_wallet_exposure()
        self._build_derived_risk_anchor_chain()
        self._build_repeated_small_transfers_to_risky_wallet()
        self._build_isolated_dust_exposure()
        self._build_exchange_contamination_prevented()
        self._build_bridge_contamination_prevented()
        self._build_mixer_route()
        self._build_bridge_route()
        self._build_ransomware_cluster()
        self._build_exchange_hot_wallet_noise()
        self._build_smart_contract_noise()
        self._build_clean_wallet()
        self._build_background_service_nodes()
        self.validate()

    def validate(self) -> None:
        """Ensure the generated dataset is large enough and contains every scenario."""
        counts = {
            "crypto_graph_nodes": len(self.nodes),
            "crypto_graph_edges": len(self.edges_by_key),
            "crypto_synthetic_screenings": len(self.screenings),
        }
        minimums = {
            "crypto_graph_nodes": MIN_GRAPH_NODES,
            "crypto_graph_edges": MIN_GRAPH_EDGES,
            "crypto_synthetic_screenings": MIN_SYNTHETIC_SCREENINGS,
        }
        for name, minimum in minimums.items():
            if counts[name] < minimum:
                raise RuntimeError(f"{name} target missed: {counts[name]} < {minimum}")

        scenarios = collections.Counter(row["scenario_type"] for row in self.screenings)
        missing = [scenario for scenario in SCENARIO_COUNTS if scenarios[scenario] == 0]
        if missing:
            raise RuntimeError(f"missing required crypto scenarios: {', '.join(missing)}")

    def _build_direct_sanctioned_wallet(self) -> None:
        """Create direct sanctioned wallet cases that must resolve to `MATCH`."""
        for idx in range(SCENARIO_COUNTS["direct_sanctioned_wallet"]):
            chain = CHAINS[idx % len(CHAINS)]
            node_key, wallet_chain, wallet_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="direct",
            )
            _cluster_key, _, _ = self._new_node(
                node_type="RISK_CLUSTER",
                chain=wallet_chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="direct-cluster",
            )
            self.add_screening_request(
                "direct_sanctioned_wallet",
                chain=wallet_chain,
                wallet_address=wallet_address,
                asset=ASSETS[idx % len(ASSETS)],
                amount_usd=24000 + idx * 900,
                expected_verdict="MATCH",
                ground_truth_reason="wallet itself is sanctioned and should be blocked directly",
            )

    def _build_one_hop_wallet_exposure(self) -> None:
        """Create sanctioned wallet -> recipient wallet one-hop exposure cases."""
        for idx in range(SCENARIO_COUNTS["one_hop_wallet_exposure"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="onehop-source",
            )
            recipient_key, _, recipient_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="onehop-recipient",
            )
            self.add_edge(
                source_key,
                recipient_key,
                "TRANSFERRED_TO",
                total_usd_value=52000 + idx * 1800,
                tx_count=5 + idx % 3,
                first_seen_days_ago=25,
                last_seen_days_ago=2,
                confidence=0.95,
            )
            self.add_screening_request(
                "one_hop_wallet_exposure",
                chain=wallet_chain,
                wallet_address=recipient_address,
                asset=ASSETS[(idx + 1) % len(ASSETS)],
                amount_usd=7200 + idx * 180,
                expected_verdict="REVIEW",
                ground_truth_reason="wallet is one hop away from a sanctioned wallet via recent transfer activity",
            )

    def _build_two_hop_wallet_exposure(self) -> None:
        """Create sanctioned wallet -> bridged relay wallet -> recipient paths."""
        for idx in range(SCENARIO_COUNTS["two_hop_wallet_exposure"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="twohop-source",
            )
            relay_key, _, _relay_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="twohop-bridged-relay",
            )
            recipient_key, _, recipient_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="twohop-recipient",
            )
            self.add_edge(
                source_key,
                relay_key,
                "BRIDGED_TO",
                total_usd_value=18000 + idx * 420,
                tx_count=3 + idx % 2,
                first_seen_days_ago=60,
                last_seen_days_ago=9,
                confidence=0.88,
            )
            self.add_edge(
                relay_key,
                recipient_key,
                "TRANSFERRED_TO",
                total_usd_value=17250 + idx * 390,
                tx_count=2 + idx % 2,
                first_seen_days_ago=38,
                last_seen_days_ago=6,
                confidence=0.84,
            )
            self.add_screening_request(
                "two_hop_wallet_exposure",
                chain=wallet_chain,
                wallet_address=recipient_address,
                asset=ASSETS[(idx + 2) % len(ASSETS)],
                amount_usd=4900 + idx * 95,
                expected_verdict="REVIEW",
                ground_truth_reason="wallet is within two hops of a sanctioned wallet through a bridge path",
            )

    def _build_derived_risk_anchor_chain(self) -> None:
        """Create controlled 3-hop crypto chains used only by derived-risk precompute."""
        for idx in range(SCENARIO_COUNTS["crypto_derived_anchor_milica_to_sanctioned"]):
            chain = CHAINS[idx % len(CHAINS)]
            milica_key, wallet_chain, milica_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                label="derived-milica-wallet",
            )
            sanctioned_key, _, _sanctioned_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="derived-sanctioned-wallet",
            )
            self.add_edge(
                milica_key,
                sanctioned_key,
                "TRANSFERRED_TO",
                total_usd_value=26000 + idx * 500,
                tx_count=2,
                first_seen_days_ago=10,
                last_seen_days_ago=1,
                confidence=0.97,
            )
            self.add_screening_request(
                "crypto_derived_anchor_milica_to_sanctioned",
                chain=wallet_chain,
                wallet_address=milica_address,
                asset=ASSETS[idx % len(ASSETS)],
                amount_usd=6200 + idx * 100,
                expected_verdict="REVIEW",
                ground_truth_reason="Milica wallet has a direct outbound path to a sanctioned wallet and should become a strong derived-risk anchor candidate",
            )

            if idx < SCENARIO_COUNTS["crypto_mateja_to_derived_anchor"]:
                mateja_key, _, mateja_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-mateja-wallet",
                )
                self.add_edge(
                    mateja_key,
                    milica_key,
                    "TRANSFERRED_TO",
                    total_usd_value=21000 + idx * 400,
                    tx_count=2,
                    first_seen_days_ago=8,
                    last_seen_days_ago=1,
                    confidence=0.96,
                )
                for feeder_idx in range(8):
                    feeder_key, _, _feeder_address = self._new_node(
                        node_type="WALLET",
                        chain=wallet_chain,
                        label=f"derived-mateja-feeder-{idx:02d}-{feeder_idx:02d}",
                    )
                    self.add_edge(
                        feeder_key,
                        mateja_key,
                        "TRANSFERRED_TO",
                        total_usd_value=1400 + feeder_idx * 60,
                        tx_count=14 + feeder_idx,
                        first_seen_days_ago=16,
                        last_seen_days_ago=1 + feeder_idx % 2,
                        confidence=0.86,
                    )
                self.add_screening_request(
                    "crypto_mateja_to_derived_anchor",
                    chain=wallet_chain,
                    wallet_address=mateja_address,
                    asset=ASSETS[(idx + 1) % len(ASSETS)],
                    amount_usd=5100 + idx * 90,
                    expected_verdict="REVIEW",
                    ground_truth_reason="Mateja wallet is two hops outbound from a sanctioned wallet and should become a derived-risk anchor",
                )

            if idx < SCENARIO_COUNTS["crypto_andrija_funds_derived_proxy"]:
                andrija_key, _, andrija_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-andrija-wallet",
                )
                self.add_edge(
                    andrija_key,
                    mateja_key,
                    "TRANSFERRED_TO",
                    total_usd_value=18500 + idx * 250,
                    tx_count=2,
                    first_seen_days_ago=7,
                    last_seen_days_ago=1,
                    confidence=0.95,
                )
                for side_idx in range(2):
                    side_key, _, _side_address = self._new_node(
                        node_type="WALLET",
                        chain=wallet_chain,
                        label=f"derived-andrija-side-{idx:02d}-{side_idx:02d}",
                    )
                    self.add_edge(
                        andrija_key,
                        side_key,
                        "TRANSFERRED_TO",
                        total_usd_value=900 + side_idx * 140,
                        tx_count=1,
                        first_seen_days_ago=12,
                        last_seen_days_ago=2 + side_idx,
                        confidence=0.79,
                    )
                self.add_screening_request(
                    "crypto_andrija_funds_derived_proxy",
                    chain=wallet_chain,
                    wallet_address=andrija_address,
                    asset=ASSETS[(idx + 2) % len(ASSETS)],
                    amount_usd=4300 + idx * 80,
                    expected_verdict="REVIEW",
                    ground_truth_reason="Andrija materially funds a wallet that is already proven to route value toward a sanctioned endpoint",
                )

            if idx < SCENARIO_COUNTS["crypto_tiny_upstream_funding_suppressed"]:
                tiny_milica_key, _, _tiny_milica_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-tiny-milica-wallet",
                )
                tiny_sanctioned_key, _, _tiny_sanctioned_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    risk_level="SANCTIONED",
                    risk_source="synthetic:sanctions",
                    label="derived-tiny-sanctioned-wallet",
                )
                tiny_mateja_key, _, _tiny_mateja_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-tiny-mateja-wallet",
                )
                tiny_andrija_key, _, tiny_andrija_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-tiny-andrija-wallet",
                )
                self.add_edge(
                    tiny_milica_key,
                    tiny_sanctioned_key,
                    "TRANSFERRED_TO",
                    total_usd_value=16000 + idx * 180,
                    tx_count=1,
                    first_seen_days_ago=8,
                    last_seen_days_ago=1,
                    confidence=0.96,
                )
                self.add_edge(
                    tiny_mateja_key,
                    tiny_milica_key,
                    "TRANSFERRED_TO",
                    total_usd_value=15000 + idx * 170,
                    tx_count=1,
                    first_seen_days_ago=7,
                    last_seen_days_ago=1,
                    confidence=0.95,
                )
                self.add_edge(
                    tiny_andrija_key,
                    tiny_mateja_key,
                    "TRANSFERRED_TO",
                    total_usd_value=12 + idx % 3,
                    tx_count=1,
                    first_seen_days_ago=6,
                    last_seen_days_ago=1,
                    confidence=0.80,
                )
                self.add_screening_request(
                    "crypto_tiny_upstream_funding_suppressed",
                    chain=wallet_chain,
                    wallet_address=tiny_andrija_address,
                    asset=ASSETS[(idx + 3) % len(ASSETS)],
                    amount_usd=12 + idx % 3,
                    expected_verdict="NO_MATCH",
                    ground_truth_reason="tiny upstream funding into a derived crypto proxy chain should stay suppressed",
                )

            if idx < SCENARIO_COUNTS["crypto_exchange_upstream_funding_suppressed"]:
                exch_andrija_key, _, exch_andrija_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-exchange-andrija-wallet",
                )
                exchange_key, _, _exchange_address = self._new_node(
                    node_type="EXCHANGE_HOT_WALLET",
                    chain=wallet_chain,
                    label="derived-exchange-hot-wallet",
                )
                exch_mateja_key, _, _exch_mateja_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-exchange-mateja-wallet",
                )
                exch_milica_key, _, _exch_milica_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-exchange-milica-wallet",
                )
                exch_sanctioned_key, _, _exch_sanctioned_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    risk_level="SANCTIONED",
                    risk_source="synthetic:sanctions",
                    label="derived-exchange-sanctioned-wallet",
                )
                self.add_edge(
                    exch_andrija_key,
                    exchange_key,
                    "DEPOSITED_TO_EXCHANGE",
                    total_usd_value=22000 + idx * 320,
                    tx_count=2,
                    first_seen_days_ago=9,
                    last_seen_days_ago=1,
                    confidence=0.93,
                )
                self.add_edge(
                    exchange_key,
                    exch_mateja_key,
                    "WITHDREW_FROM_EXCHANGE",
                    total_usd_value=21000 + idx * 300,
                    tx_count=1,
                    first_seen_days_ago=8,
                    last_seen_days_ago=1,
                    confidence=0.89,
                )
                self.add_edge(
                    exch_mateja_key,
                    exch_milica_key,
                    "TRANSFERRED_TO",
                    total_usd_value=20500 + idx * 280,
                    tx_count=1,
                    first_seen_days_ago=7,
                    last_seen_days_ago=1,
                    confidence=0.95,
                )
                self.add_edge(
                    exch_milica_key,
                    exch_sanctioned_key,
                    "TRANSFERRED_TO",
                    total_usd_value=19800 + idx * 250,
                    tx_count=1,
                    first_seen_days_ago=6,
                    last_seen_days_ago=1,
                    confidence=0.96,
                )
                self.add_screening_request(
                    "crypto_exchange_upstream_funding_suppressed",
                    chain=wallet_chain,
                    wallet_address=exch_andrija_address,
                    asset=ASSETS[(idx + 4) % len(ASSETS)],
                    amount_usd=5000 + idx * 60,
                    expected_verdict="NO_MATCH",
                    ground_truth_reason="upstream path crosses an exchange hot wallet and must not create derived crypto contamination",
                )

            if idx < SCENARIO_COUNTS["crypto_bridge_or_mixer_upstream_suppressed"]:
                infra_andrija_key, _, infra_andrija_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-infra-andrija-wallet",
                )
                infra_service_type = "BRIDGE" if idx % 2 == 0 else "MIXER"
                infra_service_key, _, _infra_service_address = self._new_node(
                    node_type=infra_service_type,
                    chain=wallet_chain,
                    risk_level="MIXER" if infra_service_type == "MIXER" else "NONE",
                    risk_source="synthetic:mixer" if infra_service_type == "MIXER" else None,
                    label="derived-infra-service",
                )
                infra_mateja_key, _, _infra_mateja_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-infra-mateja-wallet",
                )
                infra_milica_key, _, _infra_milica_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-infra-milica-wallet",
                )
                infra_sanctioned_key, _, _infra_sanctioned_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    risk_level="SANCTIONED",
                    risk_source="synthetic:sanctions",
                    label="derived-infra-sanctioned-wallet",
                )
                self.add_edge(
                    infra_andrija_key,
                    infra_service_key,
                    "USED_MIXER" if infra_service_type == "MIXER" else "BRIDGED_TO",
                    total_usd_value=24000 + idx * 300,
                    tx_count=2,
                    first_seen_days_ago=9,
                    last_seen_days_ago=1,
                    confidence=0.88,
                )
                self.add_edge(
                    infra_service_key,
                    infra_mateja_key,
                    "TRANSFERRED_TO",
                    total_usd_value=23000 + idx * 280,
                    tx_count=1,
                    first_seen_days_ago=8,
                    last_seen_days_ago=1,
                    confidence=0.86,
                )
                self.add_edge(
                    infra_mateja_key,
                    infra_milica_key,
                    "TRANSFERRED_TO",
                    total_usd_value=22000 + idx * 260,
                    tx_count=1,
                    first_seen_days_ago=7,
                    last_seen_days_ago=1,
                    confidence=0.95,
                )
                self.add_edge(
                    infra_milica_key,
                    infra_sanctioned_key,
                    "TRANSFERRED_TO",
                    total_usd_value=21000 + idx * 240,
                    tx_count=1,
                    first_seen_days_ago=6,
                    last_seen_days_ago=1,
                    confidence=0.96,
                )
                self.add_screening_request(
                    "crypto_bridge_or_mixer_upstream_suppressed",
                    chain=wallet_chain,
                    wallet_address=infra_andrija_address,
                    asset=ASSETS[idx % len(ASSETS)],
                    amount_usd=5200 + idx * 55,
                    expected_verdict="NO_MATCH",
                    ground_truth_reason="upstream path crosses a bridge or mixer service boundary and should not create derived crypto review",
                )

            if idx < SCENARIO_COUNTS["crypto_normal_high_concentration_control_no_match"]:
                control_sender_key, _, control_sender_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-control-sender-wallet",
                )
                control_receiver_key, _, _control_receiver_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-control-receiver-wallet",
                )
                self.add_edge(
                    control_sender_key,
                    control_receiver_key,
                    "TRANSFERRED_TO",
                    total_usd_value=82000 + idx * 550,
                    tx_count=4,
                    first_seen_days_ago=10,
                    last_seen_days_ago=1,
                    confidence=0.96,
                )
                for side_idx in range(2):
                    side_key, _, _side_address = self._new_node(
                        node_type="WALLET",
                        chain=wallet_chain,
                        label=f"derived-control-side-{idx:02d}-{side_idx:02d}",
                    )
                    self.add_edge(
                        control_sender_key,
                        side_key,
                        "TRANSFERRED_TO",
                        total_usd_value=1600 + side_idx * 100,
                        tx_count=1,
                        first_seen_days_ago=14,
                        last_seen_days_ago=2,
                        confidence=0.81,
                    )
                self.add_screening_request(
                    "crypto_normal_high_concentration_control_no_match",
                    chain=wallet_chain,
                    wallet_address=control_sender_address,
                    asset=ASSETS[(idx + 1) % len(ASSETS)],
                    amount_usd=7000 + idx * 75,
                    expected_verdict="NO_MATCH",
                    ground_truth_reason="high concentration without any sanctions path should not create crypto sanctions-evasion review",
                )

            if idx < SCENARIO_COUNTS["crypto_old_weak_derived_anchor_suppressed"]:
                old_andrija_key, _, old_andrija_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-old-andrija-wallet",
                )
                old_mateja_key, _, _old_mateja_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-old-mateja-wallet",
                )
                old_milica_key, _, _old_milica_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label="derived-old-milica-wallet",
                )
                old_sanctioned_key, _, _old_sanctioned_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    risk_level="SANCTIONED",
                    risk_source="synthetic:sanctions",
                    label="derived-old-sanctioned-wallet",
                )
                self.add_edge(
                    old_milica_key,
                    old_sanctioned_key,
                    "TRANSFERRED_TO",
                    total_usd_value=75,
                    tx_count=1,
                    first_seen_days_ago=260,
                    last_seen_days_ago=240,
                    confidence=0.82,
                )
                self.add_edge(
                    old_mateja_key,
                    old_milica_key,
                    "TRANSFERRED_TO",
                    total_usd_value=90,
                    tx_count=1,
                    first_seen_days_ago=255,
                    last_seen_days_ago=235,
                    confidence=0.81,
                )
                self.add_edge(
                    old_andrija_key,
                    old_mateja_key,
                    "TRANSFERRED_TO",
                    total_usd_value=5200 + idx * 60,
                    tx_count=2,
                    first_seen_days_ago=7,
                    last_seen_days_ago=1,
                    confidence=0.92,
                )
                self.add_screening_request(
                    "crypto_old_weak_derived_anchor_suppressed",
                    chain=wallet_chain,
                    wallet_address=old_andrija_address,
                    asset=ASSETS[(idx + 2) % len(ASSETS)],
                    amount_usd=2900 + idx * 40,
                    expected_verdict="NO_MATCH",
                    ground_truth_reason="upstream funding into a wallet with only old weak crypto exposure should remain suppressed",
                )

    def _build_clean_wallet(self) -> None:
        """Create clean wallet cases with no risky path in the graph."""
        for idx in range(SCENARIO_COUNTS["clean_wallet"]):
            chain = CHAINS[idx % len(CHAINS)]
            wallet_key, wallet_chain, wallet_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                label="clean-wallet",
            )
            contract_key, _, _contract_address = self._new_node(
                node_type="SMART_CONTRACT",
                chain=wallet_chain,
                label="clean-contract",
            )
            exchange_key, _, _exchange_address = self._new_node(
                node_type="EXCHANGE_HOT_WALLET",
                chain=wallet_chain,
                label="clean-exchange",
            )
            self.add_edge(
                wallet_key,
                contract_key,
                "TRANSFERRED_TO",
                total_usd_value=2200 + idx * 55,
                tx_count=1 + idx % 2,
                first_seen_days_ago=30,
                last_seen_days_ago=4,
                confidence=0.91,
            )
            self.add_edge(
                wallet_key,
                exchange_key,
                "DEPOSITED_TO_EXCHANGE",
                total_usd_value=4800 + idx * 120,
                tx_count=2 + idx % 3,
                first_seen_days_ago=40,
                last_seen_days_ago=3,
                confidence=0.93,
            )
            self.add_screening_request(
                "clean_wallet",
                chain=wallet_chain,
                wallet_address=wallet_address,
                asset=ASSETS[(idx + 3) % len(ASSETS)],
                amount_usd=1200 + idx * 40,
                expected_verdict="NO_MATCH",
                ground_truth_reason="wallet belongs to a clean synthetic cluster and has no risky upstream path",
            )

    def _build_repeated_small_transfers_to_risky_wallet(self) -> None:
        """Create aggregated structuring-like flow that must remain reviewable."""
        for idx in range(SCENARIO_COUNTS["repeated_small_transfers_to_risky_wallet"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="structuring-source",
            )
            recipient_key, _, recipient_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="structuring-recipient",
            )
            self.add_edge(
                source_key,
                recipient_key,
                "TRANSFERRED_TO",
                total_usd_value=50000,
                tx_count=10000,
                first_seen_days_ago=90,
                last_seen_days_ago=1,
                confidence=0.93,
            )
            self.add_screening_request(
                "repeated_small_transfers_to_risky_wallet",
                chain=wallet_chain,
                wallet_address=recipient_address,
                asset=ASSETS[(idx + 4) % len(ASSETS)],
                amount_usd=850.0 + idx * 15,
                expected_verdict="REVIEW",
                ground_truth_reason="many repeated 5 USD transfers aggregate into material exposure and must not be treated as dust",
            )

    def _build_isolated_dust_exposure(self) -> None:
        """Create isolated tiny indirect flows that should be pruned offline."""
        for idx in range(SCENARIO_COUNTS["isolated_dust_exposure"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="dust-source",
            )
            recipient_key, _, recipient_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="dust-recipient",
            )
            self.add_edge(
                source_key,
                recipient_key,
                "TRANSFERRED_TO",
                total_usd_value=3,
                tx_count=1,
                first_seen_days_ago=4,
                last_seen_days_ago=4,
                confidence=0.91,
            )
            self.add_screening_request(
                "isolated_dust_exposure",
                chain=wallet_chain,
                wallet_address=recipient_address,
                asset=ASSETS[idx % len(ASSETS)],
                amount_usd=3,
                expected_verdict="NO_MATCH",
                ground_truth_reason="single isolated 3 USD exposure should be ignored as dust",
            )

    def _build_exchange_contamination_prevented(self) -> None:
        """Create a shared-exchange path that must not contaminate a clean wallet."""
        for idx in range(SCENARIO_COUNTS["exchange_contamination_prevented"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="exchange-risky-source",
            )
            exchange_key, _, _exchange_address = self._new_node(
                node_type="EXCHANGE_HOT_WALLET",
                chain=wallet_chain,
                label="exchange-shared",
            )
            clean_wallet_key, _, clean_wallet_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="exchange-clean-recipient",
            )
            self.add_edge(
                source_key,
                exchange_key,
                "DEPOSITED_TO_EXCHANGE",
                total_usd_value=28000 + idx * 800,
                tx_count=2 + idx % 2,
                first_seen_days_ago=35,
                last_seen_days_ago=2,
                confidence=0.92,
            )
            self.add_edge(
                exchange_key,
                clean_wallet_key,
                "WITHDREW_FROM_EXCHANGE",
                total_usd_value=2600 + idx * 60,
                tx_count=1 + idx % 2,
                first_seen_days_ago=30,
                last_seen_days_ago=1,
                confidence=0.89,
            )
            self.add_screening_request(
                "exchange_contamination_prevented",
                chain=wallet_chain,
                wallet_address=clean_wallet_address,
                asset=ASSETS[(idx + 1) % len(ASSETS)],
                amount_usd=1400 + idx * 35,
                expected_verdict="NO_MATCH",
                ground_truth_reason="shared exchange activity must not propagate a sanctioned depositor's risk to an unrelated withdrawal recipient",
            )

    def _build_bridge_contamination_prevented(self) -> None:
        """Create a shared bridge-service path that must not contaminate a clean wallet."""
        for idx in range(SCENARIO_COUNTS["bridge_contamination_prevented"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="bridge-risky-source",
            )
            bridge_service_key, _, _bridge_service_address = self._new_node(
                node_type="BRIDGE",
                chain=wallet_chain,
                label="bridge-shared-service",
            )
            clean_wallet_key, _, clean_wallet_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="bridge-clean-recipient",
            )
            self.add_edge(
                source_key,
                bridge_service_key,
                "BRIDGED_TO",
                total_usd_value=24000 + idx * 650,
                tx_count=2 + idx % 2,
                first_seen_days_ago=42,
                last_seen_days_ago=3,
                confidence=0.90,
            )
            self.add_edge(
                bridge_service_key,
                clean_wallet_key,
                "TRANSFERRED_TO",
                total_usd_value=3100 + idx * 75,
                tx_count=1 + idx % 2,
                first_seen_days_ago=35,
                last_seen_days_ago=1,
                confidence=0.87,
            )
            self.add_screening_request(
                "bridge_contamination_prevented",
                chain=wallet_chain,
                wallet_address=clean_wallet_address,
                asset=ASSETS[(idx + 2) % len(ASSETS)],
                amount_usd=1550 + idx * 45,
                expected_verdict="NO_MATCH",
                ground_truth_reason="shared bridge service activity must not propagate a sanctioned sender's risk to an unrelated recipient",
            )

    def _build_mixer_route(self) -> None:
        """Create material mixer-routed flow that is reviewable without contaminating all mixer users."""
        for idx in range(SCENARIO_COUNTS["mixer_route"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SCAM",
                risk_source="synthetic:scam-ops",
                label="mixer-route-source",
            )
            recipient_key, _, recipient_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="mixer-route-recipient",
            )
            mixer_service_key, _, _mixer_service_address = self._new_node(
                node_type="MIXER",
                chain=wallet_chain,
                risk_level="MIXER",
                risk_source="synthetic:mixer-service",
                label="mixer-route-service",
            )
            unrelated_wallet_key, _, _unrelated_wallet_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="mixer-route-unrelated-wallet",
            )
            self.add_edge(
                source_key,
                recipient_key,
                "USED_MIXER",
                total_usd_value=18500 + idx * 520,
                tx_count=4 + idx % 2,
                first_seen_days_ago=24,
                last_seen_days_ago=2,
                confidence=0.87,
            )
            self.add_edge(
                source_key,
                mixer_service_key,
                "USED_MIXER",
                total_usd_value=16000 + idx * 400,
                tx_count=3 + idx % 2,
                first_seen_days_ago=26,
                last_seen_days_ago=3,
                confidence=0.84,
            )
            self.add_edge(
                unrelated_wallet_key,
                mixer_service_key,
                "USED_MIXER",
                total_usd_value=2400 + idx * 55,
                tx_count=1,
                first_seen_days_ago=18,
                last_seen_days_ago=4,
                confidence=0.82,
            )
            self.add_screening_request(
                "mixer_route",
                chain=wallet_chain,
                wallet_address=recipient_address,
                asset=ASSETS[idx % len(ASSETS)],
                amount_usd=2600 + idx * 65,
                expected_verdict="REVIEW",
                ground_truth_reason="wallet received material flow through a specific mixer-routed relationship and should be reviewed",
            )

    def _build_bridge_route(self) -> None:
        """Create direct wallet-to-wallet bridge routes that remain valid propagation paths."""
        for idx in range(SCENARIO_COUNTS["bridge_route"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="bridge-route-source",
            )
            recipient_key, _, recipient_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="bridge-route-recipient",
            )
            self.add_edge(
                source_key,
                recipient_key,
                "BRIDGED_TO",
                total_usd_value=21000 + idx * 610,
                tx_count=2 + idx % 2,
                first_seen_days_ago=28,
                last_seen_days_ago=2,
                confidence=0.90,
            )
            self.add_screening_request(
                "bridge_route",
                chain=wallet_chain,
                wallet_address=recipient_address,
                asset=ASSETS[(idx + 1) % len(ASSETS)],
                amount_usd=3400 + idx * 80,
                expected_verdict="REVIEW",
                ground_truth_reason="wallet is directly downstream of a risky wallet through a specific bridge route",
            )

    def _build_ransomware_cluster(self) -> None:
        """Create material ransomware cluster flow that should produce review, not match."""
        for idx in range(SCENARIO_COUNTS["ransomware_cluster"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _cluster_address = self._new_node(
                node_type="RISK_CLUSTER",
                chain=chain,
                risk_level="RANSOMWARE",
                risk_source="synthetic:ransomware-cluster",
                label="ransomware-cluster",
            )
            recipient_key, _, recipient_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="ransomware-recipient",
            )
            self.add_edge(
                source_key,
                recipient_key,
                "TRANSFERRED_TO",
                total_usd_value=64000 + idx * 2000,
                tx_count=3 + idx % 2,
                first_seen_days_ago=19,
                last_seen_days_ago=1,
                confidence=0.92,
            )
            self.add_screening_request(
                "ransomware_cluster",
                chain=wallet_chain,
                wallet_address=recipient_address,
                asset=ASSETS[(idx + 2) % len(ASSETS)],
                amount_usd=7300 + idx * 140,
                expected_verdict="REVIEW",
                ground_truth_reason="wallet received material value from a ransomware risk cluster and should be reviewed",
            )

    def _build_exchange_hot_wallet_noise(self) -> None:
        """Create exchange hot wallet noise that must not contaminate unrelated customers."""
        for idx in range(SCENARIO_COUNTS["exchange_hot_wallet_noise"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="exchange-noise-source",
            )
            exchange_key, _, _exchange_address = self._new_node(
                node_type="EXCHANGE_HOT_WALLET",
                chain=wallet_chain,
                label="exchange-noise-hot-wallet",
            )
            clean_wallet_key, _, clean_wallet_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="exchange-noise-clean-wallet",
            )
            self.add_edge(
                source_key,
                exchange_key,
                "DEPOSITED_TO_EXCHANGE",
                total_usd_value=45000 + idx * 1400,
                tx_count=3 + idx % 2,
                first_seen_days_ago=31,
                last_seen_days_ago=2,
                confidence=0.93,
            )
            self.add_edge(
                clean_wallet_key,
                exchange_key,
                "DEPOSITED_TO_EXCHANGE",
                total_usd_value=1800 + idx * 45,
                tx_count=1 + idx % 2,
                first_seen_days_ago=22,
                last_seen_days_ago=1,
                confidence=0.89,
            )
            self.add_screening_request(
                "exchange_hot_wallet_noise",
                chain=wallet_chain,
                wallet_address=clean_wallet_address,
                asset=ASSETS[(idx + 3) % len(ASSETS)],
                amount_usd=900 + idx * 20,
                expected_verdict="NO_MATCH",
                ground_truth_reason="wallet only shares an exchange hot wallet touchpoint with a sanctioned depositor and should remain clean",
            )

    def _build_smart_contract_noise(self) -> None:
        """Create high-degree smart-contract activity that must not fan out contamination."""
        for idx in range(SCENARIO_COUNTS["smart_contract_noise"]):
            chain = CHAINS[idx % len(CHAINS)]
            source_key, wallet_chain, _source_address = self._new_node(
                node_type="WALLET",
                chain=chain,
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                label="contract-noise-source",
            )
            contract_key, _, _contract_address = self._new_node(
                node_type="SMART_CONTRACT",
                chain=wallet_chain,
                label="contract-noise-hub",
            )
            clean_wallet_key, _, clean_wallet_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="contract-noise-screened-wallet",
            )
            self.add_edge(
                source_key,
                contract_key,
                "TRANSFERRED_TO",
                total_usd_value=33000 + idx * 900,
                tx_count=2 + idx % 2,
                first_seen_days_ago=33,
                last_seen_days_ago=3,
                confidence=0.91,
            )
            self.add_edge(
                clean_wallet_key,
                contract_key,
                "TRANSFERRED_TO",
                total_usd_value=2400 + idx * 60,
                tx_count=1 + idx % 2,
                first_seen_days_ago=20,
                last_seen_days_ago=2,
                confidence=0.88,
            )
            for fanout_idx in range(30):
                user_key, _, _user_address = self._new_node(
                    node_type="WALLET",
                    chain=wallet_chain,
                    label=f"contract-noise-user-{idx:02d}-{fanout_idx:02d}",
                )
                self.add_edge(
                    user_key,
                    contract_key,
                    "TRANSFERRED_TO",
                    total_usd_value=1200 + fanout_idx * 30,
                    tx_count=1 + fanout_idx % 2,
                    first_seen_days_ago=17,
                    last_seen_days_ago=1,
                    confidence=0.86,
                )
            self.add_screening_request(
                "smart_contract_noise",
                chain=wallet_chain,
                wallet_address=clean_wallet_address,
                asset=ASSETS[(idx + 4) % len(ASSETS)],
                amount_usd=1100 + idx * 25,
                expected_verdict="NO_MATCH",
                ground_truth_reason="wallet only shares a high-degree smart contract with a risky wallet and should not be contaminated",
            )

    def _build_background_service_nodes(self) -> None:
        """Add extra service structure so every Phase 1 node/edge family exists."""
        for idx in range(40):
            chain = CHAINS[idx % len(CHAINS)]
            cluster_key, wallet_chain, _cluster_address = self._new_node(
                node_type="RISK_CLUSTER",
                chain=chain,
                risk_level="SCAM" if idx % 2 == 0 else "SUSPICIOUS",
                risk_source="synthetic:background-cluster",
                label="bg-cluster",
            )
            mixer_key, _, _mixer_address = self._new_node(
                node_type="MIXER",
                chain=wallet_chain,
                risk_level="MIXER",
                risk_source="synthetic:mixer",
                label="bg-mixer",
            )
            exchange_key, _, _exchange_address = self._new_node(
                node_type="EXCHANGE_HOT_WALLET",
                chain=wallet_chain,
                label="bg-exchange",
            )
            wallet_key, _, _wallet_address = self._new_node(
                node_type="WALLET",
                chain=wallet_chain,
                label="bg-wallet",
            )
            self.add_edge(
                cluster_key,
                mixer_key,
                "USED_MIXER",
                total_usd_value=9000 + idx * 250,
                tx_count=2 + idx % 2,
                first_seen_days_ago=70,
                last_seen_days_ago=11,
                confidence=0.76,
            )
            self.add_edge(
                mixer_key,
                wallet_key,
                "TRANSFERRED_TO",
                total_usd_value=6800 + idx * 175,
                tx_count=1 + idx % 2,
                first_seen_days_ago=55,
                last_seen_days_ago=8,
                confidence=0.74,
            )
            self.add_edge(
                wallet_key,
                exchange_key,
                "DEPOSITED_TO_EXCHANGE",
                total_usd_value=5100 + idx * 130,
                tx_count=2,
                first_seen_days_ago=35,
                last_seen_days_ago=5,
                confidence=0.85,
            )
            self.add_edge(
                exchange_key,
                wallet_key,
                "WITHDREW_FROM_EXCHANGE",
                total_usd_value=4300 + idx * 110,
                tx_count=1,
                first_seen_days_ago=33,
                last_seen_days_ago=4,
                confidence=0.83,
            )

    def summary(self) -> str:
        """Return a human-readable dataset summary."""
        verdicts = collections.Counter(row["expected_verdict"] for row in self.screenings)
        scenarios = collections.Counter(row["scenario_type"] for row in self.screenings)
        risk_anchors = sum(node["risk_level"] != "NONE" for node in self.nodes)
        lines = [
            f"nodes inserted: {len(self.nodes)}",
            f"edges inserted: {len(self.edges_by_key)}",
            f"screening inputs inserted: {len(self.screenings)}",
            f"risk anchor count: {risk_anchors}",
            "",
            "screening inputs by expected_verdict:",
        ]
        for verdict in ("MATCH", "REVIEW", "NO_MATCH"):
            lines.append(f"{verdict}: {verdicts.get(verdict, 0)}")
        lines.append("")
        lines.append("screening inputs by scenario_type:")
        for scenario in SCENARIO_COUNTS:
            lines.append(f"{scenario}: {scenarios.get(scenario, 0)}")
        return "\n".join(lines)


def reset_database(engine) -> None:
    metadata.drop_all(engine)
    metadata.create_all(engine)


def insert_dataset(builder: SyntheticCryptoGraphBuilder) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(crypto_graph_nodes.insert(), builder.nodes)
        conn.execute(crypto_graph_edges.insert(), list(builder.edges_by_key.values()))
        conn.execute(crypto_synthetic_screenings.insert(), builder.screenings)


def existing_rows(engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            "crypto_graph_nodes": conn.scalar(sa.select(sa.func.count()).select_from(crypto_graph_nodes)) or 0,
            "crypto_graph_edges": conn.scalar(sa.select(sa.func.count()).select_from(crypto_graph_edges)) or 0,
            "crypto_synthetic_screenings": conn.scalar(sa.select(sa.func.count()).select_from(crypto_synthetic_screenings)) or 0,
            "crypto_exposure_index": conn.scalar(sa.select(sa.func.count()).select_from(crypto_exposure_index)) or 0,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="deterministic RNG seed")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop and recreate the crypto graph tables before inserting synthetic data",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = get_engine()
    metadata.create_all(engine)
    if args.reset:
        reset_database(engine)

    counts = existing_rows(engine)
    if any(counts.values()) and not args.reset:
        raise SystemExit(
            "database already contains crypto graph data; re-run with --reset to rebuild deterministically"
        )

    builder = SyntheticCryptoGraphBuilder(seed=args.seed)
    builder.build()
    insert_dataset(builder)
    print(builder.summary())


if __name__ == "__main__":
    main()
