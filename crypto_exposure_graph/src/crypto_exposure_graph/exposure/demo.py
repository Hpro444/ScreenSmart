"""Print one lookup result for each synthetic crypto exposure scenario."""

from __future__ import annotations

import json

import sqlalchemy as sa

from ..db.database import get_engine
from ..db.schema import crypto_synthetic_screenings
from .lookup import CryptoWalletExposureLookup

SCENARIO_ORDER = [
    "direct_sanctioned_wallet",
    "one_hop_wallet_exposure",
    "two_hop_wallet_exposure",
    "crypto_derived_anchor_milica_to_sanctioned",
    "crypto_mateja_to_derived_anchor",
    "crypto_andrija_funds_derived_proxy",
    "crypto_tiny_upstream_funding_suppressed",
    "crypto_exchange_upstream_funding_suppressed",
    "crypto_bridge_or_mixer_upstream_suppressed",
    "crypto_normal_high_concentration_control_no_match",
    "crypto_old_weak_derived_anchor_suppressed",
    "repeated_small_transfers_to_risky_wallet",
    "isolated_dust_exposure",
    "exchange_contamination_prevented",
    "bridge_contamination_prevented",
    "mixer_route",
    "bridge_route",
    "ransomware_cluster",
    "exchange_hot_wallet_noise",
    "smart_contract_noise",
    "clean_wallet",
]


def main() -> None:
    engine = get_engine()
    lookup = CryptoWalletExposureLookup.load(engine)
    rows_by_scenario: dict[str, dict] = {}
    with engine.connect() as conn:
        for row in conn.execute(
            sa.select(
                crypto_synthetic_screenings.c.case_id,
                crypto_synthetic_screenings.c.scenario_type,
                crypto_synthetic_screenings.c.chain,
                crypto_synthetic_screenings.c.wallet_address,
                crypto_synthetic_screenings.c.asset,
                crypto_synthetic_screenings.c.amount_usd,
                crypto_synthetic_screenings.c.expected_verdict,
                crypto_synthetic_screenings.c.ground_truth_reason,
            ).order_by(crypto_synthetic_screenings.c.case_id)
        ):
            rows_by_scenario.setdefault(row.scenario_type, row)

    for scenario in SCENARIO_ORDER:
        row = rows_by_scenario.get(scenario)
        if row is None:
            print(f"[missing scenario] {scenario}")
            print()
            continue
        result = lookup.screen_wallet(
            row.chain,
            row.wallet_address,
            asset=row.asset,
            amount_usd=float(row.amount_usd or 0.0),
        )
        print(f"Scenario: {scenario}")
        print(f"Case ID: {row.case_id}")
        print(f"Expected: {row.expected_verdict}")
        print(f"Observed: {result.recommended_action.value}")
        print(f"Input: chain={row.chain} wallet={row.wallet_address} asset={row.asset} amount_usd={float(row.amount_usd or 0.0):.2f}")
        print(f"Score: {result.score:.4f}")
        print(f"Direct hit: {result.direct_hit}")
        print(f"Source risk level: {result.source_risk_level}")
        print(f"Rule triggers: {', '.join(result.rule_triggers) if result.rule_triggers else '-'}")
        print(f"Reason: {result.reason}")
        print("Best path:")
        print(json.dumps(result.best_path, indent=2))
        print()


if __name__ == "__main__":
    main()
