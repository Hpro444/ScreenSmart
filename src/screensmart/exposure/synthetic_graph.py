"""Generate a synthetic counterparty exposure graph and load it into Postgres.

Run:
    python -m screensmart.exposure.synthetic_graph --seed 42 --reset
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
    exposure_index,
    graph_edges,
    graph_nodes,
    metadata,
    synthetic_payments,
)

TODAY = dt.date(2026, 6, 13)
COUNTRIES = ["de", "gb", "fr", "nl", "ae", "tr", "rs", "ch", "sg", "it", "es", "cy"]
PAYMENT_COUNTRIES = ["de", "gb", "fr", "nl", "ae", "tr", "rs", "ch", "sg"]
CURRENCIES = ["EUR", "USD", "GBP", "AED", "CHF", "SGD"]

SANCTIONED_FIRST = [
    "Omar", "Farid", "Nadia", "Tariq", "Leila", "Jamal", "Samir", "Rashid",
    "Karim", "Daria", "Milan", "Viktor", "Amina", "Saeed", "Zaina", "Ilham",
]
SANCTIONED_LAST = [
    "Karimov", "Haddad", "Petrovic", "Suleiman", "Qadri", "Nasser", "Belov",
    "Rahman", "Azizi", "Dimitrov", "Khalaf", "Mansouri", "Tarek", "Baranov",
]
CLEAN_FIRST = [
    "Luka", "Mia", "Sofia", "Emma", "Jonas", "Marta", "Elias", "Nina",
    "Daniel", "Noa", "Mila", "Hugo", "Sara", "Milan", "Eva", "Marko",
]
CLEAN_LAST = [
    "Novak", "Kovac", "Meyer", "Schmidt", "Rossi", "Dubois", "Popescu",
    "Horvat", "Nielsen", "Costa", "Petrescu", "Nowak", "Ilic", "Marin", "Varga",
]
COMPANY_PREFIX = [
    "Apex", "Blue", "Cedar", "Delta", "Everest", "Granite", "Harbor", "Ion",
    "Juniper", "Keystone", "Lumen", "Meridian",
]
COMPANY_SUFFIX = [
    "Trading", "Holdings", "Logistics", "Consulting", "Export", "Partners",
    "Advisory", "Capital", "Systems", "Works", "Ventures", "Industries",
]
COMMON_FALSE_POSITIVE_NAMES = [
    "Mohammed Hassan",
    "Mohamed Ali",
    "Ahmed Hussein",
    "Ali Reza",
    "John Smith",
    "Maria Garcia",
]

SCENARIO_COUNTS = {
    "direct_sanctioned_iban": 150,
    "one_hop_exposure": 200,
    "two_hop_exposure": 200,
    "high_volume_proxy": 200,
    "shell_company": 150,
    "old_tiny_exposure": 150,
    "clean_common_name": 300,
    "background_clean": 400,
}

BACKGROUND_ENTITY_COUNT = 2_400
BACKGROUND_CLEAN_FLOW_EDGES = 25_000
BACKGROUND_SUSPICIOUS_COUNT = 250
BACKGROUND_BANK_COUNT = 12
HUB_DEGREE_THRESHOLD = 200
MIN_GRAPH_NODES = 10_000
MIN_GRAPH_EDGES = 30_000
MIN_SYNTHETIC_PAYMENTS = 1_000


def money(value: float | int) -> decimal.Decimal:
    return decimal.Decimal(str(round(float(value), 2)))


class SyntheticGraphBuilder:
    """Controlled synthetic graph generator with scenario-aware labels."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.run_tag = f"s{seed}"
        self.person_seq = 0
        self.company_seq = 0
        self.iban_seq = 0
        self.case_seq = 0
        self.nodes: list[dict] = []
        self.node_keys: set[str] = set()
        self.edges_by_key: dict[tuple[str, str, str], dict] = {}
        self.payments: list[dict] = []
        self.protected_payment_ibans: set[str] = set()
        self.clean_labeled_ibans: set[str] = set()
        self.background_flow_ibans: list[str] = []

    def _uuid(self, kind: str, key: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"screensmart:{self.seed}:{kind}:{key}")

    def add_node(
        self,
        node_key: str,
        node_type: str,
        *,
        display_name: str | None = None,
        country: str | None = None,
        risk_level: str = "NONE",
        risk_source: str | None = None,
    ) -> str:
        if node_key in self.node_keys:
            return node_key
        self.node_keys.add(node_key)
        self.nodes.append(
            {
                "id": self._uuid("node", node_key),
                "node_key": node_key,
                "node_type": node_type,
                "display_name": display_name,
                "country": country,
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
        amount: float | int,
        tx_count: int,
        first_seen_days_ago: int,
        last_seen_days_ago: int,
        confidence: float,
    ) -> None:
        key = (from_node_key, to_node_key, edge_type)
        first_seen = TODAY - dt.timedelta(days=max(first_seen_days_ago, last_seen_days_ago))
        last_seen = TODAY - dt.timedelta(days=min(first_seen_days_ago, last_seen_days_ago))
        if key not in self.edges_by_key:
            self.edges_by_key[key] = {
                "id": self._uuid("edge", "|".join(key)),
                "from_node_key": from_node_key,
                "to_node_key": to_node_key,
                "edge_type": edge_type,
                "total_amount": money(amount),
                "transaction_count": tx_count,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "confidence": decimal.Decimal(f"{confidence:.4f}"),
                "created_at": dt.datetime.combine(TODAY, dt.time(9, 5)),
            }
            return

        edge = self.edges_by_key[key]
        edge["total_amount"] += money(amount)
        edge["transaction_count"] += tx_count
        edge["first_seen"] = min(edge["first_seen"], first_seen)
        edge["last_seen"] = max(edge["last_seen"], last_seen)
        edge["confidence"] = max(edge["confidence"], decimal.Decimal(f"{confidence:.4f}"))

    def add_payment(
        self,
        scenario_type: str,
        *,
        recipient_name: str,
        recipient_iban: str,
        recipient_country: str,
        amount: float | int,
        currency: str,
        expected_verdict: str,
        ground_truth_reason: str,
    ) -> None:
        self.case_seq += 1
        case_id = f"{scenario_type}-{self.run_tag}-{self.case_seq:04d}"
        self.payments.append(
            {
                "id": self._uuid("payment", case_id),
                "case_id": case_id,
                "scenario_type": scenario_type,
                "recipient_name": recipient_name,
                "recipient_iban": recipient_iban,
                "recipient_country": recipient_country,
                "amount": money(amount),
                "currency": currency,
                "expected_verdict": expected_verdict,
                "ground_truth_reason": ground_truth_reason,
                "created_at": dt.datetime.combine(TODAY, dt.time(10, 0)),
            }
        )
        if recipient_iban:
            self.protected_payment_ibans.add(recipient_iban)
            if scenario_type in {"clean_common_name", "background_clean"}:
                self.clean_labeled_ibans.add(recipient_iban)

    def _country(self) -> str:
        return self.rng.choice(COUNTRIES)

    def _payment_country(self, preferred: str | None = None) -> str:
        return preferred or self.rng.choice(PAYMENT_COUNTRIES)

    def _currency(self) -> str:
        return self.rng.choice(CURRENCIES)

    def _person_name(self, sanctioned: bool) -> str:
        self.person_seq += 1
        if sanctioned:
            first = SANCTIONED_FIRST[self.person_seq % len(SANCTIONED_FIRST)]
            last = SANCTIONED_LAST[(self.person_seq * 5) % len(SANCTIONED_LAST)]
        else:
            first = CLEAN_FIRST[self.person_seq % len(CLEAN_FIRST)]
            last = CLEAN_LAST[(self.person_seq * 7) % len(CLEAN_LAST)]
        return f"{first} {last}"

    def _company_name(self, suspicious: bool) -> str:
        self.company_seq += 1
        prefix = COMPANY_PREFIX[self.company_seq % len(COMPANY_PREFIX)]
        suffix = COMPANY_SUFFIX[(self.company_seq * 3) % len(COMPANY_SUFFIX)]
        tail = "FZE" if suspicious else "Ltd"
        return f"{prefix} {suffix} {tail}"

    def _new_person(
        self,
        *,
        risk_level: str = "NONE",
        risk_source: str | None = None,
        country: str | None = None,
        sanctioned: bool = False,
        label: str = "person",
    ) -> tuple[str, str, str]:
        country = country or self._country()
        name = self._person_name(sanctioned)
        node_key = f"PERSON:{self.run_tag}:{label}:{self.person_seq:04d}"
        self.add_node(
            node_key,
            "PERSON",
            display_name=name,
            country=country,
            risk_level=risk_level,
            risk_source=risk_source,
        )
        return node_key, name, country

    def _new_company(
        self,
        *,
        risk_level: str = "NONE",
        risk_source: str | None = None,
        country: str | None = None,
        suspicious: bool = False,
        label: str = "company",
    ) -> tuple[str, str, str]:
        country = country or self._country()
        name = self._company_name(suspicious)
        node_key = f"COMPANY:{self.run_tag}:{label}:{self.company_seq:04d}"
        self.add_node(
            node_key,
            "COMPANY",
            display_name=name,
            country=country,
            risk_level=risk_level,
            risk_source=risk_source,
        )
        return node_key, name, country

    def _new_iban(
        self,
        *,
        risk_level: str = "NONE",
        risk_source: str | None = None,
        country: str | None = None,
        label: str = "iban",
    ) -> tuple[str, str]:
        self.iban_seq += 1
        country = country or self._country()
        cc = country.upper()
        checksum = 10 + (self.iban_seq % 89)
        suffix = f"{self.seed:02d}{self.iban_seq:018d}"
        iban = f"{cc}{checksum}SS{suffix}"
        self.add_node(
            iban,
            "IBAN",
            display_name=iban,
            country=country,
            risk_level=risk_level,
            risk_source=risk_source,
        )
        return iban, country

    def build(self) -> None:
        self._build_direct_sanctioned_iban()
        self._build_one_hop_exposure()
        self._build_two_hop_exposure()
        self._build_old_tiny_exposure()
        self._build_clean_common_name()
        self._build_shell_company()
        self._build_high_volume_proxy()
        self._build_background_clean_payments()
        self._build_background_clean_entities()
        self._build_background_banks()
        self._build_background_clean_flows()
        self._build_background_suspicious_cluster()
        self.validate()

    def validate(self) -> None:
        counts = {
            "graph_nodes": len(self.nodes),
            "graph_edges": len(self.edges_by_key),
            "synthetic_payments": len(self.payments),
        }
        minimums = {
            "graph_nodes": MIN_GRAPH_NODES,
            "graph_edges": MIN_GRAPH_EDGES,
            "synthetic_payments": MIN_SYNTHETIC_PAYMENTS,
        }
        for name, minimum in minimums.items():
            if counts[name] < minimum:
                raise RuntimeError(f"{name} target missed: {counts[name]} < {minimum}")

        scenarios = collections.Counter(p["scenario_type"] for p in self.payments)
        missing = [scenario for scenario in SCENARIO_COUNTS if scenarios[scenario] == 0]
        if missing:
            raise RuntimeError(f"missing required payment scenarios: {', '.join(missing)}")

        risk_by_node = {node["node_key"]: node["risk_level"] for node in self.nodes}
        for edge in self.edges_by_key.values():
            endpoints = {edge["from_node_key"], edge["to_node_key"]}
            protected_clean = endpoints & self.clean_labeled_ibans
            if not protected_clean:
                continue
            other_nodes = endpoints - protected_clean
            if edge["edge_type"] != "USES_ACCOUNT" or any(
                risk_by_node.get(node_key, "NONE") != "NONE"
                for node_key in other_nodes
            ):
                raise RuntimeError(
                    "clean labeled account contamination detected on edge "
                    f"{edge['from_node_key']} -> {edge['to_node_key']}"
                )

    def _build_direct_sanctioned_iban(self) -> None:
        for idx in range(SCENARIO_COUNTS["direct_sanctioned_iban"]):
            person_key, person_name, country = self._new_person(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                sanctioned=True,
                label="direct",
            )
            iban, iban_country = self._new_iban(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                country=country,
                label="direct",
            )
            self.add_edge(
                person_key,
                iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=60,
                last_seen_days_ago=2,
                confidence=1.0,
            )
            self.add_payment(
                "direct_sanctioned_iban",
                recipient_name=person_name,
                recipient_iban=iban,
                recipient_country=iban_country,
                amount=8500 + idx * 175,
                currency="EUR",
                expected_verdict="MATCH",
                ground_truth_reason="recipient IBAN is directly controlled by a sanctioned person",
            )

    def _build_one_hop_exposure(self) -> None:
        for idx in range(SCENARIO_COUNTS["one_hop_exposure"]):
            sanction_key, sanction_name, country = self._new_person(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                sanctioned=True,
                label="onehop",
            )
            source_iban, _ = self._new_iban(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                country=country,
                label="onehop-source",
            )
            recipient_iban, recipient_country = self._new_iban(
                country=self._payment_country(),
                label="onehop-recipient",
            )
            self.add_edge(
                sanction_key,
                source_iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=140,
                last_seen_days_ago=8,
                confidence=1.0,
            )
            self.add_edge(
                source_iban,
                recipient_iban,
                "SENT_TO",
                amount=23000 + idx * 450,
                tx_count=8 + idx % 4,
                first_seen_days_ago=35,
                last_seen_days_ago=3,
                confidence=0.94,
            )
            self.add_payment(
                "one_hop_exposure",
                recipient_name=f"{sanction_name} Trading Counterparty",
                recipient_iban=recipient_iban,
                recipient_country=recipient_country,
                amount=6200 + idx * 110,
                currency="EUR",
                expected_verdict="REVIEW",
                ground_truth_reason="recipient IBAN is one hop away from a sanctioned account via recent transfers",
            )

    def _build_two_hop_exposure(self) -> None:
        for idx in range(SCENARIO_COUNTS["two_hop_exposure"]):
            sanction_key, sanction_name, country = self._new_person(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                sanctioned=True,
                label="twohop",
            )
            source_iban, _ = self._new_iban(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                country=country,
                label="twohop-source",
            )
            hop_iban, hop_country = self._new_iban(
                risk_level="SUSPICIOUS" if idx % 3 == 0 else "NONE",
                risk_source="synthetic:two-hop-relay" if idx % 3 == 0 else None,
                label="twohop-middle",
            )
            recipient_iban, recipient_country = self._new_iban(
                country=hop_country,
                label="twohop-recipient",
            )
            self.add_edge(
                sanction_key,
                source_iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=220,
                last_seen_days_ago=15,
                confidence=1.0,
            )
            self.add_edge(
                source_iban,
                hop_iban,
                "SENT_TO",
                amount=17500 + idx * 300,
                tx_count=5 + idx % 3,
                first_seen_days_ago=60,
                last_seen_days_ago=9,
                confidence=0.88,
            )
            self.add_edge(
                hop_iban,
                recipient_iban,
                "SENT_TO",
                amount=16800 + idx * 275,
                tx_count=4 + idx % 2,
                first_seen_days_ago=40,
                last_seen_days_ago=6,
                confidence=0.84,
            )
            self.add_payment(
                "two_hop_exposure",
                recipient_name=f"{sanction_name} Logistics Payee",
                recipient_iban=recipient_iban,
                recipient_country=recipient_country,
                amount=4800 + idx * 95,
                currency="EUR",
                expected_verdict="REVIEW",
                ground_truth_reason="recipient IBAN is two hops away from a sanctioned source through a recent relay account",
            )

    def _build_old_tiny_exposure(self) -> None:
        for idx in range(SCENARIO_COUNTS["old_tiny_exposure"]):
            sanction_key, sanction_name, country = self._new_person(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                sanctioned=True,
                label="oldt",
            )
            source_iban, _ = self._new_iban(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                country=country,
                label="oldt-source",
            )
            recipient_iban, recipient_country = self._new_iban(
                country=self._payment_country(),
                label="oldt-recipient",
            )
            self.add_edge(
                sanction_key,
                source_iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=600,
                last_seen_days_ago=480,
                confidence=1.0,
            )
            self.add_edge(
                source_iban,
                recipient_iban,
                "SENT_TO",
                amount=5 + idx % 2,
                tx_count=1,
                first_seen_days_ago=520,
                last_seen_days_ago=500,
                confidence=0.42,
            )
            self.add_payment(
                "old_tiny_exposure",
                recipient_name=f"{sanction_name} Legacy Counterparty",
                recipient_iban=recipient_iban,
                recipient_country=recipient_country,
                amount=2100 + idx * 35,
                currency="EUR",
                expected_verdict="NO_MATCH",
                ground_truth_reason="only link is an old tiny transfer from a sanctioned source; exposure is stale and weak",
            )

    def _build_clean_common_name(self) -> None:
        for idx in range(SCENARIO_COUNTS["clean_common_name"]):
            owner_key, _, country = self._new_person(label="common-clean")
            recipient_iban, recipient_country = self._new_iban(
                country=country,
                label="common-clean",
            )
            self.add_edge(
                owner_key,
                recipient_iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=300,
                last_seen_days_ago=3,
                confidence=0.98,
            )
            self.add_payment(
                "clean_common_name",
                recipient_name=COMMON_FALSE_POSITIVE_NAMES[idx % len(COMMON_FALSE_POSITIVE_NAMES)],
                recipient_iban=recipient_iban,
                recipient_country=recipient_country,
                amount=1400 + idx * 50,
                currency=self._currency(),
                expected_verdict="NO_MATCH",
                ground_truth_reason="recipient name is a common false-positive pattern but the IBAN sits in a clean cluster",
            )

    def _build_shell_company(self) -> None:
        for idx in range(SCENARIO_COUNTS["shell_company"]):
            sanction_key, sanction_name, country = self._new_person(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                sanctioned=True,
                label="shell-owner",
            )
            company_key, company_name, _ = self._new_company(
                risk_level="SUSPICIOUS",
                risk_source="synthetic:shell-company",
                country=country,
                suspicious=True,
                label="shell-company",
            )
            recipient_iban, recipient_country = self._new_iban(
                country=country,
                label="shell-recipient",
            )
            self.add_edge(
                sanction_key,
                company_key,
                "OWNS",
                amount=0,
                tx_count=1,
                first_seen_days_ago=420,
                last_seen_days_ago=30,
                confidence=0.95,
            )
            self.add_edge(
                company_key,
                recipient_iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=210,
                last_seen_days_ago=5,
                confidence=0.99,
            )
            self.add_payment(
                "shell_company",
                recipient_name=company_name,
                recipient_iban=recipient_iban,
                recipient_country=recipient_country,
                amount=9100 + idx * 220,
                currency="USD",
                expected_verdict="REVIEW",
                ground_truth_reason="recipient account belongs to a shell company ultimately owned by a sanctioned person",
            )

    def _build_high_volume_proxy(self) -> None:
        for idx in range(SCENARIO_COUNTS["high_volume_proxy"]):
            sanction_key, sanction_name, country = self._new_person(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                sanctioned=True,
                label="proxy-owner",
            )
            source_iban, _ = self._new_iban(
                risk_level="SANCTIONED",
                risk_source="synthetic:sanctions",
                country=country,
                label="proxy-source",
            )
            proxy_iban, proxy_country = self._new_iban(
                risk_level="SUSPICIOUS",
                risk_source="synthetic:high-volume-proxy",
                label="proxy-middle",
            )
            recipient_iban, recipient_country = self._new_iban(
                country=proxy_country,
                label="proxy-recipient",
            )
            self.add_edge(
                sanction_key,
                source_iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=120,
                last_seen_days_ago=4,
                confidence=1.0,
            )
            self.add_edge(
                source_iban,
                proxy_iban,
                "SENT_TO",
                amount=50000 + idx * 1200,
                tx_count=9 + idx % 4,
                first_seen_days_ago=18,
                last_seen_days_ago=2,
                confidence=0.97,
            )
            risky_amount = 47000 + idx * 1100
            self.add_edge(
                proxy_iban,
                recipient_iban,
                "SENT_TO",
                amount=risky_amount,
                tx_count=8 + idx % 3,
                first_seen_days_ago=12,
                last_seen_days_ago=1,
                confidence=0.96,
            )
            side_outflows = [2000, 1500, 3000, 6500]
            for side_idx, base_amount in enumerate(side_outflows):
                clean_owner_key, _, clean_country = self._new_person(label="proxy-clean-out")
                clean_iban, _ = self._new_iban(
                    country=clean_country,
                    label="proxy-clean-out",
                )
                self.add_edge(
                    clean_owner_key,
                    clean_iban,
                    "USES_ACCOUNT",
                    amount=0,
                    tx_count=1,
                    first_seen_days_ago=320,
                    last_seen_days_ago=5 + side_idx,
                    confidence=0.98,
                )
                self.add_edge(
                    proxy_iban,
                    clean_iban,
                    "SENT_TO",
                    amount=base_amount + (idx % 3) * 150,
                    tx_count=1 + side_idx % 2,
                    first_seen_days_ago=20 + side_idx * 3,
                    last_seen_days_ago=2 + side_idx,
                    confidence=0.78 + side_idx * 0.03,
                )

            benign_inflows = [2500, 3500, 4000]
            for inflow_idx, base_amount in enumerate(benign_inflows):
                clean_owner_key, _, clean_country = self._new_company(label="proxy-clean-in")
                clean_source_iban, _ = self._new_iban(
                    country=clean_country,
                    label="proxy-clean-in",
                )
                self.add_edge(
                    clean_owner_key,
                    clean_source_iban,
                    "USES_ACCOUNT",
                    amount=0,
                    tx_count=1,
                    first_seen_days_ago=340,
                    last_seen_days_ago=4 + inflow_idx,
                    confidence=0.99,
                )
                self.add_edge(
                    clean_source_iban,
                    recipient_iban,
                    "SENT_TO",
                    amount=base_amount + (idx % 2) * 125,
                    tx_count=1 + inflow_idx % 2,
                    first_seen_days_ago=16 + inflow_idx * 2,
                    last_seen_days_ago=3 + inflow_idx,
                    confidence=0.74 + inflow_idx * 0.04,
                )
            self.add_payment(
                "high_volume_proxy",
                recipient_name=f"{sanction_name} Proxy Route",
                recipient_iban=recipient_iban,
                recipient_country=recipient_country,
                amount=15000 + idx * 450,
                currency="EUR",
                expected_verdict="REVIEW",
                ground_truth_reason="recipient receives recent high-volume flows through a proxy account funded by a sanctioned source",
            )

    def _build_background_clean_entities(self) -> None:
        for idx in range(BACKGROUND_ENTITY_COUNT):
            is_company = idx % 4 == 0
            if is_company:
                owner_key, _, country = self._new_company(label="bg-clean")
            else:
                owner_key, _, country = self._new_person(label="bg-clean")
            account_count = 1 if idx % 5 else 2
            for _ in range(account_count):
                iban, _ = self._new_iban(country=country, label="bg-clean")
                self.background_flow_ibans.append(iban)
                self.add_edge(
                    owner_key,
                    iban,
                    "USES_ACCOUNT",
                    amount=0,
                    tx_count=1,
                    first_seen_days_ago=400,
                    last_seen_days_ago=2,
                    confidence=0.98,
                )

    def _build_background_clean_payments(self) -> None:
        for idx in range(SCENARIO_COUNTS["background_clean"]):
            if idx % 5 == 0:
                owner_key, owner_name, country = self._new_company(label="payment-bg-clean")
            else:
                owner_key, owner_name, country = self._new_person(label="payment-bg-clean")
            recipient_iban, recipient_country = self._new_iban(
                country=country,
                label="payment-bg-clean",
            )
            self.add_edge(
                owner_key,
                recipient_iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=360,
                last_seen_days_ago=idx % 20,
                confidence=0.98,
            )
            self.add_payment(
                "background_clean",
                recipient_name=owner_name,
                recipient_iban=recipient_iban,
                recipient_country=recipient_country,
                amount=250 + (idx % 40) * 175,
                currency=self._currency(),
                expected_verdict="NO_MATCH",
                ground_truth_reason="recipient account belongs to an isolated clean background cluster",
            )

    def _build_background_banks(self) -> None:
        banks: list[str] = []
        for idx in range(BACKGROUND_BANK_COUNT):
            country = COUNTRIES[idx % len(COUNTRIES)]
            bank_key = f"BANK:{self.run_tag}:background:{idx + 1:03d}"
            banks.append(
                self.add_node(
                    bank_key,
                    "BANK",
                    display_name=f"Regional Synthetic Bank {idx + 1:03d}",
                    country=country,
                )
            )

        for idx, iban in enumerate(self.background_flow_ibans):
            self.add_edge(
                banks[idx % len(banks)],
                iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=720,
                last_seen_days_ago=idx % 30,
                confidence=0.99,
            )

    def _build_background_clean_flows(self) -> None:
        clean_ibans = self.background_flow_ibans
        if len(clean_ibans) < 2:
            return

        edge_count = 0
        offset = 1
        while edge_count < BACKGROUND_CLEAN_FLOW_EDGES:
            src_idx = edge_count % len(clean_ibans)
            if src_idx == 0 and edge_count:
                offset += 1
            src = clean_ibans[src_idx]
            dst = clean_ibans[(src_idx + offset) % len(clean_ibans)]
            if src == dst or (src, dst, "SENT_TO") in self.edges_by_key:
                offset += 1
                continue
            idx = edge_count
            amount = 150 + (idx % 25) * 120 + self.rng.uniform(0, 90)
            self.add_edge(
                src,
                dst,
                "SENT_TO",
                amount=amount,
                tx_count=1 + idx % 4,
                first_seen_days_ago=240 - (idx % 80),
                last_seen_days_ago=idx % 21,
                confidence=0.58 + (idx % 10) * 0.02,
            )
            edge_count += 1

    def _build_background_suspicious_cluster(self) -> None:
        suspicious_ibans: list[str] = []
        for idx in range(BACKGROUND_SUSPICIOUS_COUNT):
            iban, country = self._new_iban(
                risk_level="SUSPICIOUS",
                risk_source="synthetic:suspicious-background",
                label="bg-suspicious",
            )
            suspicious_ibans.append(iban)
            if idx % 3 == 0:
                owner_key, _, _ = self._new_company(
                    risk_level="SUSPICIOUS",
                    risk_source="synthetic:suspicious-background",
                    country=country,
                    suspicious=True,
                    label="bg-suspicious",
                )
            else:
                owner_key, _, _ = self._new_person(
                    risk_level="SUSPICIOUS",
                    risk_source="synthetic:suspicious-background",
                    country=country,
                    label="bg-suspicious",
                )
            self.add_edge(
                owner_key,
                iban,
                "USES_ACCOUNT",
                amount=0,
                tx_count=1,
                first_seen_days_ago=260,
                last_seen_days_ago=7,
                confidence=0.93,
            )

        clean_ibans = self.background_flow_ibans
        for idx, src in enumerate(suspicious_ibans):
            dst = clean_ibans[(idx * 11) % len(clean_ibans)]
            self.add_edge(
                src,
                dst,
                "SENT_TO",
                amount=9000 + idx * 350,
                tx_count=3 + idx % 3,
                first_seen_days_ago=85,
                last_seen_days_ago=4,
                confidence=0.72,
            )

    def summary(self) -> str:
        verdicts = collections.Counter(p["expected_verdict"] for p in self.payments)
        scenarios = collections.Counter(p["scenario_type"] for p in self.payments)
        risk_anchors = sum(
            node["risk_level"] in {"SANCTIONED", "SUSPICIOUS"}
            for node in self.nodes
        )
        clean_nodes = sum(node["risk_level"] == "NONE" for node in self.nodes)
        degrees: collections.Counter[str] = collections.Counter()
        for edge in self.edges_by_key.values():
            degrees[edge["from_node_key"]] += 1
            degrees[edge["to_node_key"]] += 1
        average_degree = (
            sum(degrees.values()) / len(self.nodes)
            if self.nodes else 0.0
        )
        max_degree = max(degrees.values(), default=0)
        hub_like_nodes = sum(
            degree > HUB_DEGREE_THRESHOLD
            for degree in degrees.values()
        )
        lines = [
            f"nodes inserted: {len(self.nodes)}",
            f"edges inserted: {len(self.edges_by_key)}",
            f"payments inserted: {len(self.payments)}",
            f"risk anchor count: {risk_anchors}",
            f"clean node count: {clean_nodes}",
            f"average degree: {average_degree:.2f}",
            f"max degree: {max_degree}",
            f"hub-like nodes (degree > {HUB_DEGREE_THRESHOLD}): {hub_like_nodes}",
            "",
            "payments by expected_verdict:",
        ]
        for verdict in ("MATCH", "REVIEW", "NO_MATCH"):
            lines.append(f"{verdict}: {verdicts.get(verdict, 0)}")
        lines.append("")
        lines.append("payments by scenario_type:")
        for scenario in SCENARIO_COUNTS:
            lines.append(f"{scenario}: {scenarios.get(scenario, 0)}")
        lines.append("")
        lines.append("SQL check:")
        lines.append("select scenario_type, expected_verdict, count(*)")
        lines.append("from synthetic_payments")
        lines.append("group by scenario_type, expected_verdict")
        lines.append("order by scenario_type;")
        return "\n".join(lines)


def reset_database(engine) -> None:
    metadata.drop_all(engine)
    metadata.create_all(engine)


def insert_dataset(builder: SyntheticGraphBuilder) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(graph_nodes.insert(), builder.nodes)
        conn.execute(graph_edges.insert(), list(builder.edges_by_key.values()))
        conn.execute(synthetic_payments.insert(), builder.payments)


def existing_rows(engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            "graph_nodes": conn.scalar(sa.select(sa.func.count()).select_from(graph_nodes)) or 0,
            "graph_edges": conn.scalar(sa.select(sa.func.count()).select_from(graph_edges)) or 0,
            "synthetic_payments": conn.scalar(sa.select(sa.func.count()).select_from(synthetic_payments)) or 0,
            "exposure_index": conn.scalar(sa.select(sa.func.count()).select_from(exposure_index)) or 0,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="deterministic RNG seed")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop and recreate the graph tables before inserting synthetic data",
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
            "database already contains graph data; re-run with --reset to rebuild deterministically"
        )

    builder = SyntheticGraphBuilder(seed=args.seed)
    builder.build()
    insert_dataset(builder)
    print(builder.summary())


if __name__ == "__main__":
    main()
