# Sanctions Evasion Demo

This document is generated from live synthetic data and live runtime lookup output.

Regenerate it with:

```powershell
python scripts/generate_sanctions_report.py --regenerate --write-markdown
```

Every example below contains:

- synthetic transaction rows from the graph
- involved accounts, wallets, and entities
- expected decision and reason codes
- actual runtime output
- intermediate scoring math

Reason-code implementation audit:

- `DIRECT_SANCTIONS_MATCH` and `SANCTIONED_WALLET_MATCH` are implemented from direct sanctioned entity or wallet hits.
- `OUTBOUND_1_HOP_TO_SANCTIONED` and `OUTBOUND_2_HOP_TO_SANCTIONED` are implemented from policy-valid reverse flow evidence on directed payment edges.
- `INBOUND_FROM_SANCTIONED` is implemented from direct forward flow from sanctioned sources.
- `SHARED_INTERMEDIARY_WITH_SANCTIONED` is implemented for indirect sanctioned paths that are not clean directional inbound or outbound routes.
- `PROXY_ACCOUNT_BEHAVIOR` is implemented from intermediary routing, pass-through structure, or proxy-like account chains.
- `ABNORMAL_VALUE_TO_NEW_COUNTERPARTY` is implemented from large recent transfers to newly observed counterparties.
- `HIGH_RISK_CORRIDOR` is implemented in the fiat graph from source-country corridor risk and in the crypto graph from bridge-route usage.
- `HUB_PATH_DISCOUNTED` is implemented from shared hub, exchange, or service-boundary suppression.
- `OLD_EXPOSURE_DISCOUNTED` is implemented from stale historical exposure.
- `DUST_EXPOSURE_DISCOUNTED` is implemented in crypto from isolated dust exposure.
- `CRYPTO_DERIVED_RISK_ANCHOR` is implemented when a wallet already has strong direct crypto sanctions-evasion evidence and becomes eligible for the offline second-pass upstream-funding check.
- `UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY` and `CRYPTO_PROXY_CHAIN_FUNDING` are implemented only from the offline derived-anchor precompute pass, never from runtime traversal.
- `CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED` is implemented when a direct upstream funder exists but materiality, recency, or service-boundary rules suppress the second-pass escalation.
- High concentration and repeated structuring are implemented as scoring inputs and evidence context, not as standalone reason codes in the current sanctions model.
- No demo reason code below is a placeholder string without backing logic.

# Fiat Transaction Graph Scenarios

## Direct sanctioned counterparty

Scenario source: `direct_sanctioned_iban` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

The beneficiary IBAN itself is sanctioned. This is a hard block, not an indirect proxy-network case.

**Expected decision**

- `recommended_action`: `MATCH`
- `expected reason codes`: `DIRECT_SANCTIONS_MATCH`
- `observed decision`: `MATCH`
- `observed reason codes`: `DIRECT_SANCTIONS_MATCH`

**Expected evidence package**

```json
[
  {
    "reason_code": "DIRECT_SANCTIONS_MATCH",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "PERSON:s42:direct:0001",
    "to_node_key": "ES11SS42000000000000000001",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2026-04-14",
    "last_seen": "2026-06-11",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ES11SS42000000000000000001",
    "node_type": "IBAN",
    "display_name": "ES11SS42000000000000000001",
    "country": "es",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "PERSON:s42:direct:0001",
    "node_type": "PERSON",
    "display_name": "Farid Nasser",
    "country": "es",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `DIRECT_SANCTIONS_MATCH`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': False, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {}, 'account_age_days': 61, 'path_edge_factors': []}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[('DIRECT_SANCTIONS_MATCH', 1.0)]`

**Intermediate scoring math**

- `graph/exposure score`: `1.0000`
- `risk_score`: `1.0000`
- `sanctions_evasion_score`: `1.0000`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 1.0,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Recipient account is directly matched to a sanctioned account.",
  "evidence": [
    {
      "reason_code": "DIRECT_SANCTIONS_MATCH",
      "severity": "CRITICAL",
      "score_contribution": 1.0,
      "path": [
        {
          "node_key": "ES11SS42000000000000000001",
          "node_type": "IBAN",
          "risk_level": "SANCTIONED"
        }
      ],
      "explanation": "Recipient account is directly matched to a sanctioned account.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": false,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {},
        "account_age_days": 61,
        "path_edge_factors": []
      }
    }
  ]
}
```

## Outbound payment to sanctioned entity

Scenario source: `outbound_to_sanctioned` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

The screened beneficiary previously sent a large recent payment directly to a sanctioned IBAN. Direction matters: this is outbound-to-sanctioned evidence.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `OUTBOUND_1_HOP_TO_SANCTIONED`
- `observed decision`: `REVIEW`
- `observed reason codes`: `OUTBOUND_1_HOP_TO_SANCTIONED, DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "IT93SS42000000000000001151",
    "to_node_key": "IT94SS42000000000000001152",
    "edge_type": "SENT_TO",
    "total_amount": 22000.0,
    "transaction_count": 2,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.97
  },
  {
    "from_node_key": "PERSON:s42:outbound-clean-owner:0551",
    "to_node_key": "IT93SS42000000000000001151",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-07-28",
    "last_seen": "2026-06-11",
    "confidence": 0.99
  },
  {
    "from_node_key": "PERSON:s42:outbound-sanctioned-owner:0552",
    "to_node_key": "IT94SS42000000000000001152",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-06-18",
    "last_seen": "2026-06-09",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "IT93SS42000000000000001151",
    "node_type": "IBAN",
    "display_name": "IT93SS42000000000000001151",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "IT94SS42000000000000001152",
    "node_type": "IBAN",
    "display_name": "IT94SS42000000000000001152",
    "country": "it",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "PERSON:s42:outbound-clean-owner:0551",
    "node_type": "PERSON",
    "display_name": "Nina Meyer",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:outbound-sanctioned-owner:0552",
    "node_type": "PERSON",
    "display_name": "Karim Petrovic",
    "country": "it",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `OUTBOUND_1_HOP_TO_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 22000.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 22000.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'IT94SS42000000000000001152', 'source': 'IT93SS42000000000000001151', 'edge_type': 'SENT_TO', 'amount': 22000.0, 'transaction_count': 2, 'average_transaction_value': 11000.0, 'first_seen': '2026-05-26', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 22000.0, 'receiver_total_incoming_amount': 22000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 321, 'path_edge_factors': [{'node_key': 'IT94SS42000000000000001152', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 22000.0, 'transaction_count': 2, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-05-26', 'last_seen': '2026-06-12'}], 'derived_anchor_context': {'derived_anchor_node': 'IT93SS42000000000000001151', 'derived_anchor_reason_code': 'OUTBOUND_1_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.7, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 22000.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 22000.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'IT94SS42000000000000001152', 'source': 'IT93SS42000000000000001151', 'edge_type': 'SENT_TO', 'amount': 22000.0, 'transaction_count': 2, 'average_transaction_value': 11000.0, 'first_seen': '2026-05-26', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 22000.0, 'receiver_total_incoming_amount': 22000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 321}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'IT93SS42000000000000001151', 'derived_anchor_reason_code': 'OUTBOUND_1_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.7, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 22000.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 22000.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'IT94SS42000000000000001152', 'source': 'IT93SS42000000000000001151', 'edge_type': 'SENT_TO', 'amount': 22000.0, 'transaction_count': 2, 'average_transaction_value': 11000.0, 'first_seen': '2026-05-26', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 22000.0, 'receiver_total_incoming_amount': 22000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 321}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 22000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}]`
- `final score contribution`: `[('OUTBOUND_1_HOP_TO_SANCTIONED', 0.82), ('DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.3679`
- `risk_score`: `0.9600`
- `sanctions_evasion_score`: `0.9600`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 22000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.96,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary connects to a sanctioned entity through a direct outbound payment path.",
  "evidence": [
    {
      "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
      "severity": "HIGH",
      "score_contribution": 0.82,
      "path": [
        {
          "node_key": "IT93SS42000000000000001151",
          "node_type": "IBAN"
        },
        {
          "amount": 22000.0,
          "edge_to": "IT94SS42000000000000001152",
          "node_key": "IT94SS42000000000000001152",
          "edge_from": "IT93SS42000000000000001151",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-05-26",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary connects to a sanctioned entity through a direct outbound payment path.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 22000.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 22000.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "IT94SS42000000000000001152",
          "source": "IT93SS42000000000000001151",
          "edge_type": "SENT_TO",
          "amount": 22000.0,
          "transaction_count": 2,
          "average_transaction_value": 11000.0,
          "first_seen": "2026-05-26",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 22000.0,
          "receiver_total_incoming_amount": 22000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 321,
        "path_edge_factors": [
          {
            "node_key": "IT94SS42000000000000001152",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 22000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-05-26",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "IT93SS42000000000000001151",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 22000.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 22000.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "IT94SS42000000000000001152",
              "source": "IT93SS42000000000000001151",
              "edge_type": "SENT_TO",
              "amount": 22000.0,
              "transaction_count": 2,
              "average_transaction_value": 11000.0,
              "first_seen": "2026-05-26",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 22000.0,
              "receiver_total_incoming_amount": 22000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 321
          }
        }
      }
    },
    {
      "reason_code": "DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "node_key": "IT93SS42000000000000001151",
          "node_type": "IBAN"
        },
        {
          "amount": 22000.0,
          "edge_to": "IT94SS42000000000000001152",
          "node_key": "IT94SS42000000000000001152",
          "edge_from": "IT93SS42000000000000001151",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-05-26",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "This account itself qualifies as a derived sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 22000.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 22000.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "IT94SS42000000000000001152",
          "source": "IT93SS42000000000000001151",
          "edge_type": "SENT_TO",
          "amount": 22000.0,
          "transaction_count": 2,
          "average_transaction_value": 11000.0,
          "first_seen": "2026-05-26",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 22000.0,
          "receiver_total_incoming_amount": 22000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 321,
        "path_edge_factors": [
          {
            "node_key": "IT94SS42000000000000001152",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 22000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-05-26",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "IT93SS42000000000000001151",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 22000.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 22000.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "IT94SS42000000000000001152",
              "source": "IT93SS42000000000000001151",
              "edge_type": "SENT_TO",
              "amount": 22000.0,
              "transaction_count": 2,
              "average_transaction_value": 11000.0,
              "first_seen": "2026-05-26",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 22000.0,
              "receiver_total_incoming_amount": 22000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 321
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "IT93SS42000000000000001151",
          "node_type": "IBAN"
        },
        {
          "amount": 22000.0,
          "edge_to": "IT94SS42000000000000001152",
          "node_key": "IT94SS42000000000000001152",
          "edge_from": "IT93SS42000000000000001151",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-05-26",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 22000.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 22000.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "IT94SS42000000000000001152",
          "source": "IT93SS42000000000000001151",
          "edge_type": "SENT_TO",
          "amount": 22000.0,
          "transaction_count": 2,
          "average_transaction_value": 11000.0,
          "first_seen": "2026-05-26",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 22000.0,
          "receiver_total_incoming_amount": 22000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 321,
        "path_edge_factors": [
          {
            "node_key": "IT94SS42000000000000001152",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 22000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-05-26",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "IT93SS42000000000000001151",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 22000.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 22000.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "IT94SS42000000000000001152",
              "source": "IT93SS42000000000000001151",
              "edge_type": "SENT_TO",
              "amount": 22000.0,
              "transaction_count": 2,
              "average_transaction_value": 11000.0,
              "first_seen": "2026-05-26",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 22000.0,
              "receiver_total_incoming_amount": 22000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 321
          }
        }
      }
    }
  ]
}
```

## Inbound funds from sanctioned entity

Scenario source: `one_hop_exposure` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

The beneficiary received funds directly from a sanctioned account. This is directional inbound exposure.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `INBOUND_FROM_SANCTIONED`
- `observed decision`: `REVIEW`
- `observed reason codes`: `INBOUND_FROM_SANCTIONED, DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "INBOUND_FROM_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "GB72SS42000000000000000151",
    "to_node_key": "RS73SS42000000000000000152",
    "edge_type": "SENT_TO",
    "total_amount": 23000.0,
    "transaction_count": 8,
    "first_seen": "2026-05-09",
    "last_seen": "2026-06-10",
    "confidence": 0.94
  },
  {
    "from_node_key": "PERSON:s42:onehop:0151",
    "to_node_key": "GB72SS42000000000000000151",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2026-01-24",
    "last_seen": "2026-06-05",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "RS73SS42000000000000000152",
    "node_type": "IBAN",
    "display_name": "RS73SS42000000000000000152",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "GB72SS42000000000000000151",
    "node_type": "IBAN",
    "display_name": "GB72SS42000000000000000151",
    "country": "gb",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "PERSON:s42:onehop:0151",
    "node_type": "PERSON",
    "display_name": "Rashid Baranov",
    "country": "gb",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `INBOUND_FROM_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 23000.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 23000.0, 'largest_incoming_tx_count': 8, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {'counterparty': 'RS73SS42000000000000000152', 'source': 'GB72SS42000000000000000151', 'edge_type': 'SENT_TO', 'amount': 23000.0, 'transaction_count': 8, 'average_transaction_value': 2875.0, 'first_seen': '2026-05-09', 'last_seen': '2026-06-10', 'sender_total_outgoing_amount': 23000.0, 'receiver_total_incoming_amount': 23000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': None, 'path_edge_factors': [{'node_key': 'GB72SS42000000000000000151', 'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 23000.0, 'transaction_count': 8, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 0.85, 'first_seen': '2026-05-09', 'last_seen': '2026-06-10'}], 'derived_anchor_context': {'derived_anchor_node': 'RS73SS42000000000000000152', 'derived_anchor_reason_code': 'INBOUND_FROM_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 23000.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 23000.0, 'largest_incoming_tx_count': 8, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {'counterparty': 'RS73SS42000000000000000152', 'source': 'GB72SS42000000000000000151', 'edge_type': 'SENT_TO', 'amount': 23000.0, 'transaction_count': 8, 'average_transaction_value': 2875.0, 'first_seen': '2026-05-09', 'last_seen': '2026-06-10', 'sender_total_outgoing_amount': 23000.0, 'receiver_total_incoming_amount': 23000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': None}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'RS73SS42000000000000000152', 'derived_anchor_reason_code': 'INBOUND_FROM_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 23000.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 23000.0, 'largest_incoming_tx_count': 8, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {'counterparty': 'RS73SS42000000000000000152', 'source': 'GB72SS42000000000000000151', 'edge_type': 'SENT_TO', 'amount': 23000.0, 'transaction_count': 8, 'average_transaction_value': 2875.0, 'first_seen': '2026-05-09', 'last_seen': '2026-06-10', 'sender_total_outgoing_amount': 23000.0, 'receiver_total_incoming_amount': 23000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': None}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 23000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 0.85}]`
- `final score contribution`: `[('INBOUND_FROM_SANCTIONED', 0.48), ('DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.2886`
- `risk_score`: `0.6200`
- `sanctions_evasion_score`: `0.6200`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 23000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 0.85}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.62,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary received value through a path originating from a sanctioned entity.",
  "evidence": [
    {
      "reason_code": "INBOUND_FROM_SANCTIONED",
      "severity": "MEDIUM",
      "score_contribution": 0.48,
      "path": [
        {
          "node_key": "RS73SS42000000000000000152",
          "node_type": "IBAN"
        },
        {
          "amount": 23000.0,
          "edge_to": "RS73SS42000000000000000152",
          "node_key": "GB72SS42000000000000000151",
          "edge_from": "GB72SS42000000000000000151",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-10",
          "node_type": "IBAN",
          "confidence": 0.94,
          "first_seen": "2026-05-09",
          "risk_level": "SANCTIONED",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 8,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary received value through a path originating from a sanctioned entity.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 23000.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 23000.0,
        "largest_incoming_tx_count": 8,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "RS73SS42000000000000000152",
          "source": "GB72SS42000000000000000151",
          "edge_type": "SENT_TO",
          "amount": 23000.0,
          "transaction_count": 8,
          "average_transaction_value": 2875.0,
          "first_seen": "2026-05-09",
          "last_seen": "2026-06-10",
          "sender_total_outgoing_amount": 23000.0,
          "receiver_total_incoming_amount": 23000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": null,
        "path_edge_factors": [
          {
            "node_key": "GB72SS42000000000000000151",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 23000.0,
            "transaction_count": 8,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-05-09",
            "last_seen": "2026-06-10"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS73SS42000000000000000152",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 23000.0,
            "total_outgoing_amount": 0.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 0.0,
            "largest_outgoing_tx_count": 0,
            "largest_incoming_amount": 23000.0,
            "largest_incoming_tx_count": 8,
            "max_outgoing_concentration": 0.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {},
            "largest_incoming_edge": {
              "counterparty": "RS73SS42000000000000000152",
              "source": "GB72SS42000000000000000151",
              "edge_type": "SENT_TO",
              "amount": 23000.0,
              "transaction_count": 8,
              "average_transaction_value": 2875.0,
              "first_seen": "2026-05-09",
              "last_seen": "2026-06-10",
              "sender_total_outgoing_amount": 23000.0,
              "receiver_total_incoming_amount": 23000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": null
          }
        }
      }
    },
    {
      "reason_code": "DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "node_key": "RS73SS42000000000000000152",
          "node_type": "IBAN"
        },
        {
          "amount": 23000.0,
          "edge_to": "RS73SS42000000000000000152",
          "node_key": "GB72SS42000000000000000151",
          "edge_from": "GB72SS42000000000000000151",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-10",
          "node_type": "IBAN",
          "confidence": 0.94,
          "first_seen": "2026-05-09",
          "risk_level": "SANCTIONED",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 8,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "This account itself qualifies as a derived sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 23000.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 23000.0,
        "largest_incoming_tx_count": 8,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "RS73SS42000000000000000152",
          "source": "GB72SS42000000000000000151",
          "edge_type": "SENT_TO",
          "amount": 23000.0,
          "transaction_count": 8,
          "average_transaction_value": 2875.0,
          "first_seen": "2026-05-09",
          "last_seen": "2026-06-10",
          "sender_total_outgoing_amount": 23000.0,
          "receiver_total_incoming_amount": 23000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": null,
        "path_edge_factors": [
          {
            "node_key": "GB72SS42000000000000000151",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 23000.0,
            "transaction_count": 8,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-05-09",
            "last_seen": "2026-06-10"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS73SS42000000000000000152",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 23000.0,
            "total_outgoing_amount": 0.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 0.0,
            "largest_outgoing_tx_count": 0,
            "largest_incoming_amount": 23000.0,
            "largest_incoming_tx_count": 8,
            "max_outgoing_concentration": 0.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {},
            "largest_incoming_edge": {
              "counterparty": "RS73SS42000000000000000152",
              "source": "GB72SS42000000000000000151",
              "edge_type": "SENT_TO",
              "amount": 23000.0,
              "transaction_count": 8,
              "average_transaction_value": 2875.0,
              "first_seen": "2026-05-09",
              "last_seen": "2026-06-10",
              "sender_total_outgoing_amount": 23000.0,
              "receiver_total_incoming_amount": 23000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": null
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "RS73SS42000000000000000152",
          "node_type": "IBAN"
        },
        {
          "amount": 23000.0,
          "edge_to": "RS73SS42000000000000000152",
          "node_key": "GB72SS42000000000000000151",
          "edge_from": "GB72SS42000000000000000151",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-10",
          "node_type": "IBAN",
          "confidence": 0.94,
          "first_seen": "2026-05-09",
          "risk_level": "SANCTIONED",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 8,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 23000.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 23000.0,
        "largest_incoming_tx_count": 8,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "RS73SS42000000000000000152",
          "source": "GB72SS42000000000000000151",
          "edge_type": "SENT_TO",
          "amount": 23000.0,
          "transaction_count": 8,
          "average_transaction_value": 2875.0,
          "first_seen": "2026-05-09",
          "last_seen": "2026-06-10",
          "sender_total_outgoing_amount": 23000.0,
          "receiver_total_incoming_amount": 23000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": null,
        "path_edge_factors": [
          {
            "node_key": "GB72SS42000000000000000151",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 23000.0,
            "transaction_count": 8,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-05-09",
            "last_seen": "2026-06-10"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS73SS42000000000000000152",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 23000.0,
            "total_outgoing_amount": 0.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 0.0,
            "largest_outgoing_tx_count": 0,
            "largest_incoming_amount": 23000.0,
            "largest_incoming_tx_count": 8,
            "max_outgoing_concentration": 0.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {},
            "largest_incoming_edge": {
              "counterparty": "RS73SS42000000000000000152",
              "source": "GB72SS42000000000000000151",
              "edge_type": "SENT_TO",
              "amount": 23000.0,
              "transaction_count": 8,
              "average_transaction_value": 2875.0,
              "first_seen": "2026-05-09",
              "last_seen": "2026-06-10",
              "sender_total_outgoing_amount": 23000.0,
              "receiver_total_incoming_amount": 23000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": null
          }
        }
      }
    }
  ]
}
```

## Two-hop sanctions exposure

Scenario source: `two_hop_exposure` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

Funds route through an intermediary account before reaching the beneficiary. The route is still short and recent enough to justify review.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `INBOUND_FROM_SANCTIONED`
- `observed decision`: `REVIEW`
- `observed reason codes`: `INBOUND_FROM_SANCTIONED, DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "INBOUND_FROM_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "IT30SS42000000000000000554",
    "to_node_key": "TR31SS42000000000000000555",
    "edge_type": "SENT_TO",
    "total_amount": 17800.0,
    "transaction_count": 6,
    "first_seen": "2026-04-14",
    "last_seen": "2026-06-04",
    "confidence": 0.88
  },
  {
    "from_node_key": "TR31SS42000000000000000555",
    "to_node_key": "TR32SS42000000000000000556",
    "edge_type": "SENT_TO",
    "total_amount": 17075.0,
    "transaction_count": 5,
    "first_seen": "2026-05-04",
    "last_seen": "2026-06-07",
    "confidence": 0.84
  },
  {
    "from_node_key": "PERSON:s42:twohop:0352",
    "to_node_key": "IT30SS42000000000000000554",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-11-05",
    "last_seen": "2026-05-29",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "TR32SS42000000000000000556",
    "node_type": "IBAN",
    "display_name": "TR32SS42000000000000000556",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "TR31SS42000000000000000555",
    "node_type": "IBAN",
    "display_name": "TR31SS42000000000000000555",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "IT30SS42000000000000000554",
    "node_type": "IBAN",
    "display_name": "IT30SS42000000000000000554",
    "country": "it",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "PERSON:s42:twohop:0352",
    "node_type": "PERSON",
    "display_name": "Omar Khalaf",
    "country": "it",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `INBOUND_FROM_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 17075.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 17075.0, 'largest_incoming_tx_count': 5, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {'counterparty': 'TR32SS42000000000000000556', 'source': 'TR31SS42000000000000000555', 'edge_type': 'SENT_TO', 'amount': 17075.0, 'transaction_count': 5, 'average_transaction_value': 3415.0, 'first_seen': '2026-05-04', 'last_seen': '2026-06-07', 'sender_total_outgoing_amount': 17075.0, 'receiver_total_incoming_amount': 17075.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': None, 'path_edge_factors': [{'node_key': 'TR31SS42000000000000000555', 'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 17075.0, 'transaction_count': 5, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 0.85, 'first_seen': '2026-05-04', 'last_seen': '2026-06-07'}, {'node_key': 'IT30SS42000000000000000554', 'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 17800.0, 'transaction_count': 6, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 0.85, 'first_seen': '2026-04-14', 'last_seen': '2026-06-04'}], 'derived_anchor_context': {'derived_anchor_node': 'TR32SS42000000000000000556', 'derived_anchor_reason_code': 'INBOUND_FROM_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 17075.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 17075.0, 'largest_incoming_tx_count': 5, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {'counterparty': 'TR32SS42000000000000000556', 'source': 'TR31SS42000000000000000555', 'edge_type': 'SENT_TO', 'amount': 17075.0, 'transaction_count': 5, 'average_transaction_value': 3415.0, 'first_seen': '2026-05-04', 'last_seen': '2026-06-07', 'sender_total_outgoing_amount': 17075.0, 'receiver_total_incoming_amount': 17075.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': None}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'TR32SS42000000000000000556', 'derived_anchor_reason_code': 'INBOUND_FROM_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 17075.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 17075.0, 'largest_incoming_tx_count': 5, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {'counterparty': 'TR32SS42000000000000000556', 'source': 'TR31SS42000000000000000555', 'edge_type': 'SENT_TO', 'amount': 17075.0, 'transaction_count': 5, 'average_transaction_value': 3415.0, 'first_seen': '2026-05-04', 'last_seen': '2026-06-07', 'sender_total_outgoing_amount': 17075.0, 'receiver_total_incoming_amount': 17075.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': None}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 17075.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 0.85}, {'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 17800.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 0.8, 'directional_multiplier': 0.85}]`
- `final score contribution`: `[('INBOUND_FROM_SANCTIONED', 0.48), ('DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0319`
- `risk_score`: `0.6200`
- `sanctions_evasion_score`: `0.6200`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 17075.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 0.85}`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 17800.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 0.8, 'directional_multiplier': 0.85}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.62,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary received value through a path originating from a sanctioned entity.",
  "evidence": [
    {
      "reason_code": "INBOUND_FROM_SANCTIONED",
      "severity": "MEDIUM",
      "score_contribution": 0.48,
      "path": [
        {
          "node_key": "TR32SS42000000000000000556",
          "node_type": "IBAN"
        },
        {
          "amount": 17075.0,
          "edge_to": "TR32SS42000000000000000556",
          "node_key": "TR31SS42000000000000000555",
          "edge_from": "TR31SS42000000000000000555",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-07",
          "node_type": "IBAN",
          "confidence": 0.84,
          "first_seen": "2026-05-04",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 5,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 17800.0,
          "edge_to": "TR31SS42000000000000000555",
          "node_key": "IT30SS42000000000000000554",
          "edge_from": "IT30SS42000000000000000554",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-04",
          "node_type": "IBAN",
          "confidence": 0.88,
          "first_seen": "2026-04-14",
          "risk_level": "SANCTIONED",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 6,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary received value through a path originating from a sanctioned entity.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 17075.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 17075.0,
        "largest_incoming_tx_count": 5,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "TR32SS42000000000000000556",
          "source": "TR31SS42000000000000000555",
          "edge_type": "SENT_TO",
          "amount": 17075.0,
          "transaction_count": 5,
          "average_transaction_value": 3415.0,
          "first_seen": "2026-05-04",
          "last_seen": "2026-06-07",
          "sender_total_outgoing_amount": 17075.0,
          "receiver_total_incoming_amount": 17075.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": null,
        "path_edge_factors": [
          {
            "node_key": "TR31SS42000000000000000555",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 17075.0,
            "transaction_count": 5,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-05-04",
            "last_seen": "2026-06-07"
          },
          {
            "node_key": "IT30SS42000000000000000554",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 17800.0,
            "transaction_count": 6,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-04-14",
            "last_seen": "2026-06-04"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "TR32SS42000000000000000556",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 17075.0,
            "total_outgoing_amount": 0.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 0.0,
            "largest_outgoing_tx_count": 0,
            "largest_incoming_amount": 17075.0,
            "largest_incoming_tx_count": 5,
            "max_outgoing_concentration": 0.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {},
            "largest_incoming_edge": {
              "counterparty": "TR32SS42000000000000000556",
              "source": "TR31SS42000000000000000555",
              "edge_type": "SENT_TO",
              "amount": 17075.0,
              "transaction_count": 5,
              "average_transaction_value": 3415.0,
              "first_seen": "2026-05-04",
              "last_seen": "2026-06-07",
              "sender_total_outgoing_amount": 17075.0,
              "receiver_total_incoming_amount": 17075.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": null
          }
        }
      }
    },
    {
      "reason_code": "DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "node_key": "TR32SS42000000000000000556",
          "node_type": "IBAN"
        },
        {
          "amount": 17075.0,
          "edge_to": "TR32SS42000000000000000556",
          "node_key": "TR31SS42000000000000000555",
          "edge_from": "TR31SS42000000000000000555",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-07",
          "node_type": "IBAN",
          "confidence": 0.84,
          "first_seen": "2026-05-04",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 5,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 17800.0,
          "edge_to": "TR31SS42000000000000000555",
          "node_key": "IT30SS42000000000000000554",
          "edge_from": "IT30SS42000000000000000554",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-04",
          "node_type": "IBAN",
          "confidence": 0.88,
          "first_seen": "2026-04-14",
          "risk_level": "SANCTIONED",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 6,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "This account itself qualifies as a derived sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 17075.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 17075.0,
        "largest_incoming_tx_count": 5,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "TR32SS42000000000000000556",
          "source": "TR31SS42000000000000000555",
          "edge_type": "SENT_TO",
          "amount": 17075.0,
          "transaction_count": 5,
          "average_transaction_value": 3415.0,
          "first_seen": "2026-05-04",
          "last_seen": "2026-06-07",
          "sender_total_outgoing_amount": 17075.0,
          "receiver_total_incoming_amount": 17075.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": null,
        "path_edge_factors": [
          {
            "node_key": "TR31SS42000000000000000555",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 17075.0,
            "transaction_count": 5,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-05-04",
            "last_seen": "2026-06-07"
          },
          {
            "node_key": "IT30SS42000000000000000554",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 17800.0,
            "transaction_count": 6,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-04-14",
            "last_seen": "2026-06-04"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "TR32SS42000000000000000556",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 17075.0,
            "total_outgoing_amount": 0.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 0.0,
            "largest_outgoing_tx_count": 0,
            "largest_incoming_amount": 17075.0,
            "largest_incoming_tx_count": 5,
            "max_outgoing_concentration": 0.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {},
            "largest_incoming_edge": {
              "counterparty": "TR32SS42000000000000000556",
              "source": "TR31SS42000000000000000555",
              "edge_type": "SENT_TO",
              "amount": 17075.0,
              "transaction_count": 5,
              "average_transaction_value": 3415.0,
              "first_seen": "2026-05-04",
              "last_seen": "2026-06-07",
              "sender_total_outgoing_amount": 17075.0,
              "receiver_total_incoming_amount": 17075.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": null
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "TR32SS42000000000000000556",
          "node_type": "IBAN"
        },
        {
          "amount": 17075.0,
          "edge_to": "TR32SS42000000000000000556",
          "node_key": "TR31SS42000000000000000555",
          "edge_from": "TR31SS42000000000000000555",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-07",
          "node_type": "IBAN",
          "confidence": 0.84,
          "first_seen": "2026-05-04",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 5,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 17800.0,
          "edge_to": "TR31SS42000000000000000555",
          "node_key": "IT30SS42000000000000000554",
          "edge_from": "IT30SS42000000000000000554",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-04",
          "node_type": "IBAN",
          "confidence": 0.88,
          "first_seen": "2026-04-14",
          "risk_level": "SANCTIONED",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 6,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 17075.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 17075.0,
        "largest_incoming_tx_count": 5,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "TR32SS42000000000000000556",
          "source": "TR31SS42000000000000000555",
          "edge_type": "SENT_TO",
          "amount": 17075.0,
          "transaction_count": 5,
          "average_transaction_value": 3415.0,
          "first_seen": "2026-05-04",
          "last_seen": "2026-06-07",
          "sender_total_outgoing_amount": 17075.0,
          "receiver_total_incoming_amount": 17075.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": null,
        "path_edge_factors": [
          {
            "node_key": "TR31SS42000000000000000555",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 17075.0,
            "transaction_count": 5,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-05-04",
            "last_seen": "2026-06-07"
          },
          {
            "node_key": "IT30SS42000000000000000554",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 17800.0,
            "transaction_count": 6,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-04-14",
            "last_seen": "2026-06-04"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "TR32SS42000000000000000556",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 17075.0,
            "total_outgoing_amount": 0.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 0.0,
            "largest_outgoing_tx_count": 0,
            "largest_incoming_amount": 17075.0,
            "largest_incoming_tx_count": 5,
            "max_outgoing_concentration": 0.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {},
            "largest_incoming_edge": {
              "counterparty": "TR32SS42000000000000000556",
              "source": "TR31SS42000000000000000555",
              "edge_type": "SENT_TO",
              "amount": 17075.0,
              "transaction_count": 5,
              "average_transaction_value": 3415.0,
              "first_seen": "2026-05-04",
              "last_seen": "2026-06-07",
              "sender_total_outgoing_amount": 17075.0,
              "receiver_total_incoming_amount": 17075.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": null
          }
        }
      }
    }
  ]
}
```

## Sanctioned entity to shell company to clean-looking beneficiary

Scenario source: `sanctioned_entity_to_shell_to_beneficiary` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

A sanctioned owner controls a shell company account that then pays a clean-looking beneficiary. The path is indirect but operationally suspicious.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `SHARED_INTERMEDIARY_WITH_SANCTIONED, PROXY_ACCOUNT_BEHAVIOR`
- `observed decision`: `REVIEW`
- `observed reason codes`: `SHARED_INTERMEDIARY_WITH_SANCTIONED, PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "SHARED_INTERMEDIARY_WITH_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "COMPANY:s42:shell-beneficiary-company:0001",
    "to_node_key": "RS84SS42000000000000001231",
    "edge_type": "SENT_TO",
    "total_amount": 31000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-04",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "PERSON:s42:shell-beneficiary-sanctioned-owner:0631",
    "to_node_key": "COMPANY:s42:shell-beneficiary-company:0001",
    "edge_type": "OWNS",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-01-29",
    "last_seen": "2026-05-04",
    "confidence": 0.96
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "RS84SS42000000000000001231",
    "node_type": "IBAN",
    "display_name": "RS84SS42000000000000001231",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "COMPANY:s42:shell-beneficiary-company:0001",
    "node_type": "COMPANY",
    "display_name": "Blue Consulting FZE",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:shell-beneficiary-sanctioned-owner:0631",
    "node_type": "PERSON",
    "display_name": "Rashid Nasser",
    "country": "rs",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `SHARED_INTERMEDIARY_WITH_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 31000.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 31000.0, 'largest_incoming_tx_count': 1, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {'counterparty': 'RS84SS42000000000000001231', 'source': 'COMPANY:s42:shell-beneficiary-company:0001', 'edge_type': 'SENT_TO', 'amount': 31000.0, 'transaction_count': 1, 'average_transaction_value': 31000.0, 'first_seen': '2026-06-04', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 31000.0, 'receiver_total_incoming_amount': 31000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': None, 'path_edge_factors': [{'node_key': 'COMPANY:s42:shell-beneficiary-company:0001', 'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 31000.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 0.85, 'first_seen': '2026-06-04', 'last_seen': '2026-06-12'}, {'node_key': 'PERSON:s42:shell-beneficiary-sanctioned-owner:0631', 'edge_type': 'OWNS', 'semantic_flow': 'relationship', 'amount': 0.0, 'transaction_count': 1, 'flow_concentration': 0.0, 'flow_materiality_weight': 1.0, 'directional_multiplier': 1.0, 'first_seen': '2025-01-29', 'last_seen': '2026-05-04'}]}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 31000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 0.85}, {'edge_type': 'OWNS', 'semantic_flow': 'relationship', 'amount': 0.0, 'flow_materiality_weight': 1.0, 'concentration': 0.0, 'time_decay': 0.4, 'directional_multiplier': 1.0}]`
- `final score contribution`: `[('SHARED_INTERMEDIARY_WITH_SANCTIONED', 0.2), ('PROXY_ACCOUNT_BEHAVIOR', 0.1)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0448`
- `risk_score`: `0.3000`
- `sanctions_evasion_score`: `0.3000`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 31000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 0.85}`
- `{'edge_type': 'OWNS', 'semantic_flow': 'relationship', 'amount': 0.0, 'flow_materiality_weight': 1.0, 'concentration': 0.0, 'time_decay': 0.4, 'directional_multiplier': 1.0}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.3,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary shares an intermediary relationship with a sanctioned entity, but the path is weaker than a clean directional flow.",
  "evidence": [
    {
      "reason_code": "SHARED_INTERMEDIARY_WITH_SANCTIONED",
      "severity": "LOW",
      "score_contribution": 0.2,
      "path": [
        {
          "node_key": "RS84SS42000000000000001231",
          "node_type": "IBAN"
        },
        {
          "amount": 31000.0,
          "edge_to": "RS84SS42000000000000001231",
          "node_key": "COMPANY:s42:shell-beneficiary-company:0001",
          "edge_from": "COMPANY:s42:shell-beneficiary-company:0001",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "COMPANY",
          "confidence": 0.95,
          "first_seen": "2026-06-04",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 0.0,
          "edge_to": "COMPANY:s42:shell-beneficiary-company:0001",
          "node_key": "PERSON:s42:shell-beneficiary-sanctioned-owner:0631",
          "edge_from": "PERSON:s42:shell-beneficiary-sanctioned-owner:0631",
          "edge_type": "OWNS",
          "last_seen": "2026-05-04",
          "node_type": "PERSON",
          "confidence": 0.96,
          "first_seen": "2025-01-29",
          "risk_level": "SANCTIONED",
          "semantic_flow": "relationship",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 0.0,
          "directional_multiplier": 1.0,
          "incoming_concentration": 0.0,
          "outgoing_concentration": 0.0,
          "flow_materiality_weight": 1.0
        }
      ],
      "explanation": "Beneficiary shares an intermediary relationship with a sanctioned entity, but the path is weaker than a clean directional flow.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 31000.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 31000.0,
        "largest_incoming_tx_count": 1,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "RS84SS42000000000000001231",
          "source": "COMPANY:s42:shell-beneficiary-company:0001",
          "edge_type": "SENT_TO",
          "amount": 31000.0,
          "transaction_count": 1,
          "average_transaction_value": 31000.0,
          "first_seen": "2026-06-04",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 31000.0,
          "receiver_total_incoming_amount": 31000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": null,
        "path_edge_factors": [
          {
            "node_key": "COMPANY:s42:shell-beneficiary-company:0001",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 31000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-06-04",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "PERSON:s42:shell-beneficiary-sanctioned-owner:0631",
            "edge_type": "OWNS",
            "semantic_flow": "relationship",
            "amount": 0.0,
            "transaction_count": 1,
            "flow_concentration": 0.0,
            "flow_materiality_weight": 1.0,
            "directional_multiplier": 1.0,
            "first_seen": "2025-01-29",
            "last_seen": "2026-05-04"
          }
        ]
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "RS84SS42000000000000001231",
          "node_type": "IBAN"
        },
        {
          "amount": 31000.0,
          "edge_to": "RS84SS42000000000000001231",
          "node_key": "COMPANY:s42:shell-beneficiary-company:0001",
          "edge_from": "COMPANY:s42:shell-beneficiary-company:0001",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "COMPANY",
          "confidence": 0.95,
          "first_seen": "2026-06-04",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 0.0,
          "edge_to": "COMPANY:s42:shell-beneficiary-company:0001",
          "node_key": "PERSON:s42:shell-beneficiary-sanctioned-owner:0631",
          "edge_from": "PERSON:s42:shell-beneficiary-sanctioned-owner:0631",
          "edge_type": "OWNS",
          "last_seen": "2026-05-04",
          "node_type": "PERSON",
          "confidence": 0.96,
          "first_seen": "2025-01-29",
          "risk_level": "SANCTIONED",
          "semantic_flow": "relationship",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 0.0,
          "directional_multiplier": 1.0,
          "incoming_concentration": 0.0,
          "outgoing_concentration": 0.0,
          "flow_materiality_weight": 1.0
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 31000.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 31000.0,
        "largest_incoming_tx_count": 1,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "RS84SS42000000000000001231",
          "source": "COMPANY:s42:shell-beneficiary-company:0001",
          "edge_type": "SENT_TO",
          "amount": 31000.0,
          "transaction_count": 1,
          "average_transaction_value": 31000.0,
          "first_seen": "2026-06-04",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 31000.0,
          "receiver_total_incoming_amount": 31000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": null,
        "path_edge_factors": [
          {
            "node_key": "COMPANY:s42:shell-beneficiary-company:0001",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 31000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-06-04",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "PERSON:s42:shell-beneficiary-sanctioned-owner:0631",
            "edge_type": "OWNS",
            "semantic_flow": "relationship",
            "amount": 0.0,
            "transaction_count": 1,
            "flow_concentration": 0.0,
            "flow_materiality_weight": 1.0,
            "directional_multiplier": 1.0,
            "first_seen": "2025-01-29",
            "last_seen": "2026-05-04"
          }
        ]
      }
    }
  ]
}
```

## Clean customer to shell company to sanctioned entity

Scenario source: `clean_customer_to_shell_to_sanctioned` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

The beneficiary account has outbound history that leads through a shell company to a sanctioned destination. That is stronger than passive inbound contamination.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `OUTBOUND_2_HOP_TO_SANCTIONED`
- `observed decision`: `REVIEW`
- `observed reason codes`: `OUTBOUND_2_HOP_TO_SANCTIONED, DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "IT35SS42000000000000001271",
    "to_node_key": "IT36SS42000000000000001272",
    "edge_type": "SENT_TO",
    "total_amount": 14500.0,
    "transaction_count": 2,
    "first_seen": "2026-05-30",
    "last_seen": "2026-06-11",
    "confidence": 0.94
  },
  {
    "from_node_key": "IT36SS42000000000000001272",
    "to_node_key": "IT37SS42000000000000001273",
    "edge_type": "SENT_TO",
    "total_amount": 13800.0,
    "transaction_count": 1,
    "first_seen": "2026-06-01",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "PERSON:s42:clean-shell-clean-owner:0671",
    "to_node_key": "IT35SS42000000000000001271",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-09-06",
    "last_seen": "2026-06-10",
    "confidence": 0.98
  },
  {
    "from_node_key": "COMPANY:s42:clean-shell-company:0041",
    "to_node_key": "IT36SS42000000000000001272",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-12-15",
    "last_seen": "2026-06-11",
    "confidence": 0.99
  },
  {
    "from_node_key": "PERSON:s42:clean-shell-sanctioned-owner:0672",
    "to_node_key": "IT37SS42000000000000001273",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-07-28",
    "last_seen": "2026-06-07",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "IT35SS42000000000000001271",
    "node_type": "IBAN",
    "display_name": "IT35SS42000000000000001271",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "IT36SS42000000000000001272",
    "node_type": "IBAN",
    "display_name": "IT36SS42000000000000001272",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "IT37SS42000000000000001273",
    "node_type": "IBAN",
    "display_name": "IT37SS42000000000000001273",
    "country": "it",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "PERSON:s42:clean-shell-clean-owner:0671",
    "node_type": "PERSON",
    "display_name": "Marko Meyer",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "COMPANY:s42:clean-shell-company:0041",
    "node_type": "COMPANY",
    "display_name": "Granite Consulting FZE",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:clean-shell-sanctioned-owner:0672",
    "node_type": "PERSON",
    "display_name": "Omar Karimov",
    "country": "it",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `OUTBOUND_2_HOP_TO_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 14500.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 14500.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'IT36SS42000000000000001272', 'source': 'IT35SS42000000000000001271', 'edge_type': 'SENT_TO', 'amount': 14500.0, 'transaction_count': 2, 'average_transaction_value': 7250.0, 'first_seen': '2026-05-30', 'last_seen': '2026-06-11', 'sender_total_outgoing_amount': 14500.0, 'receiver_total_incoming_amount': 14500.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 281, 'path_edge_factors': [{'node_key': 'IT36SS42000000000000001272', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 14500.0, 'transaction_count': 2, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-05-30', 'last_seen': '2026-06-11'}, {'node_key': 'IT37SS42000000000000001273', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 13800.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-01', 'last_seen': '2026-06-12'}], 'derived_anchor_context': {'derived_anchor_node': 'IT35SS42000000000000001271', 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 14500.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 14500.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'IT36SS42000000000000001272', 'source': 'IT35SS42000000000000001271', 'edge_type': 'SENT_TO', 'amount': 14500.0, 'transaction_count': 2, 'average_transaction_value': 7250.0, 'first_seen': '2026-05-30', 'last_seen': '2026-06-11', 'sender_total_outgoing_amount': 14500.0, 'receiver_total_incoming_amount': 14500.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 281}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'IT35SS42000000000000001271', 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 14500.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 14500.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'IT36SS42000000000000001272', 'source': 'IT35SS42000000000000001271', 'edge_type': 'SENT_TO', 'amount': 14500.0, 'transaction_count': 2, 'average_transaction_value': 7250.0, 'first_seen': '2026-05-30', 'last_seen': '2026-06-11', 'sender_total_outgoing_amount': 14500.0, 'receiver_total_incoming_amount': 14500.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 281}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 14500.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}, {'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 13800.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}]`
- `final score contribution`: `[('OUTBOUND_2_HOP_TO_SANCTIONED', 0.62), ('DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0734`
- `risk_score`: `0.7600`
- `sanctions_evasion_score`: `0.7600`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 14500.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 13800.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.76,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary connects to a sanctioned entity through a two-hop outbound payment route.",
  "evidence": [
    {
      "reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
      "severity": "HIGH",
      "score_contribution": 0.62,
      "path": [
        {
          "node_key": "IT35SS42000000000000001271",
          "node_type": "IBAN"
        },
        {
          "amount": 14500.0,
          "edge_to": "IT36SS42000000000000001272",
          "node_key": "IT36SS42000000000000001272",
          "edge_from": "IT35SS42000000000000001271",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-11",
          "node_type": "IBAN",
          "confidence": 0.94,
          "first_seen": "2026-05-30",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 13800.0,
          "edge_to": "IT37SS42000000000000001273",
          "node_key": "IT37SS42000000000000001273",
          "edge_from": "IT36SS42000000000000001272",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.95,
          "first_seen": "2026-06-01",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary connects to a sanctioned entity through a two-hop outbound payment route.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 14500.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 14500.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "IT36SS42000000000000001272",
          "source": "IT35SS42000000000000001271",
          "edge_type": "SENT_TO",
          "amount": 14500.0,
          "transaction_count": 2,
          "average_transaction_value": 7250.0,
          "first_seen": "2026-05-30",
          "last_seen": "2026-06-11",
          "sender_total_outgoing_amount": 14500.0,
          "receiver_total_incoming_amount": 14500.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 281,
        "path_edge_factors": [
          {
            "node_key": "IT36SS42000000000000001272",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 14500.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-05-30",
            "last_seen": "2026-06-11"
          },
          {
            "node_key": "IT37SS42000000000000001273",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 13800.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-01",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "IT35SS42000000000000001271",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 14500.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 14500.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "IT36SS42000000000000001272",
              "source": "IT35SS42000000000000001271",
              "edge_type": "SENT_TO",
              "amount": 14500.0,
              "transaction_count": 2,
              "average_transaction_value": 7250.0,
              "first_seen": "2026-05-30",
              "last_seen": "2026-06-11",
              "sender_total_outgoing_amount": 14500.0,
              "receiver_total_incoming_amount": 14500.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 281
          }
        }
      }
    },
    {
      "reason_code": "DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "node_key": "IT35SS42000000000000001271",
          "node_type": "IBAN"
        },
        {
          "amount": 14500.0,
          "edge_to": "IT36SS42000000000000001272",
          "node_key": "IT36SS42000000000000001272",
          "edge_from": "IT35SS42000000000000001271",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-11",
          "node_type": "IBAN",
          "confidence": 0.94,
          "first_seen": "2026-05-30",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 13800.0,
          "edge_to": "IT37SS42000000000000001273",
          "node_key": "IT37SS42000000000000001273",
          "edge_from": "IT36SS42000000000000001272",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.95,
          "first_seen": "2026-06-01",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "This account itself qualifies as a derived sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 14500.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 14500.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "IT36SS42000000000000001272",
          "source": "IT35SS42000000000000001271",
          "edge_type": "SENT_TO",
          "amount": 14500.0,
          "transaction_count": 2,
          "average_transaction_value": 7250.0,
          "first_seen": "2026-05-30",
          "last_seen": "2026-06-11",
          "sender_total_outgoing_amount": 14500.0,
          "receiver_total_incoming_amount": 14500.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 281,
        "path_edge_factors": [
          {
            "node_key": "IT36SS42000000000000001272",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 14500.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-05-30",
            "last_seen": "2026-06-11"
          },
          {
            "node_key": "IT37SS42000000000000001273",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 13800.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-01",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "IT35SS42000000000000001271",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 14500.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 14500.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "IT36SS42000000000000001272",
              "source": "IT35SS42000000000000001271",
              "edge_type": "SENT_TO",
              "amount": 14500.0,
              "transaction_count": 2,
              "average_transaction_value": 7250.0,
              "first_seen": "2026-05-30",
              "last_seen": "2026-06-11",
              "sender_total_outgoing_amount": 14500.0,
              "receiver_total_incoming_amount": 14500.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 281
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "IT35SS42000000000000001271",
          "node_type": "IBAN"
        },
        {
          "amount": 14500.0,
          "edge_to": "IT36SS42000000000000001272",
          "node_key": "IT36SS42000000000000001272",
          "edge_from": "IT35SS42000000000000001271",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-11",
          "node_type": "IBAN",
          "confidence": 0.94,
          "first_seen": "2026-05-30",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 13800.0,
          "edge_to": "IT37SS42000000000000001273",
          "node_key": "IT37SS42000000000000001273",
          "edge_from": "IT36SS42000000000000001272",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.95,
          "first_seen": "2026-06-01",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 14500.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 14500.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "IT36SS42000000000000001272",
          "source": "IT35SS42000000000000001271",
          "edge_type": "SENT_TO",
          "amount": 14500.0,
          "transaction_count": 2,
          "average_transaction_value": 7250.0,
          "first_seen": "2026-05-30",
          "last_seen": "2026-06-11",
          "sender_total_outgoing_amount": 14500.0,
          "receiver_total_incoming_amount": 14500.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 281,
        "path_edge_factors": [
          {
            "node_key": "IT36SS42000000000000001272",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 14500.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-05-30",
            "last_seen": "2026-06-11"
          },
          {
            "node_key": "IT37SS42000000000000001273",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 13800.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-01",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "IT35SS42000000000000001271",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 14500.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 14500.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "IT36SS42000000000000001272",
              "source": "IT35SS42000000000000001271",
              "edge_type": "SENT_TO",
              "amount": 14500.0,
              "transaction_count": 2,
              "average_transaction_value": 7250.0,
              "first_seen": "2026-05-30",
              "last_seen": "2026-06-11",
              "sender_total_outgoing_amount": 14500.0,
              "receiver_total_incoming_amount": 14500.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 281
          }
        }
      }
    }
  ]
}
```

## Shell company pass-through structuring

Scenario source: `shell_structuring_pass_through` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

Many small inflows collect in a shell account, followed by a large outbound transfer to a sanctioned destination.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `PROXY_ACCOUNT_BEHAVIOR`
- `observed decision`: `REVIEW`
- `observed reason codes`: `PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "TR66SS42000000000000001391",
    "to_node_key": "TR67SS42000000000000001392",
    "edge_type": "SENT_TO",
    "total_amount": 18000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-07",
    "last_seen": "2026-06-12",
    "confidence": 0.97
  },
  {
    "from_node_key": "TR79SS42000000000000001404",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1335.0,
    "transaction_count": 21,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.84
  },
  {
    "from_node_key": "SG78SS42000000000000001403",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1300.0,
    "transaction_count": 20,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.84
  },
  {
    "from_node_key": "NL77SS42000000000000001402",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1265.0,
    "transaction_count": 19,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.84
  },
  {
    "from_node_key": "DE76SS42000000000000001401",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1230.0,
    "transaction_count": 18,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.84
  },
  {
    "from_node_key": "RS75SS42000000000000001400",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1195.0,
    "transaction_count": 17,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.84
  },
  {
    "from_node_key": "CH74SS42000000000000001399",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1160.0,
    "transaction_count": 16,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.84
  },
  {
    "from_node_key": "SG73SS42000000000000001398",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1125.0,
    "transaction_count": 15,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.84
  },
  {
    "from_node_key": "ES72SS42000000000000001397",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1090.0,
    "transaction_count": 14,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.84
  },
  {
    "from_node_key": "DE71SS42000000000000001396",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1055.0,
    "transaction_count": 13,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.84
  },
  {
    "from_node_key": "SG70SS42000000000000001395",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 1020.0,
    "transaction_count": 12,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.84
  },
  {
    "from_node_key": "RS69SS42000000000000001394",
    "to_node_key": "TR66SS42000000000000001391",
    "edge_type": "SENT_TO",
    "total_amount": 985.0,
    "transaction_count": 11,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.84
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "TR66SS42000000000000001391",
    "node_type": "IBAN",
    "display_name": "TR66SS42000000000000001391",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "COMPANY:s42:shell-structuring-company:0081",
    "node_type": "COMPANY",
    "display_name": "Keystone Consulting FZE",
    "country": "tr",
    "risk_level": "SUSPICIOUS"
  },
  {
    "node_key": "TR67SS42000000000000001392",
    "node_type": "IBAN",
    "display_name": "TR67SS42000000000000001392",
    "country": "tr",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "TR79SS42000000000000001404",
    "node_type": "IBAN",
    "display_name": "TR79SS42000000000000001404",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "SG78SS42000000000000001403",
    "node_type": "IBAN",
    "display_name": "SG78SS42000000000000001403",
    "country": "sg",
    "risk_level": "NONE"
  },
  {
    "node_key": "NL77SS42000000000000001402",
    "node_type": "IBAN",
    "display_name": "NL77SS42000000000000001402",
    "country": "nl",
    "risk_level": "NONE"
  },
  {
    "node_key": "DE76SS42000000000000001401",
    "node_type": "IBAN",
    "display_name": "DE76SS42000000000000001401",
    "country": "de",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS75SS42000000000000001400",
    "node_type": "IBAN",
    "display_name": "RS75SS42000000000000001400",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "CH74SS42000000000000001399",
    "node_type": "IBAN",
    "display_name": "CH74SS42000000000000001399",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "SG73SS42000000000000001398",
    "node_type": "IBAN",
    "display_name": "SG73SS42000000000000001398",
    "country": "sg",
    "risk_level": "NONE"
  },
  {
    "node_key": "ES72SS42000000000000001397",
    "node_type": "IBAN",
    "display_name": "ES72SS42000000000000001397",
    "country": "es",
    "risk_level": "NONE"
  },
  {
    "node_key": "DE71SS42000000000000001396",
    "node_type": "IBAN",
    "display_name": "DE71SS42000000000000001396",
    "country": "de",
    "risk_level": "NONE"
  },
  {
    "node_key": "SG70SS42000000000000001395",
    "node_type": "IBAN",
    "display_name": "SG70SS42000000000000001395",
    "country": "sg",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS69SS42000000000000001394",
    "node_type": "IBAN",
    "display_name": "RS69SS42000000000000001394",
    "country": "rs",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `PROXY_ACCOUNT_BEHAVIOR`
- `transaction pattern evidence`: `{'has_structuring': True, 'has_high_concentration': True, 'small_inbound_counterparty_count': 12, 'small_inbound_total_amount': 13710.0, 'small_inbound_tx_count': 186, 'small_inbound_window_days': 15, 'total_incoming_amount': 13710.0, 'total_outgoing_amount': 18000.0, 'pass_through_ratio': 1.3129, 'largest_outgoing_amount': 18000.0, 'largest_outgoing_tx_count': 1, 'largest_incoming_amount': 1335.0, 'largest_incoming_tx_count': 21, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.097374, 'largest_outgoing_edge': {'counterparty': 'TR67SS42000000000000001392', 'source': 'TR66SS42000000000000001391', 'edge_type': 'SENT_TO', 'amount': 18000.0, 'transaction_count': 1, 'average_transaction_value': 18000.0, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 18000.0, 'receiver_total_incoming_amount': 18000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {'counterparty': 'TR66SS42000000000000001391', 'source': 'TR79SS42000000000000001404', 'edge_type': 'SENT_TO', 'amount': 1335.0, 'transaction_count': 21, 'average_transaction_value': 63.57142857142857, 'first_seen': '2026-05-28', 'last_seen': '2026-06-11', 'sender_total_outgoing_amount': 1335.0, 'receiver_total_incoming_amount': 13710.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 0.09737417943107221}, 'account_age_days': 91, 'path_edge_factors': [{'node_key': 'COMPANY:s42:shell-structuring-company:0081', 'edge_type': 'USES_ACCOUNT', 'semantic_flow': 'relationship', 'amount': 0.0, 'transaction_count': 1, 'flow_concentration': 0.0, 'flow_materiality_weight': 1.0, 'directional_multiplier': 0.95, 'first_seen': '2026-03-15', 'last_seen': '2026-06-11'}]}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[{'edge_type': 'USES_ACCOUNT', 'semantic_flow': 'relationship', 'amount': 0.0, 'flow_materiality_weight': 1.0, 'concentration': 0.0, 'time_decay': 1.0, 'directional_multiplier': 0.95}]`
- `final score contribution`: `[('PROXY_ACCOUNT_BEHAVIOR', 0.44)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.4148`
- `risk_score`: `0.4400`
- `sanctions_evasion_score`: `0.4400`
- `discounts or uplifts`: `none`
- `{'edge_type': 'USES_ACCOUNT', 'semantic_flow': 'relationship', 'amount': 0.0, 'flow_materiality_weight': 1.0, 'concentration': 0.0, 'time_decay': 1.0, 'directional_multiplier': 0.95}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.44,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Path structure is consistent with proxy or pass-through account behavior near a suspicious anchor.",
  "evidence": [
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "MEDIUM",
      "score_contribution": 0.44,
      "path": [
        {
          "node_key": "TR66SS42000000000000001391",
          "node_type": "IBAN"
        },
        {
          "amount": 0.0,
          "edge_to": "TR66SS42000000000000001391",
          "node_key": "COMPANY:s42:shell-structuring-company:0081",
          "edge_from": "COMPANY:s42:shell-structuring-company:0081",
          "edge_type": "USES_ACCOUNT",
          "last_seen": "2026-06-11",
          "node_type": "COMPANY",
          "confidence": 0.99,
          "first_seen": "2026-03-15",
          "risk_level": "SUSPICIOUS",
          "semantic_flow": "relationship",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 0.0,
          "directional_multiplier": 0.95,
          "incoming_concentration": 0.0,
          "outgoing_concentration": 0.0,
          "flow_materiality_weight": 1.0
        }
      ],
      "explanation": "Path structure is consistent with proxy or pass-through account behavior near a suspicious anchor.",
      "decision_factors": {
        "has_structuring": true,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 12,
        "small_inbound_total_amount": 13710.0,
        "small_inbound_tx_count": 186,
        "small_inbound_window_days": 15,
        "total_incoming_amount": 13710.0,
        "total_outgoing_amount": 18000.0,
        "pass_through_ratio": 1.3129,
        "largest_outgoing_amount": 18000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 1335.0,
        "largest_incoming_tx_count": 21,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.097374,
        "largest_outgoing_edge": {
          "counterparty": "TR67SS42000000000000001392",
          "source": "TR66SS42000000000000001391",
          "edge_type": "SENT_TO",
          "amount": 18000.0,
          "transaction_count": 1,
          "average_transaction_value": 18000.0,
          "first_seen": "2026-06-07",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 18000.0,
          "receiver_total_incoming_amount": 18000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {
          "counterparty": "TR66SS42000000000000001391",
          "source": "TR79SS42000000000000001404",
          "edge_type": "SENT_TO",
          "amount": 1335.0,
          "transaction_count": 21,
          "average_transaction_value": 63.57142857142857,
          "first_seen": "2026-05-28",
          "last_seen": "2026-06-11",
          "sender_total_outgoing_amount": 1335.0,
          "receiver_total_incoming_amount": 13710.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 0.09737417943107221
        },
        "account_age_days": 91,
        "path_edge_factors": [
          {
            "node_key": "COMPANY:s42:shell-structuring-company:0081",
            "edge_type": "USES_ACCOUNT",
            "semantic_flow": "relationship",
            "amount": 0.0,
            "transaction_count": 1,
            "flow_concentration": 0.0,
            "flow_materiality_weight": 1.0,
            "directional_multiplier": 0.95,
            "first_seen": "2026-03-15",
            "last_seen": "2026-06-11"
          }
        ]
      }
    }
  ]
}
```

## Abnormal value to a new counterparty

Scenario source: `abnormal_new_counterparty_company` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

A newly active low-activity company account makes one large recent payment to a sanctioned counterparty.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `OUTBOUND_1_HOP_TO_SANCTIONED, ABNORMAL_VALUE_TO_NEW_COUNTERPARTY`
- `observed decision`: `REVIEW`
- `observed reason codes`: `OUTBOUND_1_HOP_TO_SANCTIONED, DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR, ABNORMAL_VALUE_TO_NEW_COUNTERPARTY`

**Expected evidence package**

```json
[
  {
    "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "RS92SS42000000000000001951",
    "to_node_key": "RS93SS42000000000000001952",
    "edge_type": "SENT_TO",
    "total_amount": 42000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-08",
    "last_seen": "2026-06-12",
    "confidence": 0.98
  },
  {
    "from_node_key": "COMPANY:s42:abnormal-company:0601",
    "to_node_key": "RS92SS42000000000000001951",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2026-05-20",
    "last_seen": "2026-06-11",
    "confidence": 0.99
  },
  {
    "from_node_key": "PERSON:s42:abnormal-sanctioned-owner:0791",
    "to_node_key": "RS93SS42000000000000001952",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-06-18",
    "last_seen": "2026-06-05",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "RS92SS42000000000000001951",
    "node_type": "IBAN",
    "display_name": "RS92SS42000000000000001951",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS93SS42000000000000001952",
    "node_type": "IBAN",
    "display_name": "RS93SS42000000000000001952",
    "country": "rs",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "COMPANY:s42:abnormal-company:0601",
    "node_type": "COMPANY",
    "display_name": "Blue Consulting Ltd",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:abnormal-sanctioned-owner:0791",
    "node_type": "PERSON",
    "display_name": "Rashid Rahman",
    "country": "rs",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `OUTBOUND_1_HOP_TO_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 42000.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 42000.0, 'largest_outgoing_tx_count': 1, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'RS93SS42000000000000001952', 'source': 'RS92SS42000000000000001951', 'edge_type': 'SENT_TO', 'amount': 42000.0, 'transaction_count': 1, 'average_transaction_value': 42000.0, 'first_seen': '2026-06-08', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 42000.0, 'receiver_total_incoming_amount': 42000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 25, 'path_edge_factors': [{'node_key': 'RS93SS42000000000000001952', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 42000.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-08', 'last_seen': '2026-06-12'}], 'derived_anchor_context': {'derived_anchor_node': 'RS92SS42000000000000001951', 'derived_anchor_reason_code': 'OUTBOUND_1_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.7, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 42000.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 42000.0, 'largest_outgoing_tx_count': 1, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'RS93SS42000000000000001952', 'source': 'RS92SS42000000000000001951', 'edge_type': 'SENT_TO', 'amount': 42000.0, 'transaction_count': 1, 'average_transaction_value': 42000.0, 'first_seen': '2026-06-08', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 42000.0, 'receiver_total_incoming_amount': 42000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 25}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'RS92SS42000000000000001951', 'derived_anchor_reason_code': 'OUTBOUND_1_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.7, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 42000.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 42000.0, 'largest_outgoing_tx_count': 1, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'RS93SS42000000000000001952', 'source': 'RS92SS42000000000000001951', 'edge_type': 'SENT_TO', 'amount': 42000.0, 'transaction_count': 1, 'average_transaction_value': 42000.0, 'first_seen': '2026-06-08', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 42000.0, 'receiver_total_incoming_amount': 42000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 25}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 42000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}]`
- `final score contribution`: `[('OUTBOUND_1_HOP_TO_SANCTIONED', 0.82), ('DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1), ('ABNORMAL_VALUE_TO_NEW_COUNTERPARTY', 0.08)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.3717`
- `risk_score`: `1.0000`
- `sanctions_evasion_score`: `1.0000`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 42000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 1.0,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary connects to a sanctioned entity through a direct outbound payment path.",
  "evidence": [
    {
      "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
      "severity": "HIGH",
      "score_contribution": 0.82,
      "path": [
        {
          "node_key": "RS92SS42000000000000001951",
          "node_type": "IBAN"
        },
        {
          "amount": 42000.0,
          "edge_to": "RS93SS42000000000000001952",
          "node_key": "RS93SS42000000000000001952",
          "edge_from": "RS92SS42000000000000001951",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-08",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary connects to a sanctioned entity through a direct outbound payment path.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 42000.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 42000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS93SS42000000000000001952",
          "source": "RS92SS42000000000000001951",
          "edge_type": "SENT_TO",
          "amount": 42000.0,
          "transaction_count": 1,
          "average_transaction_value": 42000.0,
          "first_seen": "2026-06-08",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 42000.0,
          "receiver_total_incoming_amount": 42000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 25,
        "path_edge_factors": [
          {
            "node_key": "RS93SS42000000000000001952",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 42000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-08",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS92SS42000000000000001951",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 42000.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 42000.0,
            "largest_outgoing_tx_count": 1,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "RS93SS42000000000000001952",
              "source": "RS92SS42000000000000001951",
              "edge_type": "SENT_TO",
              "amount": 42000.0,
              "transaction_count": 1,
              "average_transaction_value": 42000.0,
              "first_seen": "2026-06-08",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 42000.0,
              "receiver_total_incoming_amount": 42000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 25
          }
        }
      }
    },
    {
      "reason_code": "DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "node_key": "RS92SS42000000000000001951",
          "node_type": "IBAN"
        },
        {
          "amount": 42000.0,
          "edge_to": "RS93SS42000000000000001952",
          "node_key": "RS93SS42000000000000001952",
          "edge_from": "RS92SS42000000000000001951",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-08",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "This account itself qualifies as a derived sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 42000.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 42000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS93SS42000000000000001952",
          "source": "RS92SS42000000000000001951",
          "edge_type": "SENT_TO",
          "amount": 42000.0,
          "transaction_count": 1,
          "average_transaction_value": 42000.0,
          "first_seen": "2026-06-08",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 42000.0,
          "receiver_total_incoming_amount": 42000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 25,
        "path_edge_factors": [
          {
            "node_key": "RS93SS42000000000000001952",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 42000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-08",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS92SS42000000000000001951",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 42000.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 42000.0,
            "largest_outgoing_tx_count": 1,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "RS93SS42000000000000001952",
              "source": "RS92SS42000000000000001951",
              "edge_type": "SENT_TO",
              "amount": 42000.0,
              "transaction_count": 1,
              "average_transaction_value": 42000.0,
              "first_seen": "2026-06-08",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 42000.0,
              "receiver_total_incoming_amount": 42000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 25
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "RS92SS42000000000000001951",
          "node_type": "IBAN"
        },
        {
          "amount": 42000.0,
          "edge_to": "RS93SS42000000000000001952",
          "node_key": "RS93SS42000000000000001952",
          "edge_from": "RS92SS42000000000000001951",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-08",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 42000.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 42000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS93SS42000000000000001952",
          "source": "RS92SS42000000000000001951",
          "edge_type": "SENT_TO",
          "amount": 42000.0,
          "transaction_count": 1,
          "average_transaction_value": 42000.0,
          "first_seen": "2026-06-08",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 42000.0,
          "receiver_total_incoming_amount": 42000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 25,
        "path_edge_factors": [
          {
            "node_key": "RS93SS42000000000000001952",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 42000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-08",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS92SS42000000000000001951",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 42000.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 42000.0,
            "largest_outgoing_tx_count": 1,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "RS93SS42000000000000001952",
              "source": "RS92SS42000000000000001951",
              "edge_type": "SENT_TO",
              "amount": 42000.0,
              "transaction_count": 1,
              "average_transaction_value": 42000.0,
              "first_seen": "2026-06-08",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 42000.0,
              "receiver_total_incoming_amount": 42000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 25
          }
        }
      }
    },
    {
      "reason_code": "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "node_key": "RS92SS42000000000000001951",
          "node_type": "IBAN"
        },
        {
          "amount": 42000.0,
          "edge_to": "RS93SS42000000000000001952",
          "node_key": "RS93SS42000000000000001952",
          "edge_from": "RS92SS42000000000000001951",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-08",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A large recent transfer to a new counterparty increases concern.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 42000.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 42000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS93SS42000000000000001952",
          "source": "RS92SS42000000000000001951",
          "edge_type": "SENT_TO",
          "amount": 42000.0,
          "transaction_count": 1,
          "average_transaction_value": 42000.0,
          "first_seen": "2026-06-08",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 42000.0,
          "receiver_total_incoming_amount": 42000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 25,
        "path_edge_factors": [
          {
            "node_key": "RS93SS42000000000000001952",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 42000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-08",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS92SS42000000000000001951",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 0.0,
            "total_outgoing_amount": 42000.0,
            "pass_through_ratio": 0.0,
            "largest_outgoing_amount": 42000.0,
            "largest_outgoing_tx_count": 1,
            "largest_incoming_amount": 0.0,
            "largest_incoming_tx_count": 0,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.0,
            "largest_outgoing_edge": {
              "counterparty": "RS93SS42000000000000001952",
              "source": "RS92SS42000000000000001951",
              "edge_type": "SENT_TO",
              "amount": 42000.0,
              "transaction_count": 1,
              "average_transaction_value": 42000.0,
              "first_seen": "2026-06-08",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 42000.0,
              "receiver_total_incoming_amount": 42000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {},
            "account_age_days": 25
          }
        }
      }
    }
  ]
}
```

## High concentration flow into a low-activity shell account

Scenario source: `high_concentration_to_shell` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

Most outgoing value from a sanctioned sender concentrates into one suspicious shell account, which is atypical for legitimate commercial behavior.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `PROXY_ACCOUNT_BEHAVIOR`
- `observed decision`: `REVIEW`
- `observed reason codes`: `PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "TR83SS42000000000000002031",
    "to_node_key": "TR84SS42000000000000002032",
    "edge_type": "SENT_TO",
    "total_amount": 88000.0,
    "transaction_count": 6,
    "first_seen": "2026-05-29",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "TR83SS42000000000000002031",
    "to_node_key": "FR87SS42000000000000002035",
    "edge_type": "SENT_TO",
    "total_amount": 3200.0,
    "transaction_count": 1,
    "first_seen": "2026-05-24",
    "last_seen": "2026-06-09",
    "confidence": 0.77
  },
  {
    "from_node_key": "TR83SS42000000000000002031",
    "to_node_key": "TR85SS42000000000000002033",
    "edge_type": "SENT_TO",
    "total_amount": 2400.0,
    "transaction_count": 1,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.77
  },
  {
    "from_node_key": "TR83SS42000000000000002031",
    "to_node_key": "DE86SS42000000000000002034",
    "edge_type": "SENT_TO",
    "total_amount": 1800.0,
    "transaction_count": 1,
    "first_seen": "2026-05-25",
    "last_seen": "2026-06-10",
    "confidence": 0.77
  },
  {
    "from_node_key": "COMPANY:s42:concentration-shell-company:0641",
    "to_node_key": "TR84SS42000000000000002032",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2026-01-04",
    "last_seen": "2026-06-10",
    "confidence": 0.99
  },
  {
    "from_node_key": "PERSON:s42:concentration-sanctioned-owner:0831",
    "to_node_key": "TR83SS42000000000000002031",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-09-26",
    "last_seen": "2026-06-09",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "TR84SS42000000000000002032",
    "node_type": "IBAN",
    "display_name": "TR84SS42000000000000002032",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "COMPANY:s42:concentration-shell-company:0641",
    "node_type": "COMPANY",
    "display_name": "Granite Consulting FZE",
    "country": "tr",
    "risk_level": "SUSPICIOUS"
  },
  {
    "node_key": "TR83SS42000000000000002031",
    "node_type": "IBAN",
    "display_name": "TR83SS42000000000000002031",
    "country": "tr",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "FR87SS42000000000000002035",
    "node_type": "IBAN",
    "display_name": "FR87SS42000000000000002035",
    "country": "fr",
    "risk_level": "NONE"
  },
  {
    "node_key": "TR85SS42000000000000002033",
    "node_type": "IBAN",
    "display_name": "TR85SS42000000000000002033",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "DE86SS42000000000000002034",
    "node_type": "IBAN",
    "display_name": "DE86SS42000000000000002034",
    "country": "de",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:concentration-sanctioned-owner:0831",
    "node_type": "PERSON",
    "display_name": "Ilham Mansouri",
    "country": "tr",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `PROXY_ACCOUNT_BEHAVIOR`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 88000.0, 'total_outgoing_amount': 0.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 0.0, 'largest_outgoing_tx_count': 0, 'largest_incoming_amount': 88000.0, 'largest_incoming_tx_count': 6, 'max_outgoing_concentration': 0.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {}, 'largest_incoming_edge': {'counterparty': 'TR84SS42000000000000002032', 'source': 'TR83SS42000000000000002031', 'edge_type': 'SENT_TO', 'amount': 88000.0, 'transaction_count': 6, 'average_transaction_value': 14666.666666666666, 'first_seen': '2026-05-29', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 95400.0, 'receiver_total_incoming_amount': 88000.0, 'outgoing_concentration': 0.9224318658280922, 'incoming_concentration': 1.0}, 'account_age_days': 161, 'path_edge_factors': [{'node_key': 'COMPANY:s42:concentration-shell-company:0641', 'edge_type': 'USES_ACCOUNT', 'semantic_flow': 'relationship', 'amount': 0.0, 'transaction_count': 1, 'flow_concentration': 0.0, 'flow_materiality_weight': 1.0, 'directional_multiplier': 0.95, 'first_seen': '2026-01-04', 'last_seen': '2026-06-10'}]}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[{'edge_type': 'USES_ACCOUNT', 'semantic_flow': 'relationship', 'amount': 0.0, 'flow_materiality_weight': 1.0, 'concentration': 0.0, 'time_decay': 1.0, 'directional_multiplier': 0.95}]`
- `final score contribution`: `[('PROXY_ACCOUNT_BEHAVIOR', 0.44)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.4148`
- `risk_score`: `0.4400`
- `sanctions_evasion_score`: `0.4400`
- `discounts or uplifts`: `none`
- `{'edge_type': 'USES_ACCOUNT', 'semantic_flow': 'relationship', 'amount': 0.0, 'flow_materiality_weight': 1.0, 'concentration': 0.0, 'time_decay': 1.0, 'directional_multiplier': 0.95}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.44,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Path structure is consistent with proxy or pass-through account behavior near a suspicious anchor.",
  "evidence": [
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "MEDIUM",
      "score_contribution": 0.44,
      "path": [
        {
          "node_key": "TR84SS42000000000000002032",
          "node_type": "IBAN"
        },
        {
          "amount": 0.0,
          "edge_to": "TR84SS42000000000000002032",
          "node_key": "COMPANY:s42:concentration-shell-company:0641",
          "edge_from": "COMPANY:s42:concentration-shell-company:0641",
          "edge_type": "USES_ACCOUNT",
          "last_seen": "2026-06-10",
          "node_type": "COMPANY",
          "confidence": 0.99,
          "first_seen": "2026-01-04",
          "risk_level": "SUSPICIOUS",
          "semantic_flow": "relationship",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 0.0,
          "directional_multiplier": 0.95,
          "incoming_concentration": 0.0,
          "outgoing_concentration": 0.0,
          "flow_materiality_weight": 1.0
        }
      ],
      "explanation": "Path structure is consistent with proxy or pass-through account behavior near a suspicious anchor.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 88000.0,
        "total_outgoing_amount": 0.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 0.0,
        "largest_outgoing_tx_count": 0,
        "largest_incoming_amount": 88000.0,
        "largest_incoming_tx_count": 6,
        "max_outgoing_concentration": 0.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {},
        "largest_incoming_edge": {
          "counterparty": "TR84SS42000000000000002032",
          "source": "TR83SS42000000000000002031",
          "edge_type": "SENT_TO",
          "amount": 88000.0,
          "transaction_count": 6,
          "average_transaction_value": 14666.666666666666,
          "first_seen": "2026-05-29",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 95400.0,
          "receiver_total_incoming_amount": 88000.0,
          "outgoing_concentration": 0.9224318658280922,
          "incoming_concentration": 1.0
        },
        "account_age_days": 161,
        "path_edge_factors": [
          {
            "node_key": "COMPANY:s42:concentration-shell-company:0641",
            "edge_type": "USES_ACCOUNT",
            "semantic_flow": "relationship",
            "amount": 0.0,
            "transaction_count": 1,
            "flow_concentration": 0.0,
            "flow_materiality_weight": 1.0,
            "directional_multiplier": 0.95,
            "first_seen": "2026-01-04",
            "last_seen": "2026-06-10"
          }
        ]
      }
    }
  ]
}
```

## Shared intermediary false-positive suppression

Scenario source: `shared_hub_false_positive_prevented` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

A clean account shares only a downstream hub with a sanctioned sender. The system should discount this as weak shared-hub evidence.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `SHARED_INTERMEDIARY_WITH_SANCTIONED`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `SHARED_INTERMEDIARY_WITH_SANCTIONED`

**Expected evidence package**

```json
[
  {
    "reason_code": "SHARED_INTERMEDIARY_WITH_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "CH62SS42000000000000002811",
    "to_node_key": "CH63SS42000000000000002812",
    "edge_type": "SENT_TO",
    "total_amount": 42000.0,
    "transaction_count": 6,
    "first_seen": "2026-04-19",
    "last_seen": "2026-06-10",
    "confidence": 0.93
  },
  {
    "from_node_key": "CH64SS42000000000000002813",
    "to_node_key": "CH63SS42000000000000002812",
    "edge_type": "SENT_TO",
    "total_amount": 1800.0,
    "transaction_count": 2,
    "first_seen": "2026-05-19",
    "last_seen": "2026-06-11",
    "confidence": 0.91
  },
  {
    "from_node_key": "PERSON:s42:shared-hub-clean-owner:1272",
    "to_node_key": "CH64SS42000000000000002813",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-09-06",
    "last_seen": "2026-06-09",
    "confidence": 0.98
  },
  {
    "from_node_key": "PERSON:s42:shared-hub-source:1271",
    "to_node_key": "CH62SS42000000000000002811",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2026-02-13",
    "last_seen": "2026-06-03",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "CH64SS42000000000000002813",
    "node_type": "IBAN",
    "display_name": "CH64SS42000000000000002813",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "CH63SS42000000000000002812",
    "node_type": "IBAN",
    "display_name": "CH63SS42000000000000002812",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "CH62SS42000000000000002811",
    "node_type": "IBAN",
    "display_name": "CH62SS42000000000000002811",
    "country": "ch",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "PERSON:s42:shared-hub-clean-owner:1272",
    "node_type": "PERSON",
    "display_name": "Daniel Costa",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:shared-hub-source:1271",
    "node_type": "PERSON",
    "display_name": "Rashid Baranov",
    "country": "ch",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `SHARED_INTERMEDIARY_WITH_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': False, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 1800.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 1800.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'CH63SS42000000000000002812', 'source': 'CH64SS42000000000000002813', 'edge_type': 'SENT_TO', 'amount': 1800.0, 'transaction_count': 2, 'average_transaction_value': 900.0, 'first_seen': '2026-05-19', 'last_seen': '2026-06-11', 'sender_total_outgoing_amount': 1800.0, 'receiver_total_incoming_amount': 43800.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 0.0410958904109589}, 'largest_incoming_edge': {}, 'account_age_days': 281, 'path_edge_factors': [{'node_key': 'CH63SS42000000000000002812', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 1800.0, 'transaction_count': 2, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.65, 'directional_multiplier': 1.05, 'first_seen': '2026-05-19', 'last_seen': '2026-06-11'}, {'node_key': 'CH62SS42000000000000002811', 'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 42000.0, 'transaction_count': 6, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 0.85, 'first_seen': '2026-04-19', 'last_seen': '2026-06-10'}]}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 1800.0, 'flow_materiality_weight': 0.65, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}, {'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 42000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 0.85}]`
- `final score contribution`: `[('SHARED_INTERMEDIARY_WITH_SANCTIONED', 0.2)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0426`
- `risk_score`: `0.2000`
- `sanctions_evasion_score`: `0.2000`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 1800.0, 'flow_materiality_weight': 0.65, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'inbound_from_anchor', 'amount': 42000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 0.85}`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.2,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary shares an intermediary relationship with a sanctioned entity, but the path is weaker than a clean directional flow.",
  "evidence": [
    {
      "reason_code": "SHARED_INTERMEDIARY_WITH_SANCTIONED",
      "severity": "LOW",
      "score_contribution": 0.2,
      "path": [
        {
          "node_key": "CH64SS42000000000000002813",
          "node_type": "IBAN"
        },
        {
          "amount": 1800.0,
          "edge_to": "CH63SS42000000000000002812",
          "node_key": "CH63SS42000000000000002812",
          "edge_from": "CH64SS42000000000000002813",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-11",
          "node_type": "IBAN",
          "confidence": 0.91,
          "first_seen": "2026-05-19",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 0.041096,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.65
        },
        {
          "amount": 42000.0,
          "edge_to": "CH63SS42000000000000002812",
          "node_key": "CH62SS42000000000000002811",
          "edge_from": "CH62SS42000000000000002811",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-10",
          "node_type": "IBAN",
          "confidence": 0.93,
          "first_seen": "2026-04-19",
          "risk_level": "SANCTIONED",
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "override_allowed": true,
          "transaction_count": 6,
          "flow_concentration": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 0.958904,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary shares an intermediary relationship with a sanctioned entity, but the path is weaker than a clean directional flow.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": false,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 1800.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 1800.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "CH63SS42000000000000002812",
          "source": "CH64SS42000000000000002813",
          "edge_type": "SENT_TO",
          "amount": 1800.0,
          "transaction_count": 2,
          "average_transaction_value": 900.0,
          "first_seen": "2026-05-19",
          "last_seen": "2026-06-11",
          "sender_total_outgoing_amount": 1800.0,
          "receiver_total_incoming_amount": 43800.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 0.0410958904109589
        },
        "largest_incoming_edge": {},
        "account_age_days": 281,
        "path_edge_factors": [
          {
            "node_key": "CH63SS42000000000000002812",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 1800.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.65,
            "directional_multiplier": 1.05,
            "first_seen": "2026-05-19",
            "last_seen": "2026-06-11"
          },
          {
            "node_key": "CH62SS42000000000000002811",
            "edge_type": "SENT_TO",
            "semantic_flow": "inbound_from_anchor",
            "amount": 42000.0,
            "transaction_count": 6,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 0.85,
            "first_seen": "2026-04-19",
            "last_seen": "2026-06-10"
          }
        ]
      }
    }
  ]
}
```

# Derived Risk Anchor Precompute

## Derived anchor precompute: Milica routes directly to sanctioned

Scenario source: `derived_anchor_milica_to_sanctioned` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

Milica directly pays a sanctioned endpoint. That makes her account a strong derived-risk anchor candidate for the second offline pass.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `OUTBOUND_1_HOP_TO_SANCTIONED, DERIVED_RISK_ANCHOR`
- `observed decision`: `REVIEW`
- `observed reason codes`: `OUTBOUND_1_HOP_TO_SANCTIONED, DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "DERIVED_RISK_ANCHOR",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "RS16SS42000000000000002231",
    "to_node_key": "RS17SS42000000000000002232",
    "edge_type": "SENT_TO",
    "total_amount": 26000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-03",
    "last_seen": "2026-06-12",
    "confidence": 0.98
  },
  {
    "from_node_key": "RS18SS42000000000000002233",
    "to_node_key": "RS16SS42000000000000002231",
    "edge_type": "SENT_TO",
    "total_amount": 21000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.97
  },
  {
    "from_node_key": "RS29SS42000000000000002244",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 18500.0,
    "transaction_count": 2,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "CH28SS42000000000000002243",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1505.0,
    "transaction_count": 21,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "GB27SS42000000000000002242",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1460.0,
    "transaction_count": 20,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "CH26SS42000000000000002241",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1415.0,
    "transaction_count": 19,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "FR25SS42000000000000002240",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1370.0,
    "transaction_count": 18,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "TR24SS42000000000000002239",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1325.0,
    "transaction_count": 17,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ES23SS42000000000000002238",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1280.0,
    "transaction_count": 16,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "TR22SS42000000000000002237",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1235.0,
    "transaction_count": 15,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "IT21SS42000000000000002236",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1190.0,
    "transaction_count": 14,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ES20SS42000000000000002235",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1145.0,
    "transaction_count": 13,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "RS16SS42000000000000002231",
    "node_type": "IBAN",
    "display_name": "RS16SS42000000000000002231",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS17SS42000000000000002232",
    "node_type": "IBAN",
    "display_name": "RS17SS42000000000000002232",
    "country": "rs",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "RS18SS42000000000000002233",
    "node_type": "IBAN",
    "display_name": "RS18SS42000000000000002233",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS29SS42000000000000002244",
    "node_type": "IBAN",
    "display_name": "RS29SS42000000000000002244",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "CH28SS42000000000000002243",
    "node_type": "IBAN",
    "display_name": "CH28SS42000000000000002243",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "GB27SS42000000000000002242",
    "node_type": "IBAN",
    "display_name": "GB27SS42000000000000002242",
    "country": "gb",
    "risk_level": "NONE"
  },
  {
    "node_key": "CH26SS42000000000000002241",
    "node_type": "IBAN",
    "display_name": "CH26SS42000000000000002241",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "FR25SS42000000000000002240",
    "node_type": "IBAN",
    "display_name": "FR25SS42000000000000002240",
    "country": "fr",
    "risk_level": "NONE"
  },
  {
    "node_key": "TR24SS42000000000000002239",
    "node_type": "IBAN",
    "display_name": "TR24SS42000000000000002239",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "ES23SS42000000000000002238",
    "node_type": "IBAN",
    "display_name": "ES23SS42000000000000002238",
    "country": "es",
    "risk_level": "NONE"
  },
  {
    "node_key": "TR22SS42000000000000002237",
    "node_type": "IBAN",
    "display_name": "TR22SS42000000000000002237",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "IT21SS42000000000000002236",
    "node_type": "IBAN",
    "display_name": "IT21SS42000000000000002236",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "ES20SS42000000000000002235",
    "node_type": "IBAN",
    "display_name": "ES20SS42000000000000002235",
    "country": "es",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `OUTBOUND_1_HOP_TO_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 21000.0, 'total_outgoing_amount': 26000.0, 'pass_through_ratio': 1.2381, 'largest_outgoing_amount': 26000.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 21000.0, 'largest_incoming_tx_count': 1, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {'counterparty': 'RS17SS42000000000000002232', 'source': 'RS16SS42000000000000002231', 'edge_type': 'SENT_TO', 'amount': 26000.0, 'transaction_count': 2, 'average_transaction_value': 13000.0, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 26000.0, 'receiver_total_incoming_amount': 26000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {'counterparty': 'RS16SS42000000000000002231', 'source': 'RS18SS42000000000000002233', 'edge_type': 'SENT_TO', 'amount': 21000.0, 'transaction_count': 1, 'average_transaction_value': 21000.0, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 21000.0, 'receiver_total_incoming_amount': 21000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': 221, 'path_edge_factors': [{'node_key': 'RS17SS42000000000000002232', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'transaction_count': 2, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12'}], 'derived_anchor_context': {'derived_anchor_node': 'RS16SS42000000000000002231', 'derived_anchor_reason_code': 'OUTBOUND_1_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.7, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 21000.0, 'total_outgoing_amount': 26000.0, 'pass_through_ratio': 1.2381, 'largest_outgoing_amount': 26000.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 21000.0, 'largest_incoming_tx_count': 1, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {'counterparty': 'RS17SS42000000000000002232', 'source': 'RS16SS42000000000000002231', 'edge_type': 'SENT_TO', 'amount': 26000.0, 'transaction_count': 2, 'average_transaction_value': 13000.0, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 26000.0, 'receiver_total_incoming_amount': 26000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {'counterparty': 'RS16SS42000000000000002231', 'source': 'RS18SS42000000000000002233', 'edge_type': 'SENT_TO', 'amount': 21000.0, 'transaction_count': 1, 'average_transaction_value': 21000.0, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 21000.0, 'receiver_total_incoming_amount': 21000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': 221}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'RS16SS42000000000000002231', 'derived_anchor_reason_code': 'OUTBOUND_1_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.7, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 21000.0, 'total_outgoing_amount': 26000.0, 'pass_through_ratio': 1.2381, 'largest_outgoing_amount': 26000.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 21000.0, 'largest_incoming_tx_count': 1, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 1.0, 'largest_outgoing_edge': {'counterparty': 'RS17SS42000000000000002232', 'source': 'RS16SS42000000000000002231', 'edge_type': 'SENT_TO', 'amount': 26000.0, 'transaction_count': 2, 'average_transaction_value': 13000.0, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 26000.0, 'receiver_total_incoming_amount': 26000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {'counterparty': 'RS16SS42000000000000002231', 'source': 'RS18SS42000000000000002233', 'edge_type': 'SENT_TO', 'amount': 21000.0, 'transaction_count': 1, 'average_transaction_value': 21000.0, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 21000.0, 'receiver_total_incoming_amount': 21000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'account_age_days': 221}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}]`
- `final score contribution`: `[('OUTBOUND_1_HOP_TO_SANCTIONED', 0.82), ('DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.3717`
- `risk_score`: `0.9600`
- `sanctions_evasion_score`: `0.9600`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.96,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary connects to a sanctioned entity through a direct outbound payment path.",
  "evidence": [
    {
      "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
      "severity": "HIGH",
      "score_contribution": 0.82,
      "path": [
        {
          "node_key": "RS16SS42000000000000002231",
          "node_type": "IBAN"
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary connects to a sanctioned entity through a direct outbound payment path.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 21000.0,
        "total_outgoing_amount": 26000.0,
        "pass_through_ratio": 1.2381,
        "largest_outgoing_amount": 26000.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 21000.0,
        "largest_incoming_tx_count": 1,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {
          "counterparty": "RS17SS42000000000000002232",
          "source": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "amount": 26000.0,
          "transaction_count": 2,
          "average_transaction_value": 13000.0,
          "first_seen": "2026-06-03",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 26000.0,
          "receiver_total_incoming_amount": 26000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {
          "counterparty": "RS16SS42000000000000002231",
          "source": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "amount": 21000.0,
          "transaction_count": 1,
          "average_transaction_value": 21000.0,
          "first_seen": "2026-06-05",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 21000.0,
          "receiver_total_incoming_amount": 21000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": 221,
        "path_edge_factors": [
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS16SS42000000000000002231",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 21000.0,
            "total_outgoing_amount": 26000.0,
            "pass_through_ratio": 1.2381,
            "largest_outgoing_amount": 26000.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 21000.0,
            "largest_incoming_tx_count": 1,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {
              "counterparty": "RS17SS42000000000000002232",
              "source": "RS16SS42000000000000002231",
              "edge_type": "SENT_TO",
              "amount": 26000.0,
              "transaction_count": 2,
              "average_transaction_value": 13000.0,
              "first_seen": "2026-06-03",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 26000.0,
              "receiver_total_incoming_amount": 26000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {
              "counterparty": "RS16SS42000000000000002231",
              "source": "RS18SS42000000000000002233",
              "edge_type": "SENT_TO",
              "amount": 21000.0,
              "transaction_count": 1,
              "average_transaction_value": 21000.0,
              "first_seen": "2026-06-05",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 21000.0,
              "receiver_total_incoming_amount": 21000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": 221
          }
        }
      }
    },
    {
      "reason_code": "DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "node_key": "RS16SS42000000000000002231",
          "node_type": "IBAN"
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "This account itself qualifies as a derived sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 21000.0,
        "total_outgoing_amount": 26000.0,
        "pass_through_ratio": 1.2381,
        "largest_outgoing_amount": 26000.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 21000.0,
        "largest_incoming_tx_count": 1,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {
          "counterparty": "RS17SS42000000000000002232",
          "source": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "amount": 26000.0,
          "transaction_count": 2,
          "average_transaction_value": 13000.0,
          "first_seen": "2026-06-03",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 26000.0,
          "receiver_total_incoming_amount": 26000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {
          "counterparty": "RS16SS42000000000000002231",
          "source": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "amount": 21000.0,
          "transaction_count": 1,
          "average_transaction_value": 21000.0,
          "first_seen": "2026-06-05",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 21000.0,
          "receiver_total_incoming_amount": 21000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": 221,
        "path_edge_factors": [
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS16SS42000000000000002231",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 21000.0,
            "total_outgoing_amount": 26000.0,
            "pass_through_ratio": 1.2381,
            "largest_outgoing_amount": 26000.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 21000.0,
            "largest_incoming_tx_count": 1,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {
              "counterparty": "RS17SS42000000000000002232",
              "source": "RS16SS42000000000000002231",
              "edge_type": "SENT_TO",
              "amount": 26000.0,
              "transaction_count": 2,
              "average_transaction_value": 13000.0,
              "first_seen": "2026-06-03",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 26000.0,
              "receiver_total_incoming_amount": 26000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {
              "counterparty": "RS16SS42000000000000002231",
              "source": "RS18SS42000000000000002233",
              "edge_type": "SENT_TO",
              "amount": 21000.0,
              "transaction_count": 1,
              "average_transaction_value": 21000.0,
              "first_seen": "2026-06-05",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 21000.0,
              "receiver_total_incoming_amount": 21000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": 221
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "RS16SS42000000000000002231",
          "node_type": "IBAN"
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 21000.0,
        "total_outgoing_amount": 26000.0,
        "pass_through_ratio": 1.2381,
        "largest_outgoing_amount": 26000.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 21000.0,
        "largest_incoming_tx_count": 1,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 1.0,
        "largest_outgoing_edge": {
          "counterparty": "RS17SS42000000000000002232",
          "source": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "amount": 26000.0,
          "transaction_count": 2,
          "average_transaction_value": 13000.0,
          "first_seen": "2026-06-03",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 26000.0,
          "receiver_total_incoming_amount": 26000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {
          "counterparty": "RS16SS42000000000000002231",
          "source": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "amount": 21000.0,
          "transaction_count": 1,
          "average_transaction_value": 21000.0,
          "first_seen": "2026-06-05",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 21000.0,
          "receiver_total_incoming_amount": 21000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "account_age_days": 221,
        "path_edge_factors": [
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS16SS42000000000000002231",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 0,
            "small_inbound_total_amount": 0.0,
            "small_inbound_tx_count": 0,
            "small_inbound_window_days": null,
            "total_incoming_amount": 21000.0,
            "total_outgoing_amount": 26000.0,
            "pass_through_ratio": 1.2381,
            "largest_outgoing_amount": 26000.0,
            "largest_outgoing_tx_count": 2,
            "largest_incoming_amount": 21000.0,
            "largest_incoming_tx_count": 1,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 1.0,
            "largest_outgoing_edge": {
              "counterparty": "RS17SS42000000000000002232",
              "source": "RS16SS42000000000000002231",
              "edge_type": "SENT_TO",
              "amount": 26000.0,
              "transaction_count": 2,
              "average_transaction_value": 13000.0,
              "first_seen": "2026-06-03",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 26000.0,
              "receiver_total_incoming_amount": 26000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {
              "counterparty": "RS16SS42000000000000002231",
              "source": "RS18SS42000000000000002233",
              "edge_type": "SENT_TO",
              "amount": 21000.0,
              "transaction_count": 1,
              "average_transaction_value": 21000.0,
              "first_seen": "2026-06-05",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 21000.0,
              "receiver_total_incoming_amount": 21000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "account_age_days": 221
          }
        }
      }
    }
  ]
}
```

## Derived anchor precompute: Mateja funds derived anchor

Scenario source: `mateja_shell_to_derived_anchor` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

Mateja behaves like a shell account that routes material value into Milica, who already routes directly to sanctions. The account should still be a normal REVIEW, but also qualify as a derived-risk anchor.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `OUTBOUND_2_HOP_TO_SANCTIONED, DERIVED_RISK_ANCHOR`
- `observed decision`: `REVIEW`
- `observed reason codes`: `OUTBOUND_2_HOP_TO_SANCTIONED, DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR, ABNORMAL_VALUE_TO_NEW_COUNTERPARTY`

**Expected evidence package**

```json
[
  {
    "reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "DERIVED_RISK_ANCHOR",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "RS16SS42000000000000002231",
    "to_node_key": "RS17SS42000000000000002232",
    "edge_type": "SENT_TO",
    "total_amount": 26000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-03",
    "last_seen": "2026-06-12",
    "confidence": 0.98
  },
  {
    "from_node_key": "RS18SS42000000000000002233",
    "to_node_key": "RS16SS42000000000000002231",
    "edge_type": "SENT_TO",
    "total_amount": 21000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.97
  },
  {
    "from_node_key": "RS29SS42000000000000002244",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 18500.0,
    "transaction_count": 2,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "CH28SS42000000000000002243",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1505.0,
    "transaction_count": 21,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "GB27SS42000000000000002242",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1460.0,
    "transaction_count": 20,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "CH26SS42000000000000002241",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1415.0,
    "transaction_count": 19,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "FR25SS42000000000000002240",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1370.0,
    "transaction_count": 18,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "TR24SS42000000000000002239",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1325.0,
    "transaction_count": 17,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ES23SS42000000000000002238",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1280.0,
    "transaction_count": 16,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "TR22SS42000000000000002237",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1235.0,
    "transaction_count": 15,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "IT21SS42000000000000002236",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1190.0,
    "transaction_count": 14,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ES20SS42000000000000002235",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1145.0,
    "transaction_count": 13,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "RS18SS42000000000000002233",
    "node_type": "IBAN",
    "display_name": "RS18SS42000000000000002233",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS16SS42000000000000002231",
    "node_type": "IBAN",
    "display_name": "RS16SS42000000000000002231",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS17SS42000000000000002232",
    "node_type": "IBAN",
    "display_name": "RS17SS42000000000000002232",
    "country": "rs",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "RS29SS42000000000000002244",
    "node_type": "IBAN",
    "display_name": "RS29SS42000000000000002244",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "CH28SS42000000000000002243",
    "node_type": "IBAN",
    "display_name": "CH28SS42000000000000002243",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "GB27SS42000000000000002242",
    "node_type": "IBAN",
    "display_name": "GB27SS42000000000000002242",
    "country": "gb",
    "risk_level": "NONE"
  },
  {
    "node_key": "CH26SS42000000000000002241",
    "node_type": "IBAN",
    "display_name": "CH26SS42000000000000002241",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "FR25SS42000000000000002240",
    "node_type": "IBAN",
    "display_name": "FR25SS42000000000000002240",
    "country": "fr",
    "risk_level": "NONE"
  },
  {
    "node_key": "TR24SS42000000000000002239",
    "node_type": "IBAN",
    "display_name": "TR24SS42000000000000002239",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "ES23SS42000000000000002238",
    "node_type": "IBAN",
    "display_name": "ES23SS42000000000000002238",
    "country": "es",
    "risk_level": "NONE"
  },
  {
    "node_key": "TR22SS42000000000000002237",
    "node_type": "IBAN",
    "display_name": "TR22SS42000000000000002237",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "IT21SS42000000000000002236",
    "node_type": "IBAN",
    "display_name": "IT21SS42000000000000002236",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "ES20SS42000000000000002235",
    "node_type": "IBAN",
    "display_name": "ES20SS42000000000000002235",
    "country": "es",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `OUTBOUND_2_HOP_TO_SANCTIONED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 10, 'small_inbound_total_amount': 13025.0, 'small_inbound_tx_count': 165, 'small_inbound_window_days': 17, 'total_incoming_amount': 31525.0, 'total_outgoing_amount': 21000.0, 'pass_through_ratio': 0.6661, 'largest_outgoing_amount': 21000.0, 'largest_outgoing_tx_count': 1, 'largest_incoming_amount': 18500.0, 'largest_incoming_tx_count': 2, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.586836, 'largest_outgoing_edge': {'counterparty': 'RS16SS42000000000000002231', 'source': 'RS18SS42000000000000002233', 'edge_type': 'SENT_TO', 'amount': 21000.0, 'transaction_count': 1, 'average_transaction_value': 21000.0, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 21000.0, 'receiver_total_incoming_amount': 21000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {'counterparty': 'RS18SS42000000000000002233', 'source': 'RS29SS42000000000000002244', 'edge_type': 'SENT_TO', 'amount': 18500.0, 'transaction_count': 2, 'average_transaction_value': 9250.0, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 20310.0, 'receiver_total_incoming_amount': 31525.0, 'outgoing_concentration': 0.9108813392417529, 'incoming_concentration': 0.5868358445678034}, 'account_age_days': 141, 'path_edge_factors': [{'node_key': 'RS16SS42000000000000002231', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 21000.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12'}, {'node_key': 'RS17SS42000000000000002232', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'transaction_count': 2, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12'}], 'derived_anchor_context': {'derived_anchor_node': 'RS18SS42000000000000002233', 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 10, 'small_inbound_total_amount': 13025.0, 'small_inbound_tx_count': 165, 'small_inbound_window_days': 17, 'total_incoming_amount': 31525.0, 'total_outgoing_amount': 21000.0, 'pass_through_ratio': 0.6661, 'largest_outgoing_amount': 21000.0, 'largest_outgoing_tx_count': 1, 'largest_incoming_amount': 18500.0, 'largest_incoming_tx_count': 2, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.586836, 'largest_outgoing_edge': {'counterparty': 'RS16SS42000000000000002231', 'source': 'RS18SS42000000000000002233', 'edge_type': 'SENT_TO', 'amount': 21000.0, 'transaction_count': 1, 'average_transaction_value': 21000.0, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 21000.0, 'receiver_total_incoming_amount': 21000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {'counterparty': 'RS18SS42000000000000002233', 'source': 'RS29SS42000000000000002244', 'edge_type': 'SENT_TO', 'amount': 18500.0, 'transaction_count': 2, 'average_transaction_value': 9250.0, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 20310.0, 'receiver_total_incoming_amount': 31525.0, 'outgoing_concentration': 0.9108813392417529, 'incoming_concentration': 0.5868358445678034}, 'account_age_days': 141}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'RS18SS42000000000000002233', 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.', 'behavior_factors': {'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 10, 'small_inbound_total_amount': 13025.0, 'small_inbound_tx_count': 165, 'small_inbound_window_days': 17, 'total_incoming_amount': 31525.0, 'total_outgoing_amount': 21000.0, 'pass_through_ratio': 0.6661, 'largest_outgoing_amount': 21000.0, 'largest_outgoing_tx_count': 1, 'largest_incoming_amount': 18500.0, 'largest_incoming_tx_count': 2, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.586836, 'largest_outgoing_edge': {'counterparty': 'RS16SS42000000000000002231', 'source': 'RS18SS42000000000000002233', 'edge_type': 'SENT_TO', 'amount': 21000.0, 'transaction_count': 1, 'average_transaction_value': 21000.0, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 21000.0, 'receiver_total_incoming_amount': 21000.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {'counterparty': 'RS18SS42000000000000002233', 'source': 'RS29SS42000000000000002244', 'edge_type': 'SENT_TO', 'amount': 18500.0, 'transaction_count': 2, 'average_transaction_value': 9250.0, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 20310.0, 'receiver_total_incoming_amount': 31525.0, 'outgoing_concentration': 0.9108813392417529, 'incoming_concentration': 0.5868358445678034}, 'account_age_days': 141}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 21000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}, {'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}]`
- `final score contribution`: `[('OUTBOUND_2_HOP_TO_SANCTIONED', 0.62), ('DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1), ('ABNORMAL_VALUE_TO_NEW_COUNTERPARTY', 0.08)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0781`
- `risk_score`: `0.8400`
- `sanctions_evasion_score`: `0.8400`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 21000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.84,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary connects to a sanctioned entity through a two-hop outbound payment route.",
  "evidence": [
    {
      "reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
      "severity": "HIGH",
      "score_contribution": 0.62,
      "path": [
        {
          "node_key": "RS18SS42000000000000002233",
          "node_type": "IBAN"
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary connects to a sanctioned entity through a two-hop outbound payment route.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 10,
        "small_inbound_total_amount": 13025.0,
        "small_inbound_tx_count": 165,
        "small_inbound_window_days": 17,
        "total_incoming_amount": 31525.0,
        "total_outgoing_amount": 21000.0,
        "pass_through_ratio": 0.6661,
        "largest_outgoing_amount": 21000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 18500.0,
        "largest_incoming_tx_count": 2,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.586836,
        "largest_outgoing_edge": {
          "counterparty": "RS16SS42000000000000002231",
          "source": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "amount": 21000.0,
          "transaction_count": 1,
          "average_transaction_value": 21000.0,
          "first_seen": "2026-06-05",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 21000.0,
          "receiver_total_incoming_amount": 21000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "account_age_days": 141,
        "path_edge_factors": [
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 10,
            "small_inbound_total_amount": 13025.0,
            "small_inbound_tx_count": 165,
            "small_inbound_window_days": 17,
            "total_incoming_amount": 31525.0,
            "total_outgoing_amount": 21000.0,
            "pass_through_ratio": 0.6661,
            "largest_outgoing_amount": 21000.0,
            "largest_outgoing_tx_count": 1,
            "largest_incoming_amount": 18500.0,
            "largest_incoming_tx_count": 2,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.586836,
            "largest_outgoing_edge": {
              "counterparty": "RS16SS42000000000000002231",
              "source": "RS18SS42000000000000002233",
              "edge_type": "SENT_TO",
              "amount": 21000.0,
              "transaction_count": 1,
              "average_transaction_value": 21000.0,
              "first_seen": "2026-06-05",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 21000.0,
              "receiver_total_incoming_amount": 21000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {
              "counterparty": "RS18SS42000000000000002233",
              "source": "RS29SS42000000000000002244",
              "edge_type": "SENT_TO",
              "amount": 18500.0,
              "transaction_count": 2,
              "average_transaction_value": 9250.0,
              "first_seen": "2026-06-06",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 20310.0,
              "receiver_total_incoming_amount": 31525.0,
              "outgoing_concentration": 0.9108813392417529,
              "incoming_concentration": 0.5868358445678034
            },
            "account_age_days": 141
          }
        }
      }
    },
    {
      "reason_code": "DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "node_key": "RS18SS42000000000000002233",
          "node_type": "IBAN"
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "This account itself qualifies as a derived sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 10,
        "small_inbound_total_amount": 13025.0,
        "small_inbound_tx_count": 165,
        "small_inbound_window_days": 17,
        "total_incoming_amount": 31525.0,
        "total_outgoing_amount": 21000.0,
        "pass_through_ratio": 0.6661,
        "largest_outgoing_amount": 21000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 18500.0,
        "largest_incoming_tx_count": 2,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.586836,
        "largest_outgoing_edge": {
          "counterparty": "RS16SS42000000000000002231",
          "source": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "amount": 21000.0,
          "transaction_count": 1,
          "average_transaction_value": 21000.0,
          "first_seen": "2026-06-05",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 21000.0,
          "receiver_total_incoming_amount": 21000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "account_age_days": 141,
        "path_edge_factors": [
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 10,
            "small_inbound_total_amount": 13025.0,
            "small_inbound_tx_count": 165,
            "small_inbound_window_days": 17,
            "total_incoming_amount": 31525.0,
            "total_outgoing_amount": 21000.0,
            "pass_through_ratio": 0.6661,
            "largest_outgoing_amount": 21000.0,
            "largest_outgoing_tx_count": 1,
            "largest_incoming_amount": 18500.0,
            "largest_incoming_tx_count": 2,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.586836,
            "largest_outgoing_edge": {
              "counterparty": "RS16SS42000000000000002231",
              "source": "RS18SS42000000000000002233",
              "edge_type": "SENT_TO",
              "amount": 21000.0,
              "transaction_count": 1,
              "average_transaction_value": 21000.0,
              "first_seen": "2026-06-05",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 21000.0,
              "receiver_total_incoming_amount": 21000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {
              "counterparty": "RS18SS42000000000000002233",
              "source": "RS29SS42000000000000002244",
              "edge_type": "SENT_TO",
              "amount": 18500.0,
              "transaction_count": 2,
              "average_transaction_value": 9250.0,
              "first_seen": "2026-06-06",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 20310.0,
              "receiver_total_incoming_amount": 31525.0,
              "outgoing_concentration": 0.9108813392417529,
              "incoming_concentration": 0.5868358445678034
            },
            "account_age_days": 141
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "RS18SS42000000000000002233",
          "node_type": "IBAN"
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 10,
        "small_inbound_total_amount": 13025.0,
        "small_inbound_tx_count": 165,
        "small_inbound_window_days": 17,
        "total_incoming_amount": 31525.0,
        "total_outgoing_amount": 21000.0,
        "pass_through_ratio": 0.6661,
        "largest_outgoing_amount": 21000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 18500.0,
        "largest_incoming_tx_count": 2,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.586836,
        "largest_outgoing_edge": {
          "counterparty": "RS16SS42000000000000002231",
          "source": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "amount": 21000.0,
          "transaction_count": 1,
          "average_transaction_value": 21000.0,
          "first_seen": "2026-06-05",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 21000.0,
          "receiver_total_incoming_amount": 21000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "account_age_days": 141,
        "path_edge_factors": [
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 10,
            "small_inbound_total_amount": 13025.0,
            "small_inbound_tx_count": 165,
            "small_inbound_window_days": 17,
            "total_incoming_amount": 31525.0,
            "total_outgoing_amount": 21000.0,
            "pass_through_ratio": 0.6661,
            "largest_outgoing_amount": 21000.0,
            "largest_outgoing_tx_count": 1,
            "largest_incoming_amount": 18500.0,
            "largest_incoming_tx_count": 2,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.586836,
            "largest_outgoing_edge": {
              "counterparty": "RS16SS42000000000000002231",
              "source": "RS18SS42000000000000002233",
              "edge_type": "SENT_TO",
              "amount": 21000.0,
              "transaction_count": 1,
              "average_transaction_value": 21000.0,
              "first_seen": "2026-06-05",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 21000.0,
              "receiver_total_incoming_amount": 21000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {
              "counterparty": "RS18SS42000000000000002233",
              "source": "RS29SS42000000000000002244",
              "edge_type": "SENT_TO",
              "amount": 18500.0,
              "transaction_count": 2,
              "average_transaction_value": 9250.0,
              "first_seen": "2026-06-06",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 20310.0,
              "receiver_total_incoming_amount": 31525.0,
              "outgoing_concentration": 0.9108813392417529,
              "incoming_concentration": 0.5868358445678034
            },
            "account_age_days": 141
          }
        }
      }
    },
    {
      "reason_code": "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "node_key": "RS18SS42000000000000002233",
          "node_type": "IBAN"
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A large recent transfer to a new counterparty increases concern.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 10,
        "small_inbound_total_amount": 13025.0,
        "small_inbound_tx_count": 165,
        "small_inbound_window_days": 17,
        "total_incoming_amount": 31525.0,
        "total_outgoing_amount": 21000.0,
        "pass_through_ratio": 0.6661,
        "largest_outgoing_amount": 21000.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 18500.0,
        "largest_incoming_tx_count": 2,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.586836,
        "largest_outgoing_edge": {
          "counterparty": "RS16SS42000000000000002231",
          "source": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "amount": 21000.0,
          "transaction_count": 1,
          "average_transaction_value": 21000.0,
          "first_seen": "2026-06-05",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 21000.0,
          "receiver_total_incoming_amount": 21000.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "account_age_days": 141,
        "path_edge_factors": [
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current account already has strong enough sanctions-evasion evidence to seed a controlled upstream-funding review pass.",
          "behavior_factors": {
            "has_structuring": false,
            "has_high_concentration": true,
            "small_inbound_counterparty_count": 10,
            "small_inbound_total_amount": 13025.0,
            "small_inbound_tx_count": 165,
            "small_inbound_window_days": 17,
            "total_incoming_amount": 31525.0,
            "total_outgoing_amount": 21000.0,
            "pass_through_ratio": 0.6661,
            "largest_outgoing_amount": 21000.0,
            "largest_outgoing_tx_count": 1,
            "largest_incoming_amount": 18500.0,
            "largest_incoming_tx_count": 2,
            "max_outgoing_concentration": 1.0,
            "max_incoming_concentration": 0.586836,
            "largest_outgoing_edge": {
              "counterparty": "RS16SS42000000000000002231",
              "source": "RS18SS42000000000000002233",
              "edge_type": "SENT_TO",
              "amount": 21000.0,
              "transaction_count": 1,
              "average_transaction_value": 21000.0,
              "first_seen": "2026-06-05",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 21000.0,
              "receiver_total_incoming_amount": 21000.0,
              "outgoing_concentration": 1.0,
              "incoming_concentration": 1.0
            },
            "largest_incoming_edge": {
              "counterparty": "RS18SS42000000000000002233",
              "source": "RS29SS42000000000000002244",
              "edge_type": "SENT_TO",
              "amount": 18500.0,
              "transaction_count": 2,
              "average_transaction_value": 9250.0,
              "first_seen": "2026-06-06",
              "last_seen": "2026-06-12",
              "sender_total_outgoing_amount": 20310.0,
              "receiver_total_incoming_amount": 31525.0,
              "outgoing_concentration": 0.9108813392417529,
              "incoming_concentration": 0.5868358445678034
            },
            "account_age_days": 141
          }
        }
      }
    }
  ]
}
```

## Derived anchor precompute: Andrija funds derived proxy

Scenario source: `andrija_funds_derived_proxy` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

Andrija does not have a direct 3-hop runtime traversal. He becomes reviewable only because the offline second pass recognized Mateja as a derived sanctions proxy and then evaluated Andrija's direct funding into that proxy account.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `UPSTREAM_FUNDING_OF_DERIVED_SANCTIONS_PROXY, PROXY_CHAIN_FUNDING`
- `observed decision`: `REVIEW`
- `observed reason codes`: `UPSTREAM_FUNDING_OF_DERIVED_SANCTIONS_PROXY, PROXY_CHAIN_FUNDING, DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR, ABNORMAL_VALUE_TO_NEW_COUNTERPARTY`

**Expected evidence package**

```json
[
  {
    "reason_code": "UPSTREAM_FUNDING_OF_DERIVED_SANCTIONS_PROXY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "PROXY_CHAIN_FUNDING",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "RS16SS42000000000000002231",
    "to_node_key": "RS17SS42000000000000002232",
    "edge_type": "SENT_TO",
    "total_amount": 26000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-03",
    "last_seen": "2026-06-12",
    "confidence": 0.98
  },
  {
    "from_node_key": "RS18SS42000000000000002233",
    "to_node_key": "RS16SS42000000000000002231",
    "edge_type": "SENT_TO",
    "total_amount": 21000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.97
  },
  {
    "from_node_key": "RS29SS42000000000000002244",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 18500.0,
    "transaction_count": 2,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "CH28SS42000000000000002243",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1505.0,
    "transaction_count": 21,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "GB27SS42000000000000002242",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1460.0,
    "transaction_count": 20,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "CH26SS42000000000000002241",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1415.0,
    "transaction_count": 19,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "FR25SS42000000000000002240",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1370.0,
    "transaction_count": 18,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "TR24SS42000000000000002239",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1325.0,
    "transaction_count": 17,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ES23SS42000000000000002238",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1280.0,
    "transaction_count": 16,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "TR22SS42000000000000002237",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1235.0,
    "transaction_count": 15,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "IT21SS42000000000000002236",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1190.0,
    "transaction_count": 14,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ES20SS42000000000000002235",
    "to_node_key": "RS18SS42000000000000002233",
    "edge_type": "SENT_TO",
    "total_amount": 1145.0,
    "transaction_count": 13,
    "first_seen": "2026-05-26",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "RS29SS42000000000000002244",
    "node_type": "IBAN",
    "display_name": "RS29SS42000000000000002244",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS18SS42000000000000002233",
    "node_type": "IBAN",
    "display_name": "RS18SS42000000000000002233",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS16SS42000000000000002231",
    "node_type": "IBAN",
    "display_name": "RS16SS42000000000000002231",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS17SS42000000000000002232",
    "node_type": "IBAN",
    "display_name": "RS17SS42000000000000002232",
    "country": "rs",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "CH28SS42000000000000002243",
    "node_type": "IBAN",
    "display_name": "CH28SS42000000000000002243",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "GB27SS42000000000000002242",
    "node_type": "IBAN",
    "display_name": "GB27SS42000000000000002242",
    "country": "gb",
    "risk_level": "NONE"
  },
  {
    "node_key": "CH26SS42000000000000002241",
    "node_type": "IBAN",
    "display_name": "CH26SS42000000000000002241",
    "country": "ch",
    "risk_level": "NONE"
  },
  {
    "node_key": "FR25SS42000000000000002240",
    "node_type": "IBAN",
    "display_name": "FR25SS42000000000000002240",
    "country": "fr",
    "risk_level": "NONE"
  },
  {
    "node_key": "TR24SS42000000000000002239",
    "node_type": "IBAN",
    "display_name": "TR24SS42000000000000002239",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "ES23SS42000000000000002238",
    "node_type": "IBAN",
    "display_name": "ES23SS42000000000000002238",
    "country": "es",
    "risk_level": "NONE"
  },
  {
    "node_key": "TR22SS42000000000000002237",
    "node_type": "IBAN",
    "display_name": "TR22SS42000000000000002237",
    "country": "tr",
    "risk_level": "NONE"
  },
  {
    "node_key": "IT21SS42000000000000002236",
    "node_type": "IBAN",
    "display_name": "IT21SS42000000000000002236",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "ES20SS42000000000000002235",
    "node_type": "IBAN",
    "display_name": "ES20SS42000000000000002235",
    "country": "es",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `UPSTREAM_FUNDING_OF_DERIVED_SANCTIONS_PROXY`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': True, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 20310.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 18500.0, 'largest_outgoing_tx_count': 2, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 0.910881, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'RS18SS42000000000000002233', 'source': 'RS29SS42000000000000002244', 'edge_type': 'SENT_TO', 'amount': 18500.0, 'transaction_count': 2, 'average_transaction_value': 9250.0, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 20310.0, 'receiver_total_incoming_amount': 31525.0, 'outgoing_concentration': 0.9108813392417529, 'incoming_concentration': 0.5868358445678034}, 'largest_incoming_edge': {}, 'account_age_days': 301, 'path_edge_factors': [{'node_key': 'RS18SS42000000000000002233', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 18500.0, 'transaction_count': 2, 'flow_concentration': 0.910881, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12'}, {'node_key': 'RS16SS42000000000000002231', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 21000.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12'}, {'node_key': 'RS17SS42000000000000002232', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'transaction_count': 2, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12'}], 'derived_anchor_context': {'derived_anchor_node': 'RS18SS42000000000000002233', 'derived_anchor_score': 0.55, 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_explanation': 'Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.', 'derived_anchor_original_score': 0.0781, 'suppression_reason': None, 'upstream_funding_edge': {'edge_type': 'SENT_TO', 'amount': 18500.0, 'transaction_count': 2, 'flow_concentration': 0.910881, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12', 'time_decay': 1.0}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'RS18SS42000000000000002233', 'derived_anchor_score': 0.55, 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_explanation': 'Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.', 'derived_anchor_original_score': 0.0781, 'suppression_reason': None, 'upstream_funding_edge': {'edge_type': 'SENT_TO', 'amount': 18500.0, 'transaction_count': 2, 'flow_concentration': 0.910881, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12', 'time_decay': 1.0}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 18500.0, 'flow_materiality_weight': 0.86, 'concentration': 0.9109, 'time_decay': 1.0, 'directional_multiplier': 1.05}, {'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 21000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}, {'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}]`
- `final score contribution`: `[('UPSTREAM_FUNDING_OF_DERIVED_SANCTIONS_PROXY', 0.38), ('PROXY_CHAIN_FUNDING', 0.08), ('DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1), ('ABNORMAL_VALUE_TO_NEW_COUNTERPARTY', 0.08)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.2002`
- `risk_score`: `0.6800`
- `sanctions_evasion_score`: `0.6800`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 18500.0, 'flow_materiality_weight': 0.86, 'concentration': 0.9109, 'time_decay': 1.0, 'directional_multiplier': 1.05}`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 21000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 26000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.68,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Beneficiary directly funded an account that was already proven offline to behave like a sanctions proxy through OUTBOUND_2_HOP_TO_SANCTIONED evidence.",
  "evidence": [
    {
      "reason_code": "UPSTREAM_FUNDING_OF_DERIVED_SANCTIONS_PROXY",
      "severity": "MEDIUM",
      "score_contribution": 0.38,
      "path": [
        {
          "node_key": "RS29SS42000000000000002244",
          "node_type": "IBAN"
        },
        {
          "amount": 18500.0,
          "edge_to": "RS18SS42000000000000002233",
          "node_key": "RS18SS42000000000000002233",
          "edge_from": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.96,
          "first_seen": "2026-06-06",
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.910881,
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.05,
          "incoming_concentration": 0.586836,
          "outgoing_concentration": 0.910881,
          "flow_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0781
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Beneficiary directly funded an account that was already proven offline to behave like a sanctions proxy through OUTBOUND_2_HOP_TO_SANCTIONED evidence.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 20310.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 18500.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 0.910881,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "largest_incoming_edge": {},
        "account_age_days": 301,
        "path_edge_factors": [
          {
            "node_key": "RS18SS42000000000000002233",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0781,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "SENT_TO",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "PROXY_CHAIN_FUNDING",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "node_key": "RS29SS42000000000000002244",
          "node_type": "IBAN"
        },
        {
          "amount": 18500.0,
          "edge_to": "RS18SS42000000000000002233",
          "node_key": "RS18SS42000000000000002233",
          "edge_from": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.96,
          "first_seen": "2026-06-06",
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.910881,
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.05,
          "incoming_concentration": 0.586836,
          "outgoing_concentration": 0.910881,
          "flow_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0781
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Funding a derived sanctions-proxy account strengthens the proxy-network evasion hypothesis.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 20310.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 18500.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 0.910881,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "largest_incoming_edge": {},
        "account_age_days": 301,
        "path_edge_factors": [
          {
            "node_key": "RS18SS42000000000000002233",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0781,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "SENT_TO",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "node_key": "RS29SS42000000000000002244",
          "node_type": "IBAN"
        },
        {
          "amount": 18500.0,
          "edge_to": "RS18SS42000000000000002233",
          "node_key": "RS18SS42000000000000002233",
          "edge_from": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.96,
          "first_seen": "2026-06-06",
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.910881,
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.05,
          "incoming_concentration": 0.586836,
          "outgoing_concentration": 0.910881,
          "flow_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0781
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "The immediate counterparty was precomputed offline as a derived sanctions-risk anchor before runtime lookup.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 20310.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 18500.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 0.910881,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "largest_incoming_edge": {},
        "account_age_days": 301,
        "path_edge_factors": [
          {
            "node_key": "RS18SS42000000000000002233",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0781,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "SENT_TO",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "RS29SS42000000000000002244",
          "node_type": "IBAN"
        },
        {
          "amount": 18500.0,
          "edge_to": "RS18SS42000000000000002233",
          "node_key": "RS18SS42000000000000002233",
          "edge_from": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.96,
          "first_seen": "2026-06-06",
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.910881,
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.05,
          "incoming_concentration": 0.586836,
          "outgoing_concentration": 0.910881,
          "flow_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0781
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A high share of incoming or outgoing value concentrates through one account relationship, which is consistent with proxy routing.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 20310.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 18500.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 0.910881,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "largest_incoming_edge": {},
        "account_age_days": 301,
        "path_edge_factors": [
          {
            "node_key": "RS18SS42000000000000002233",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0781,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "SENT_TO",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "node_key": "RS29SS42000000000000002244",
          "node_type": "IBAN"
        },
        {
          "amount": 18500.0,
          "edge_to": "RS18SS42000000000000002233",
          "node_key": "RS18SS42000000000000002233",
          "edge_from": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.96,
          "first_seen": "2026-06-06",
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.910881,
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.05,
          "incoming_concentration": 0.586836,
          "outgoing_concentration": 0.910881,
          "flow_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0781
        },
        {
          "amount": 21000.0,
          "edge_to": "RS16SS42000000000000002231",
          "node_key": "RS16SS42000000000000002231",
          "edge_from": "RS18SS42000000000000002233",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.97,
          "first_seen": "2026-06-05",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 26000.0,
          "edge_to": "RS17SS42000000000000002232",
          "node_key": "RS17SS42000000000000002232",
          "edge_from": "RS16SS42000000000000002231",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.98,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A large recent transfer to a new counterparty increases concern.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": true,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 20310.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 18500.0,
        "largest_outgoing_tx_count": 2,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 0.910881,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS18SS42000000000000002233",
          "source": "RS29SS42000000000000002244",
          "edge_type": "SENT_TO",
          "amount": 18500.0,
          "transaction_count": 2,
          "average_transaction_value": 9250.0,
          "first_seen": "2026-06-06",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 20310.0,
          "receiver_total_incoming_amount": 31525.0,
          "outgoing_concentration": 0.9108813392417529,
          "incoming_concentration": 0.5868358445678034
        },
        "largest_incoming_edge": {},
        "account_age_days": 301,
        "path_edge_factors": [
          {
            "node_key": "RS18SS42000000000000002233",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS16SS42000000000000002231",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 21000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS17SS42000000000000002232",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 26000.0,
            "transaction_count": 2,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS18SS42000000000000002233",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0781,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "SENT_TO",
            "amount": 18500.0,
            "transaction_count": 2,
            "flow_concentration": 0.910881,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    }
  ]
}
```

## Derived anchor precompute: tiny upstream funding suppressed

Scenario source: `tiny_upstream_funding_suppressed` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

A tiny payment into an otherwise suspicious downstream shell chain should remain suppressed. Derived-anchor propagation should not rescue dust-like funding.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `DERIVED_RISK_PROPAGATION_SUPPRESSED`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `DERIVED_RISK_PROPAGATION_SUPPRESSED, PROXY_ACCOUNT_BEHAVIOR, ABNORMAL_VALUE_TO_NEW_COUNTERPARTY`

**Expected evidence package**

```json
[
  {
    "reason_code": "DERIVED_RISK_PROPAGATION_SUPPRESSED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "RS33SS42000000000000002248",
    "to_node_key": "RS34SS42000000000000002249",
    "edge_type": "SENT_TO",
    "total_amount": 16000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "RS34SS42000000000000002249",
    "to_node_key": "RS35SS42000000000000002250",
    "edge_type": "SENT_TO",
    "total_amount": 15000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-07",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "RS32SS42000000000000002247",
    "to_node_key": "RS33SS42000000000000002248",
    "edge_type": "SENT_TO",
    "total_amount": 35.0,
    "transaction_count": 1,
    "first_seen": "2026-06-07",
    "last_seen": "2026-06-12",
    "confidence": 0.78
  },
  {
    "from_node_key": "PERSON:s42:derived-tiny-owner:0996",
    "to_node_key": "RS32SS42000000000000002247",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-08-17",
    "last_seen": "2026-06-11",
    "confidence": 0.99
  },
  {
    "from_node_key": "COMPANY:s42:derived-tiny-mateja-company:0692",
    "to_node_key": "RS33SS42000000000000002248",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2026-03-05",
    "last_seen": "2026-06-11",
    "confidence": 0.99
  },
  {
    "from_node_key": "PERSON:s42:derived-tiny-milica-owner:0997",
    "to_node_key": "RS34SS42000000000000002249",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-11-25",
    "last_seen": "2026-06-11",
    "confidence": 0.99
  },
  {
    "from_node_key": "PERSON:s42:derived-tiny-sanctioned-owner:0998",
    "to_node_key": "RS35SS42000000000000002250",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-07-08",
    "last_seen": "2026-06-09",
    "confidence": 1.0
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "RS32SS42000000000000002247",
    "node_type": "IBAN",
    "display_name": "RS32SS42000000000000002247",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS33SS42000000000000002248",
    "node_type": "IBAN",
    "display_name": "RS33SS42000000000000002248",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS34SS42000000000000002249",
    "node_type": "IBAN",
    "display_name": "RS34SS42000000000000002249",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS35SS42000000000000002250",
    "node_type": "IBAN",
    "display_name": "RS35SS42000000000000002250",
    "country": "rs",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "PERSON:s42:derived-tiny-owner:0996",
    "node_type": "PERSON",
    "display_name": "Jonas Ilic",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "COMPANY:s42:derived-tiny-mateja-company:0692",
    "node_type": "COMPANY",
    "display_name": "Juniper Trading FZE",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:derived-tiny-milica-owner:0997",
    "node_type": "PERSON",
    "display_name": "Marta Rossi",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:derived-tiny-sanctioned-owner:0998",
    "node_type": "PERSON",
    "display_name": "Samir Belov",
    "country": "rs",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `DERIVED_RISK_PROPAGATION_SUPPRESSED`
- `transaction pattern evidence`: `{'has_structuring': False, 'has_high_concentration': False, 'small_inbound_counterparty_count': 0, 'small_inbound_total_amount': 0.0, 'small_inbound_tx_count': 0, 'small_inbound_window_days': None, 'total_incoming_amount': 0.0, 'total_outgoing_amount': 35.0, 'pass_through_ratio': 0.0, 'largest_outgoing_amount': 35.0, 'largest_outgoing_tx_count': 1, 'largest_incoming_amount': 0.0, 'largest_incoming_tx_count': 0, 'max_outgoing_concentration': 1.0, 'max_incoming_concentration': 0.0, 'largest_outgoing_edge': {'counterparty': 'RS33SS42000000000000002248', 'source': 'RS32SS42000000000000002247', 'edge_type': 'SENT_TO', 'amount': 35.0, 'transaction_count': 1, 'average_transaction_value': 35.0, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12', 'sender_total_outgoing_amount': 35.0, 'receiver_total_incoming_amount': 35.0, 'outgoing_concentration': 1.0, 'incoming_concentration': 1.0}, 'largest_incoming_edge': {}, 'account_age_days': 301, 'path_edge_factors': [{'node_key': 'RS33SS42000000000000002248', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 35.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.335, 'directional_multiplier': 1.05, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12'}, {'node_key': 'RS34SS42000000000000002249', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 16000.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12'}, {'node_key': 'RS35SS42000000000000002250', 'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 15000.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.86, 'directional_multiplier': 1.05, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12'}], 'derived_anchor_context': {'derived_anchor_node': 'RS33SS42000000000000002248', 'derived_anchor_score': 0.55, 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_explanation': 'Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.', 'derived_anchor_original_score': 0.075, 'suppression_reason': 'LOW_MATERIALITY_OR_STALE', 'upstream_funding_edge': {'edge_type': 'SENT_TO', 'amount': 35.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.335, 'directional_multiplier': 1.05, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12', 'time_decay': 1.0}}}`
- `derived anchor explanation`: `{'derived_anchor_node': 'RS33SS42000000000000002248', 'derived_anchor_score': 0.55, 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_explanation': 'Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.', 'derived_anchor_original_score': 0.075, 'suppression_reason': 'LOW_MATERIALITY_OR_STALE', 'upstream_funding_edge': {'edge_type': 'SENT_TO', 'amount': 35.0, 'transaction_count': 1, 'flow_concentration': 1.0, 'flow_materiality_weight': 0.335, 'directional_multiplier': 1.05, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12', 'time_decay': 1.0}}`
- `concentration/materiality evidence`: `[{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 35.0, 'flow_materiality_weight': 0.335, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}, {'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 16000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}, {'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 15000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}]`
- `final score contribution`: `[('DERIVED_RISK_PROPAGATION_SUPPRESSED', 0.08), ('PROXY_ACCOUNT_BEHAVIOR', 0.1), ('ABNORMAL_VALUE_TO_NEW_COUNTERPARTY', 0.08)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0290`
- `risk_score`: `0.2600`
- `sanctions_evasion_score`: `0.2600`
- `discounts or uplifts`: `none`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 35.0, 'flow_materiality_weight': 0.335, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 16000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`
- `{'edge_type': 'SENT_TO', 'semantic_flow': 'outbound_to_anchor', 'amount': 15000.0, 'flow_materiality_weight': 0.86, 'concentration': 1.0, 'time_decay': 1.0, 'directional_multiplier': 1.05}`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.26,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Upstream funding reached a derived sanctions-proxy account, but the second-pass propagation was suppressed because low materiality or stale.",
  "evidence": [
    {
      "reason_code": "DERIVED_RISK_PROPAGATION_SUPPRESSED",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "node_key": "RS32SS42000000000000002247",
          "node_type": "IBAN"
        },
        {
          "amount": 35.0,
          "edge_to": "RS33SS42000000000000002248",
          "node_key": "RS33SS42000000000000002248",
          "edge_from": "RS32SS42000000000000002247",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.78,
          "first_seen": "2026-06-07",
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "derived_anchor_node": "RS33SS42000000000000002248",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.335,
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "derived_anchor_original_score": 0.075
        },
        {
          "amount": 16000.0,
          "edge_to": "RS34SS42000000000000002249",
          "node_key": "RS34SS42000000000000002249",
          "edge_from": "RS33SS42000000000000002248",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 15000.0,
          "edge_to": "RS35SS42000000000000002250",
          "node_key": "RS35SS42000000000000002250",
          "edge_from": "RS34SS42000000000000002249",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.96,
          "first_seen": "2026-06-07",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Upstream funding reached a derived sanctions-proxy account, but the second-pass propagation was suppressed because low materiality or stale.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": false,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 35.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 35.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS33SS42000000000000002248",
          "source": "RS32SS42000000000000002247",
          "edge_type": "SENT_TO",
          "amount": 35.0,
          "transaction_count": 1,
          "average_transaction_value": 35.0,
          "first_seen": "2026-06-07",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 35.0,
          "receiver_total_incoming_amount": 35.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 301,
        "path_edge_factors": [
          {
            "node_key": "RS33SS42000000000000002248",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 35.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.335,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS34SS42000000000000002249",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 16000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS35SS42000000000000002250",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 15000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS33SS42000000000000002248",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.075,
          "suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "upstream_funding_edge": {
            "edge_type": "SENT_TO",
            "amount": 35.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.335,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "node_key": "RS32SS42000000000000002247",
          "node_type": "IBAN"
        },
        {
          "amount": 35.0,
          "edge_to": "RS33SS42000000000000002248",
          "node_key": "RS33SS42000000000000002248",
          "edge_from": "RS32SS42000000000000002247",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.78,
          "first_seen": "2026-06-07",
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "derived_anchor_node": "RS33SS42000000000000002248",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.335,
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "derived_anchor_original_score": 0.075
        },
        {
          "amount": 16000.0,
          "edge_to": "RS34SS42000000000000002249",
          "node_key": "RS34SS42000000000000002249",
          "edge_from": "RS33SS42000000000000002248",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 15000.0,
          "edge_to": "RS35SS42000000000000002250",
          "node_key": "RS35SS42000000000000002250",
          "edge_from": "RS34SS42000000000000002249",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.96,
          "first_seen": "2026-06-07",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "Intermediary or pass-through account behavior increases sanctions-evasion concern.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": false,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 35.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 35.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS33SS42000000000000002248",
          "source": "RS32SS42000000000000002247",
          "edge_type": "SENT_TO",
          "amount": 35.0,
          "transaction_count": 1,
          "average_transaction_value": 35.0,
          "first_seen": "2026-06-07",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 35.0,
          "receiver_total_incoming_amount": 35.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 301,
        "path_edge_factors": [
          {
            "node_key": "RS33SS42000000000000002248",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 35.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.335,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS34SS42000000000000002249",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 16000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS35SS42000000000000002250",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 15000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS33SS42000000000000002248",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.075,
          "suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "upstream_funding_edge": {
            "edge_type": "SENT_TO",
            "amount": 35.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.335,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "node_key": "RS32SS42000000000000002247",
          "node_type": "IBAN"
        },
        {
          "amount": 35.0,
          "edge_to": "RS33SS42000000000000002248",
          "node_key": "RS33SS42000000000000002248",
          "edge_from": "RS32SS42000000000000002247",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.78,
          "first_seen": "2026-06-07",
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "derived_anchor_node": "RS33SS42000000000000002248",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.335,
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "derived_anchor_original_score": 0.075
        },
        {
          "amount": 16000.0,
          "edge_to": "RS34SS42000000000000002249",
          "node_key": "RS34SS42000000000000002249",
          "edge_from": "RS33SS42000000000000002248",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        },
        {
          "amount": 15000.0,
          "edge_to": "RS35SS42000000000000002250",
          "node_key": "RS35SS42000000000000002250",
          "edge_from": "RS34SS42000000000000002249",
          "edge_type": "SENT_TO",
          "last_seen": "2026-06-12",
          "node_type": "IBAN",
          "confidence": 0.96,
          "first_seen": "2026-06-07",
          "risk_level": "SANCTIONED",
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "directional_multiplier": 1.05,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "flow_materiality_weight": 0.86
        }
      ],
      "explanation": "A large recent transfer to a new counterparty increases concern.",
      "decision_factors": {
        "has_structuring": false,
        "has_high_concentration": false,
        "small_inbound_counterparty_count": 0,
        "small_inbound_total_amount": 0.0,
        "small_inbound_tx_count": 0,
        "small_inbound_window_days": null,
        "total_incoming_amount": 0.0,
        "total_outgoing_amount": 35.0,
        "pass_through_ratio": 0.0,
        "largest_outgoing_amount": 35.0,
        "largest_outgoing_tx_count": 1,
        "largest_incoming_amount": 0.0,
        "largest_incoming_tx_count": 0,
        "max_outgoing_concentration": 1.0,
        "max_incoming_concentration": 0.0,
        "largest_outgoing_edge": {
          "counterparty": "RS33SS42000000000000002248",
          "source": "RS32SS42000000000000002247",
          "edge_type": "SENT_TO",
          "amount": 35.0,
          "transaction_count": 1,
          "average_transaction_value": 35.0,
          "first_seen": "2026-06-07",
          "last_seen": "2026-06-12",
          "sender_total_outgoing_amount": 35.0,
          "receiver_total_incoming_amount": 35.0,
          "outgoing_concentration": 1.0,
          "incoming_concentration": 1.0
        },
        "largest_incoming_edge": {},
        "account_age_days": 301,
        "path_edge_factors": [
          {
            "node_key": "RS33SS42000000000000002248",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 35.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.335,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS34SS42000000000000002249",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 16000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "RS35SS42000000000000002250",
            "edge_type": "SENT_TO",
            "semantic_flow": "outbound_to_anchor",
            "amount": 15000.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.86,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          }
        ],
        "derived_anchor_context": {
          "derived_anchor_node": "RS33SS42000000000000002248",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound payment path to a sanctioned account created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.075,
          "suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "upstream_funding_edge": {
            "edge_type": "SENT_TO",
            "amount": 35.0,
            "transaction_count": 1,
            "flow_concentration": 1.0,
            "flow_materiality_weight": 0.335,
            "directional_multiplier": 1.05,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    }
  ]
}
```

## Derived anchor precompute: hub-crossing upstream funding suppressed

Scenario source: `hub_upstream_funding_suppressed` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

Funding that crosses a bank hub before reaching the shell/proxy chain should remain out of scope for the second pass because the payer is not a direct upstream funder of the derived anchor.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `NO_EXPOSURE_INDEX_ENTRY`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `NO_EXPOSURE_INDEX_ENTRY`

**Expected evidence package**

```json
[
  {
    "reason_code": "NO_EXPOSURE_INDEX_ENTRY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "RS36SS42000000000000002251",
    "to_node_key": "RS37SS42000000000000002252",
    "edge_type": "SENT_TO",
    "total_amount": 21000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-04",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "RS37SS42000000000000002252",
    "to_node_key": "RS38SS42000000000000002253",
    "edge_type": "SENT_TO",
    "total_amount": 20500.0,
    "transaction_count": 2,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "PERSON:s42:derived-hub-owner:0999",
    "to_node_key": "RS36SS42000000000000002251",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-08-17",
    "last_seen": "2026-06-11",
    "confidence": 0.99
  },
  {
    "from_node_key": "BANK:s42:derived-hub:000",
    "to_node_key": "RS37SS42000000000000002252",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2024-07-13",
    "last_seen": "2026-06-03",
    "confidence": 0.99
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "RS36SS42000000000000002251",
    "node_type": "IBAN",
    "display_name": "RS36SS42000000000000002251",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS37SS42000000000000002252",
    "node_type": "IBAN",
    "display_name": "RS37SS42000000000000002252",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "RS38SS42000000000000002253",
    "node_type": "IBAN",
    "display_name": "RS38SS42000000000000002253",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:derived-hub-owner:0999",
    "node_type": "PERSON",
    "display_name": "Nina Schmidt",
    "country": "rs",
    "risk_level": "NONE"
  },
  {
    "node_key": "BANK:s42:derived-hub:000",
    "node_type": "BANK",
    "display_name": "Derived Hub Bank 000",
    "country": "rs",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `NONE`
- `transaction pattern evidence`: `{}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0000`
- `risk_score`: `0.0000`
- `sanctions_evasion_score`: `0.0000`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.0,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "No transaction-graph exposure evidence was found.",
  "evidence": []
}
```

## Derived anchor precompute: high concentration without sanctions path control

Scenario source: `normal_high_concentration_control_no_match` in `transaction_graph_exposure`

**Why this case is suspicious or clean**

High concentration without any sanctioned or derived-anchor path must stay clean.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `NO_EXPOSURE_INDEX_ENTRY`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `NO_EXPOSURE_INDEX_ENTRY`

**Expected evidence package**

```json
[
  {
    "reason_code": "NO_EXPOSURE_INDEX_ENTRY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "AE42SS42000000000000002257",
    "to_node_key": "AE41SS42000000000000002256",
    "edge_type": "SENT_TO",
    "total_amount": 76000.0,
    "transaction_count": 5,
    "first_seen": "2026-06-01",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "AE42SS42000000000000002257",
    "to_node_key": "DE44SS42000000000000002259",
    "edge_type": "SENT_TO",
    "total_amount": 1500.0,
    "transaction_count": 1,
    "first_seen": "2026-05-30",
    "last_seen": "2026-06-11",
    "confidence": 0.8
  },
  {
    "from_node_key": "AE42SS42000000000000002257",
    "to_node_key": "IT43SS42000000000000002258",
    "edge_type": "SENT_TO",
    "total_amount": 1400.0,
    "transaction_count": 1,
    "first_seen": "2026-05-30",
    "last_seen": "2026-06-11",
    "confidence": 0.8
  },
  {
    "from_node_key": "COMPANY:s42:derived-normal-control-company:0694",
    "to_node_key": "AE41SS42000000000000002256",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-11-05",
    "last_seen": "2026-06-10",
    "confidence": 0.99
  },
  {
    "from_node_key": "PERSON:s42:derived-normal-control-sender:1002",
    "to_node_key": "AE42SS42000000000000002257",
    "edge_type": "USES_ACCOUNT",
    "total_amount": 0.0,
    "transaction_count": 1,
    "first_seen": "2025-08-17",
    "last_seen": "2026-06-10",
    "confidence": 0.99
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "AE41SS42000000000000002256",
    "node_type": "IBAN",
    "display_name": "AE41SS42000000000000002256",
    "country": "ae",
    "risk_level": "NONE"
  },
  {
    "node_key": "AE42SS42000000000000002257",
    "node_type": "IBAN",
    "display_name": "AE42SS42000000000000002257",
    "country": "ae",
    "risk_level": "NONE"
  },
  {
    "node_key": "DE44SS42000000000000002259",
    "node_type": "IBAN",
    "display_name": "DE44SS42000000000000002259",
    "country": "de",
    "risk_level": "NONE"
  },
  {
    "node_key": "IT43SS42000000000000002258",
    "node_type": "IBAN",
    "display_name": "IT43SS42000000000000002258",
    "country": "it",
    "risk_level": "NONE"
  },
  {
    "node_key": "COMPANY:s42:derived-normal-control-company:0694",
    "node_type": "COMPANY",
    "display_name": "Lumen Advisory Ltd",
    "country": "ae",
    "risk_level": "NONE"
  },
  {
    "node_key": "PERSON:s42:derived-normal-control-sender:1002",
    "node_type": "PERSON",
    "display_name": "Mila Costa",
    "country": "ae",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `NONE`
- `transaction pattern evidence`: `{}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0000`
- `risk_score`: `0.0000`
- `sanctions_evasion_score`: `0.0000`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.0,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "No transaction-graph exposure evidence was found.",
  "evidence": []
}
```

# Crypto Derived Risk Anchor Precompute

## Crypto derived anchor: Milica routes directly to sanctioned wallet

Scenario source: `crypto_derived_anchor_milica_to_sanctioned` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

Milica wallet sends material recent value directly to a sanctioned wallet. That makes it a strong derived-risk anchor candidate for the second offline pass.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `OUTBOUND_1_HOP_TO_SANCTIONED, CRYPTO_DERIVED_RISK_ANCHOR`
- `observed decision`: `REVIEW`
- `observed reason codes`: `OUTBOUND_1_HOP_TO_SANCTIONED, CRYPTO_DERIVED_RISK_ANCHOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "CRYPTO_DERIVED_RISK_ANCHOR",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000261",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000262",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 26000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-03",
    "last_seen": "2026-06-12",
    "confidence": 0.97
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000261",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 21000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000272",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 18500.0,
    "transaction_count": 2,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000271",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1820.0,
    "transaction_count": 21,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000270",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1760.0,
    "transaction_count": 20,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000269",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1700.0,
    "transaction_count": 19,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000268",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1640.0,
    "transaction_count": 18,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000267",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1580.0,
    "transaction_count": 17,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000266",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1520.0,
    "transaction_count": 16,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000265",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1460.0,
    "transaction_count": 15,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000264",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1400.0,
    "transaction_count": 14,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000261",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000261",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-milica-wallet:0261",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000262",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000262",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-sanctioned-wallet:0262",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000263",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000263",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-wallet:0263",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000272",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000272",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-andrija-wallet:0272",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000271",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000271",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-07:0271",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000270",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000270",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-06:0270",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000269",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000269",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-05:0269",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000268",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000268",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-04:0268",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000267",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000267",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-03:0267",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000266",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000266",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-02:0266",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000265",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000265",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-01:0265",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000264",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000264",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-00:0264",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `OUTBOUND_1_HOP_TO_SANCTIONED`
- `transaction pattern evidence`: `{'path_edge_factors': [{'node_key': 'ETH:0x4200000000000000000000000000000000000262', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'transaction_count': 2, 'average_transaction_value': 13000.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12'}], 'chain': 'ETH', 'asset': 'ETH', 'amount_usd': 6200.0, 'guard_hints': [], 'derived_anchor_context': {'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000261', 'derived_anchor_reason_code': 'OUTBOUND_1_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.7, 'derived_anchor_explanation': 'Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass.'}}`
- `derived anchor explanation`: `{'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000261', 'derived_anchor_reason_code': 'OUTBOUND_1_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.7, 'derived_anchor_explanation': 'Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass.'}`
- `concentration/materiality evidence`: `[{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}]`
- `final score contribution`: `[('OUTBOUND_1_HOP_TO_SANCTIONED', 0.82), ('CRYPTO_DERIVED_RISK_ANCHOR', 0.04)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.4175`
- `risk_score`: `0.8600`
- `sanctions_evasion_score`: `0.8600`
- `discounts or uplifts`: `none`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.86,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Wallet is one hop away from a sanctioned counterparty through an outbound payment path.",
  "evidence": [
    {
      "reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
      "severity": "HIGH",
      "score_contribution": 0.82,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Wallet is one hop away from a sanctioned counterparty through an outbound payment path.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "ETH",
        "amount_usd": 6200.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000261",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    },
    {
      "reason_code": "CRYPTO_DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "This wallet itself qualifies as a derived crypto sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "ETH",
        "amount_usd": 6200.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000261",
          "derived_anchor_reason_code": "OUTBOUND_1_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.7,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    }
  ]
}
```

## Crypto derived anchor: Mateja funds derived anchor

Scenario source: `crypto_mateja_to_derived_anchor` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

Mateja wallet materially funds Milica, and Milica already routes directly to a sanctioned wallet. Mateja should remain a normal REVIEW while also becoming a crypto derived-risk anchor.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `OUTBOUND_2_HOP_TO_SANCTIONED, CRYPTO_DERIVED_RISK_ANCHOR`
- `observed decision`: `REVIEW`
- `observed reason codes`: `OUTBOUND_2_HOP_TO_SANCTIONED, CRYPTO_DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR, ABNORMAL_VALUE_TO_NEW_COUNTERPARTY`

**Expected evidence package**

```json
[
  {
    "reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "CRYPTO_DERIVED_RISK_ANCHOR",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000261",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000262",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 26000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-03",
    "last_seen": "2026-06-12",
    "confidence": 0.97
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000261",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 21000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000272",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 18500.0,
    "transaction_count": 2,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000271",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1820.0,
    "transaction_count": 21,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000270",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1760.0,
    "transaction_count": 20,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000269",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1700.0,
    "transaction_count": 19,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000268",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1640.0,
    "transaction_count": 18,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000267",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1580.0,
    "transaction_count": 17,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000266",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1520.0,
    "transaction_count": 16,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000265",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1460.0,
    "transaction_count": 15,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000264",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1400.0,
    "transaction_count": 14,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000272",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000274",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1040.0,
    "transaction_count": 1,
    "first_seen": "2026-06-01",
    "last_seen": "2026-06-10",
    "confidence": 0.79
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000263",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000263",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-wallet:0263",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000261",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000261",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-milica-wallet:0261",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000262",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000262",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-sanctioned-wallet:0262",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000272",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000272",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-andrija-wallet:0272",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000271",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000271",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-07:0271",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000270",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000270",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-06:0270",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000269",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000269",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-05:0269",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000268",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000268",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-04:0268",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000267",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000267",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-03:0267",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000266",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000266",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-02:0266",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000265",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000265",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-01:0265",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000264",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000264",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-00:0264",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000274",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000274",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-andrija-side-00-01:0274",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `OUTBOUND_2_HOP_TO_SANCTIONED`
- `transaction pattern evidence`: `{'path_edge_factors': [{'node_key': 'ETH:0x4200000000000000000000000000000000000261', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 21000.0, 'transaction_count': 2, 'average_transaction_value': 10500.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12'}, {'node_key': 'ETH:0x4200000000000000000000000000000000000262', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'transaction_count': 2, 'average_transaction_value': 13000.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12'}], 'chain': 'ETH', 'asset': 'USDT', 'amount_usd': 5100.0, 'guard_hints': [], 'derived_anchor_context': {'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000263', 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass.'}}`
- `derived anchor explanation`: `{'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000263', 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass.'}`
- `concentration/materiality evidence`: `[{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 21000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}, {'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}]`
- `final score contribution`: `[('OUTBOUND_2_HOP_TO_SANCTIONED', 0.62), ('CRYPTO_DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1), ('ABNORMAL_VALUE_TO_NEW_COUNTERPARTY', 0.08)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0986`
- `risk_score`: `0.8400`
- `sanctions_evasion_score`: `0.8400`
- `discounts or uplifts`: `none`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 21000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.84,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Wallet is connected to a sanctioned counterparty through a two-hop outbound route.",
  "evidence": [
    {
      "reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
      "severity": "HIGH",
      "score_contribution": 0.62,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Wallet is connected to a sanctioned counterparty through a two-hop outbound route.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDT",
        "amount_usd": 5100.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    },
    {
      "reason_code": "CRYPTO_DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "This wallet itself qualifies as a derived crypto sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDT",
        "amount_usd": 5100.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Intermediary routing, bridge usage, or pass-through behavior increases sanctions-evasion concern.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDT",
        "amount_usd": 5100.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    },
    {
      "reason_code": "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "A large recent transfer to a newly observed counterparty increases concern.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDT",
        "amount_usd": 5100.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    }
  ]
}
```

## Crypto derived anchor: Andrija funds derived proxy

Scenario source: `crypto_andrija_funds_derived_proxy` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

Andrija has no direct 3-hop runtime traversal. He becomes reviewable only because the offline second pass recognized Mateja as a derived crypto proxy and then evaluated Andrija's direct funding into that proxy wallet.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY, CRYPTO_PROXY_CHAIN_FUNDING`
- `observed decision`: `REVIEW`
- `observed reason codes`: `UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY, CRYPTO_PROXY_CHAIN_FUNDING, CRYPTO_DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR, ABNORMAL_VALUE_TO_NEW_COUNTERPARTY`

**Expected evidence package**

```json
[
  {
    "reason_code": "UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "CRYPTO_PROXY_CHAIN_FUNDING",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000261",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000262",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 26000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-03",
    "last_seen": "2026-06-12",
    "confidence": 0.97
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000261",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 21000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000272",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 18500.0,
    "transaction_count": 2,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000271",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1820.0,
    "transaction_count": 21,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000270",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1760.0,
    "transaction_count": 20,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000269",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1700.0,
    "transaction_count": 19,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000268",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1640.0,
    "transaction_count": 18,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000267",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1580.0,
    "transaction_count": 17,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000266",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1520.0,
    "transaction_count": 16,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000265",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1460.0,
    "transaction_count": 15,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-11",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000264",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000263",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1400.0,
    "transaction_count": 14,
    "first_seen": "2026-05-28",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000272",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000274",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1040.0,
    "transaction_count": 1,
    "first_seen": "2026-06-01",
    "last_seen": "2026-06-10",
    "confidence": 0.79
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000272",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000272",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-andrija-wallet:0272",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000263",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000263",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-wallet:0263",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000261",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000261",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-milica-wallet:0261",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000262",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000262",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-sanctioned-wallet:0262",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000271",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000271",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-07:0271",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000270",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000270",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-06:0270",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000269",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000269",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-05:0269",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000268",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000268",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-04:0268",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000267",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000267",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-03:0267",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000266",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000266",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-02:0266",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000265",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000265",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-01:0265",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000264",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000264",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-mateja-feeder-00-00:0264",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000274",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000274",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-andrija-side-00-01:0274",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY`
- `transaction pattern evidence`: `{'path_edge_factors': [{'node_key': 'ETH:0x4200000000000000000000000000000000000263', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 18500.0, 'transaction_count': 2, 'average_transaction_value': 9250.0, 'flow_concentration': 0.905088, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12'}, {'node_key': 'ETH:0x4200000000000000000000000000000000000261', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 21000.0, 'transaction_count': 2, 'average_transaction_value': 10500.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12'}, {'node_key': 'ETH:0x4200000000000000000000000000000000000262', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'transaction_count': 2, 'average_transaction_value': 13000.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-03', 'last_seen': '2026-06-12'}], 'chain': 'ETH', 'asset': 'USDC', 'amount_usd': 4300.0, 'guard_hints': [], 'derived_anchor_context': {'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000263', 'derived_anchor_score': 0.55, 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_explanation': 'Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.', 'derived_anchor_original_score': 0.0986, 'suppression_reason': None, 'upstream_funding_edge': {'edge_type': 'TRANSFERRED_TO', 'amount_usd': 18500.0, 'transaction_count': 2, 'average_transaction_value': 9250.0, 'flow_concentration': 0.905088, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'chain': 'ETH', 'asset': None, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12', 'time_decay': 1.0}}}`
- `derived anchor explanation`: `{'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000263', 'derived_anchor_score': 0.55, 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_explanation': 'Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.', 'derived_anchor_original_score': 0.0986, 'suppression_reason': None, 'upstream_funding_edge': {'edge_type': 'TRANSFERRED_TO', 'amount_usd': 18500.0, 'transaction_count': 2, 'average_transaction_value': 9250.0, 'flow_concentration': 0.905088, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'chain': 'ETH', 'asset': None, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12', 'time_decay': 1.0}}`
- `concentration/materiality evidence`: `[{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 18500.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 0.9051, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}, {'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 21000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}, {'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}]`
- `final score contribution`: `[('UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY', 0.38), ('CRYPTO_PROXY_CHAIN_FUNDING', 0.08), ('CRYPTO_DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1), ('ABNORMAL_VALUE_TO_NEW_COUNTERPARTY', 0.08)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.2249`
- `risk_score`: `0.6800`
- `sanctions_evasion_score`: `0.6800`
- `discounts or uplifts`: `none`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 18500.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 0.9051, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 21000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 26000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.68,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Wallet directly funded a wallet that was already proven offline to behave like a crypto sanctions proxy through OUTBOUND_2_HOP_TO_SANCTIONED evidence.",
  "evidence": [
    {
      "reason_code": "UPSTREAM_FUNDING_OF_DERIVED_CRYPTO_PROXY",
      "severity": "MEDIUM",
      "score_contribution": 0.38,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000272",
          "node_key": "ETH:0x4200000000000000000000000000000000000272",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "edge_to": "ETH:0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "edge_from": "ETH:0x4200000000000000000000000000000000000272",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "total_usd_value": 18500.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.905088,
          "concentration_score": 1.0,
          "derived_anchor_node": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.1,
          "incoming_concentration": 0.589547,
          "outgoing_concentration": 0.905088,
          "average_transaction_value": 9250.0,
          "crypto_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0986
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Wallet directly funded a wallet that was already proven offline to behave like a crypto sanctions proxy through OUTBOUND_2_HOP_TO_SANCTIONED evidence.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000263",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDC",
        "amount_usd": 4300.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0986,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "TRANSFERRED_TO",
            "amount_usd": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "chain": "ETH",
            "asset": null,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "CRYPTO_PROXY_CHAIN_FUNDING",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000272",
          "node_key": "ETH:0x4200000000000000000000000000000000000272",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "edge_to": "ETH:0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "edge_from": "ETH:0x4200000000000000000000000000000000000272",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "total_usd_value": 18500.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.905088,
          "concentration_score": 1.0,
          "derived_anchor_node": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.1,
          "incoming_concentration": 0.589547,
          "outgoing_concentration": 0.905088,
          "average_transaction_value": 9250.0,
          "crypto_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0986
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Funding a derived crypto sanctions-proxy wallet strengthens the proxy-network evasion hypothesis.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000263",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDC",
        "amount_usd": 4300.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0986,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "TRANSFERRED_TO",
            "amount_usd": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "chain": "ETH",
            "asset": null,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "CRYPTO_DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000272",
          "node_key": "ETH:0x4200000000000000000000000000000000000272",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "edge_to": "ETH:0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "edge_from": "ETH:0x4200000000000000000000000000000000000272",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "total_usd_value": 18500.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.905088,
          "concentration_score": 1.0,
          "derived_anchor_node": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.1,
          "incoming_concentration": 0.589547,
          "outgoing_concentration": 0.905088,
          "average_transaction_value": 9250.0,
          "crypto_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0986
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "The immediate counterparty was precomputed offline as a derived crypto sanctions-risk anchor.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000263",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDC",
        "amount_usd": 4300.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0986,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "TRANSFERRED_TO",
            "amount_usd": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "chain": "ETH",
            "asset": null,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000272",
          "node_key": "ETH:0x4200000000000000000000000000000000000272",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "edge_to": "ETH:0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "edge_from": "ETH:0x4200000000000000000000000000000000000272",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "total_usd_value": 18500.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.905088,
          "concentration_score": 1.0,
          "derived_anchor_node": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.1,
          "incoming_concentration": 0.589547,
          "outgoing_concentration": 0.905088,
          "average_transaction_value": 9250.0,
          "crypto_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0986
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Intermediary routing, bridge usage, or pass-through behavior increases sanctions-evasion concern.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000263",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDC",
        "amount_usd": 4300.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0986,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "TRANSFERRED_TO",
            "amount_usd": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "chain": "ETH",
            "asset": null,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000272",
          "node_key": "ETH:0x4200000000000000000000000000000000000272",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000263",
          "edge_to": "ETH:0x4200000000000000000000000000000000000263",
          "node_key": "ETH:0x4200000000000000000000000000000000000263",
          "edge_from": "ETH:0x4200000000000000000000000000000000000272",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "total_usd_value": 18500.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 0.905088,
          "concentration_score": 1.0,
          "derived_anchor_node": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.1,
          "incoming_concentration": 0.589547,
          "outgoing_concentration": 0.905088,
          "average_transaction_value": 9250.0,
          "crypto_materiality_weight": 0.86,
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": null,
          "derived_anchor_original_score": 0.0986
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000261",
          "edge_to": "ETH:0x4200000000000000000000000000000000000261",
          "node_key": "ETH:0x4200000000000000000000000000000000000261",
          "edge_from": "ETH:0x4200000000000000000000000000000000000263",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 21000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 10500.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000262",
          "edge_to": "ETH:0x4200000000000000000000000000000000000262",
          "node_key": "ETH:0x4200000000000000000000000000000000000262",
          "edge_from": "ETH:0x4200000000000000000000000000000000000261",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.97,
          "first_seen": "2026-06-03",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 26000.0,
          "override_allowed": true,
          "transaction_count": 2,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 13000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "A large recent transfer to a newly observed counterparty increases concern.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000263",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000261",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 21000.0,
            "transaction_count": 2,
            "average_transaction_value": 10500.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000262",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 26000.0,
            "transaction_count": 2,
            "average_transaction_value": 13000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-03",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "USDC",
        "amount_usd": 4300.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000263",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0986,
          "suppression_reason": null,
          "upstream_funding_edge": {
            "edge_type": "TRANSFERRED_TO",
            "amount_usd": 18500.0,
            "transaction_count": 2,
            "average_transaction_value": 9250.0,
            "flow_concentration": 0.905088,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "chain": "ETH",
            "asset": null,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    }
  ]
}
```

## Crypto derived anchor: tiny upstream funding suppressed

Scenario source: `crypto_tiny_upstream_funding_suppressed` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

Tiny upstream funding into a downstream proxy chain should remain suppressed even when the downstream wallets connect to sanctions.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED, PROXY_ACCOUNT_BEHAVIOR, ABNORMAL_VALUE_TO_NEW_COUNTERPARTY`

**Expected evidence package**

```json
[
  {
    "reason_code": "CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000275",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000276",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 16000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000277",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000275",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 15000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.95
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000278",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000277",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 12.0,
    "transaction_count": 1,
    "first_seen": "2026-06-07",
    "last_seen": "2026-06-12",
    "confidence": 0.8
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000278",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000278",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-tiny-andrija-wallet:0278",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000277",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000277",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-tiny-mateja-wallet:0277",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000275",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000275",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-tiny-milica-wallet:0275",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000276",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000276",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-tiny-sanctioned-wallet:0276",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED`
- `transaction pattern evidence`: `{'path_edge_factors': [{'node_key': 'ETH:0x4200000000000000000000000000000000000277', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 12.0, 'transaction_count': 1, 'average_transaction_value': 12.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.335, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12'}, {'node_key': 'ETH:0x4200000000000000000000000000000000000275', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 15000.0, 'transaction_count': 1, 'average_transaction_value': 15000.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-06', 'last_seen': '2026-06-12'}, {'node_key': 'ETH:0x4200000000000000000000000000000000000276', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 16000.0, 'transaction_count': 1, 'average_transaction_value': 16000.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'first_seen': '2026-06-05', 'last_seen': '2026-06-12'}], 'chain': 'ETH', 'asset': 'BTC', 'amount_usd': 12.0, 'guard_hints': [], 'derived_anchor_context': {'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000277', 'derived_anchor_score': 0.55, 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_explanation': 'Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.', 'derived_anchor_original_score': 0.0966, 'suppression_reason': 'LOW_MATERIALITY_OR_STALE', 'upstream_funding_edge': {'edge_type': 'TRANSFERRED_TO', 'amount_usd': 12.0, 'transaction_count': 1, 'average_transaction_value': 12.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.335, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'chain': 'ETH', 'asset': None, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12', 'time_decay': 1.0}}}`
- `derived anchor explanation`: `{'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000277', 'derived_anchor_score': 0.55, 'derived_anchor_reason_code': 'OUTBOUND_2_HOP_TO_SANCTIONED', 'derived_anchor_explanation': 'Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.', 'derived_anchor_original_score': 0.0966, 'suppression_reason': 'LOW_MATERIALITY_OR_STALE', 'upstream_funding_edge': {'edge_type': 'TRANSFERRED_TO', 'amount_usd': 12.0, 'transaction_count': 1, 'average_transaction_value': 12.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.335, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1, 'chain': 'ETH', 'asset': None, 'first_seen': '2026-06-07', 'last_seen': '2026-06-12', 'time_decay': 1.0}}`
- `concentration/materiality evidence`: `[{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 12.0, 'crypto_materiality_weight': 0.335, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}, {'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 15000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}, {'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 16000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}]`
- `final score contribution`: `[('CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED', 0.08), ('PROXY_ACCOUNT_BEHAVIOR', 0.1), ('ABNORMAL_VALUE_TO_NEW_COUNTERPARTY', 0.08)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0290`
- `risk_score`: `0.2600`
- `sanctions_evasion_score`: `0.2600`
- `discounts or uplifts`: `none`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 12.0, 'crypto_materiality_weight': 0.335, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 15000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'outbound_to_anchor', 'total_usd_value': 16000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 1.1}`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.26,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Upstream funding reached a derived crypto sanctions-proxy wallet, but second-pass propagation was suppressed because low materiality or stale.",
  "evidence": [
    {
      "reason_code": "CRYPTO_DERIVED_RISK_PROPAGATION_SUPPRESSED",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000278",
          "node_key": "ETH:0x4200000000000000000000000000000000000278",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000277",
          "edge_to": "ETH:0x4200000000000000000000000000000000000277",
          "node_key": "ETH:0x4200000000000000000000000000000000000277",
          "edge_from": "ETH:0x4200000000000000000000000000000000000278",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.8,
          "first_seen": "2026-06-07",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "total_usd_value": 12.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "derived_anchor_node": "ETH:0x4200000000000000000000000000000000000277",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 12.0,
          "crypto_materiality_weight": 0.335,
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "derived_anchor_original_score": 0.0966
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000275",
          "edge_to": "ETH:0x4200000000000000000000000000000000000275",
          "node_key": "ETH:0x4200000000000000000000000000000000000275",
          "edge_from": "ETH:0x4200000000000000000000000000000000000277",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 15000.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 15000.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000276",
          "edge_to": "ETH:0x4200000000000000000000000000000000000276",
          "node_key": "ETH:0x4200000000000000000000000000000000000276",
          "edge_from": "ETH:0x4200000000000000000000000000000000000275",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 16000.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 16000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Upstream funding reached a derived crypto sanctions-proxy wallet, but second-pass propagation was suppressed because low materiality or stale.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000277",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 12.0,
            "transaction_count": 1,
            "average_transaction_value": 12.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.335,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000275",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 15000.0,
            "transaction_count": 1,
            "average_transaction_value": 15000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000276",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 16000.0,
            "transaction_count": 1,
            "average_transaction_value": 16000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "BTC",
        "amount_usd": 12.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000277",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0966,
          "suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "upstream_funding_edge": {
            "edge_type": "TRANSFERRED_TO",
            "amount_usd": 12.0,
            "transaction_count": 1,
            "average_transaction_value": 12.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.335,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "chain": "ETH",
            "asset": null,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000278",
          "node_key": "ETH:0x4200000000000000000000000000000000000278",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000277",
          "edge_to": "ETH:0x4200000000000000000000000000000000000277",
          "node_key": "ETH:0x4200000000000000000000000000000000000277",
          "edge_from": "ETH:0x4200000000000000000000000000000000000278",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.8,
          "first_seen": "2026-06-07",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "total_usd_value": 12.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "derived_anchor_node": "ETH:0x4200000000000000000000000000000000000277",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 12.0,
          "crypto_materiality_weight": 0.335,
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "derived_anchor_original_score": 0.0966
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000275",
          "edge_to": "ETH:0x4200000000000000000000000000000000000275",
          "node_key": "ETH:0x4200000000000000000000000000000000000275",
          "edge_from": "ETH:0x4200000000000000000000000000000000000277",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 15000.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 15000.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000276",
          "edge_to": "ETH:0x4200000000000000000000000000000000000276",
          "node_key": "ETH:0x4200000000000000000000000000000000000276",
          "edge_from": "ETH:0x4200000000000000000000000000000000000275",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 16000.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 16000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Intermediary routing, bridge usage, or pass-through behavior increases sanctions-evasion concern.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000277",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 12.0,
            "transaction_count": 1,
            "average_transaction_value": 12.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.335,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000275",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 15000.0,
            "transaction_count": 1,
            "average_transaction_value": 15000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000276",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 16000.0,
            "transaction_count": 1,
            "average_transaction_value": 16000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "BTC",
        "amount_usd": 12.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000277",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0966,
          "suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "upstream_funding_edge": {
            "edge_type": "TRANSFERRED_TO",
            "amount_usd": 12.0,
            "transaction_count": 1,
            "average_transaction_value": 12.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.335,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "chain": "ETH",
            "asset": null,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    },
    {
      "reason_code": "ABNORMAL_VALUE_TO_NEW_COUNTERPARTY",
      "severity": "LOW",
      "score_contribution": 0.08,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000278",
          "node_key": "ETH:0x4200000000000000000000000000000000000278",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000277",
          "edge_to": "ETH:0x4200000000000000000000000000000000000277",
          "node_key": "ETH:0x4200000000000000000000000000000000000277",
          "edge_from": "ETH:0x4200000000000000000000000000000000000278",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.8,
          "first_seen": "2026-06-07",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "derived_anchor": true,
          "edge_direction": "reverse",
          "total_usd_value": 12.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "derived_anchor_node": "ETH:0x4200000000000000000000000000000000000277",
          "derived_anchor_score": 0.55,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 12.0,
          "crypto_materiality_weight": 0.335,
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "derived_anchor_original_score": 0.0966
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000275",
          "edge_to": "ETH:0x4200000000000000000000000000000000000275",
          "node_key": "ETH:0x4200000000000000000000000000000000000275",
          "edge_from": "ETH:0x4200000000000000000000000000000000000277",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.95,
          "first_seen": "2026-06-06",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 15000.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 15000.0,
          "crypto_materiality_weight": 0.86
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000276",
          "edge_to": "ETH:0x4200000000000000000000000000000000000276",
          "node_key": "ETH:0x4200000000000000000000000000000000000276",
          "edge_from": "ETH:0x4200000000000000000000000000000000000275",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.96,
          "first_seen": "2026-06-05",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "outbound_to_anchor",
          "edge_direction": "reverse",
          "total_usd_value": 16000.0,
          "override_allowed": true,
          "transaction_count": 1,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 1.1,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 16000.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "A large recent transfer to a newly observed counterparty increases concern.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000277",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 12.0,
            "transaction_count": 1,
            "average_transaction_value": 12.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.335,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000275",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 15000.0,
            "transaction_count": 1,
            "average_transaction_value": 15000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-06",
            "last_seen": "2026-06-12"
          },
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000276",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "outbound_to_anchor",
            "total_usd_value": 16000.0,
            "transaction_count": 1,
            "average_transaction_value": 16000.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "first_seen": "2026-06-05",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "BTC",
        "amount_usd": 12.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000277",
          "derived_anchor_score": 0.55,
          "derived_anchor_reason_code": "OUTBOUND_2_HOP_TO_SANCTIONED",
          "derived_anchor_explanation": "Two-hop outbound crypto flow to a sanctioned wallet created a medium-strength derived anchor.",
          "derived_anchor_original_score": 0.0966,
          "suppression_reason": "LOW_MATERIALITY_OR_STALE",
          "upstream_funding_edge": {
            "edge_type": "TRANSFERRED_TO",
            "amount_usd": 12.0,
            "transaction_count": 1,
            "average_transaction_value": 12.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.335,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 1.1,
            "chain": "ETH",
            "asset": null,
            "first_seen": "2026-06-07",
            "last_seen": "2026-06-12",
            "time_decay": 1.0
          }
        }
      }
    }
  ]
}
```

## Crypto derived anchor: exchange upstream funding suppressed

Scenario source: `crypto_exchange_upstream_funding_suppressed` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

An upstream payer that only touches the proxy chain through an exchange hot wallet must stay out of scope for derived-risk propagation.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `NO_EXPOSURE_INDEX_ENTRY`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `NO_EXPOSURE_INDEX_ENTRY`

**Expected evidence package**

```json
[
  {
    "reason_code": "NO_EXPOSURE_INDEX_ENTRY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000279",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000280",
    "edge_type": "DEPOSITED_TO_EXCHANGE",
    "total_usd_value": 22000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-04",
    "last_seen": "2026-06-12",
    "confidence": 0.93
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000280",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000281",
    "edge_type": "WITHDREW_FROM_EXCHANGE",
    "total_usd_value": 21000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.89
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000279",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000279",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-exchange-andrija-wallet:0279",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000280",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000280",
    "node_type": "EXCHANGE_HOT_WALLET",
    "display_name": "EXCHANGE_HOT_WALLET:derived-exchange-hot-wallet:0280",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000281",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000281",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-exchange-mateja-wallet:0281",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `NONE`
- `transaction pattern evidence`: `{}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0000`
- `risk_score`: `0.0000`
- `sanctions_evasion_score`: `0.0000`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.0,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "No crypto exposure evidence was found.",
  "evidence": []
}
```

## Crypto derived anchor: bridge or mixer upstream suppressed

Scenario source: `crypto_bridge_or_mixer_upstream_suppressed` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

An upstream payer that only reaches the downstream proxy chain through a bridge or mixer service boundary must remain suppressed.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `NO_EXPOSURE_INDEX_ENTRY`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `NO_EXPOSURE_INDEX_ENTRY`

**Expected evidence package**

```json
[
  {
    "reason_code": "NO_EXPOSURE_INDEX_ENTRY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000284",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000285",
    "edge_type": "BRIDGED_TO",
    "total_usd_value": 24000.0,
    "transaction_count": 2,
    "first_seen": "2026-06-04",
    "last_seen": "2026-06-12",
    "confidence": 0.88
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000285",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000286",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 23000.0,
    "transaction_count": 1,
    "first_seen": "2026-06-05",
    "last_seen": "2026-06-12",
    "confidence": 0.86
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000284",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000284",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-infra-andrija-wallet:0284",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000285",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000285",
    "node_type": "BRIDGE",
    "display_name": "BRIDGE:derived-infra-service:0285",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000286",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000286",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-infra-mateja-wallet:0286",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `NONE`
- `transaction pattern evidence`: `{}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0000`
- `risk_score`: `0.0000`
- `sanctions_evasion_score`: `0.0000`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.0,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "No crypto exposure evidence was found.",
  "evidence": []
}
```

## Crypto derived anchor: normal high concentration control

Scenario source: `crypto_normal_high_concentration_control_no_match` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

High concentration without any sanctions path must remain a clean control case.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `NO_EXPOSURE_INDEX_ENTRY`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `NO_EXPOSURE_INDEX_ENTRY`

**Expected evidence package**

```json
[
  {
    "reason_code": "NO_EXPOSURE_INDEX_ENTRY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000289",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000290",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 82000.0,
    "transaction_count": 4,
    "first_seen": "2026-06-03",
    "last_seen": "2026-06-12",
    "confidence": 0.96
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000289",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000292",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1700.0,
    "transaction_count": 1,
    "first_seen": "2026-05-30",
    "last_seen": "2026-06-11",
    "confidence": 0.81
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000289",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000291",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 1600.0,
    "transaction_count": 1,
    "first_seen": "2026-05-30",
    "last_seen": "2026-06-11",
    "confidence": 0.81
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000289",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000289",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-control-sender-wallet:0289",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000290",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000290",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-control-receiver-wallet:0290",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000292",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000292",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-control-side-00-01:0292",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000291",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000291",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-control-side-00-00:0291",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `NONE`
- `transaction pattern evidence`: `{}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0000`
- `risk_score`: `0.0000`
- `sanctions_evasion_score`: `0.0000`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.0,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "No crypto exposure evidence was found.",
  "evidence": []
}
```

## Crypto derived anchor: old weak anchor suppressed

Scenario source: `crypto_old_weak_derived_anchor_suppressed` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

Funding into a wallet whose only downstream sanctions relation is old, weak, and dust-like should remain suppressed.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `NO_EXPOSURE_INDEX_ENTRY`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `NO_EXPOSURE_INDEX_ENTRY`

**Expected evidence package**

```json
[
  {
    "reason_code": "NO_EXPOSURE_INDEX_ENTRY",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000293",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000294",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 5200.0,
    "transaction_count": 2,
    "first_seen": "2026-06-06",
    "last_seen": "2026-06-12",
    "confidence": 0.92
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000294",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000295",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 90.0,
    "transaction_count": 1,
    "first_seen": "2025-10-01",
    "last_seen": "2025-10-21",
    "confidence": 0.81
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000293",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000293",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-old-andrija-wallet:0293",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000294",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000294",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-old-mateja-wallet:0294",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000295",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000295",
    "node_type": "WALLET",
    "display_name": "WALLET:derived-old-milica-wallet:0295",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `NONE`
- `transaction pattern evidence`: `{}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0000`
- `risk_score`: `0.0000`
- `sanctions_evasion_score`: `0.0000`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.0,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "No crypto exposure evidence was found.",
  "evidence": []
}
```

# Crypto Wallet Scenarios

## Exchange false-positive suppression

Scenario source: `exchange_contamination_prevented` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

A sanctioned wallet touched a shared exchange hot wallet, but unrelated customers withdrawing later should remain clean.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `HUB_PATH_DISCOUNTED`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `HUB_PATH_DISCOUNTED`

**Expected evidence package**

```json
[
  {
    "reason_code": "HUB_PATH_DISCOUNTED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000001101",
    "to_node_key": "ETH:0x4200000000000000000000000000000000001102",
    "edge_type": "DEPOSITED_TO_EXCHANGE",
    "total_usd_value": 28000.0,
    "transaction_count": 2,
    "first_seen": "2026-05-09",
    "last_seen": "2026-06-11",
    "confidence": 0.92
  },
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000001102",
    "to_node_key": "ETH:0x4200000000000000000000000000000000001103",
    "edge_type": "WITHDREW_FROM_EXCHANGE",
    "total_usd_value": 2600.0,
    "transaction_count": 1,
    "first_seen": "2026-05-14",
    "last_seen": "2026-06-12",
    "confidence": 0.89
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000001103",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000001103",
    "node_type": "WALLET",
    "display_name": "WALLET:exchange-clean-recipient:1103",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000001101",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000001101",
    "node_type": "WALLET",
    "display_name": "WALLET:exchange-risky-source:1101",
    "risk_level": "SANCTIONED"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000001102",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000001102",
    "node_type": "EXCHANGE_HOT_WALLET",
    "display_name": "EXCHANGE_HOT_WALLET:exchange-shared:1102",
    "risk_level": "NONE"
  }
]
```

**Decision factors**

- `base path evidence`: `HUB_PATH_DISCOUNTED`
- `transaction pattern evidence`: `{'path_edge_factors': [], 'chain': 'ETH', 'asset': 'USDT', 'amount_usd': 1400.0, 'guard_hints': ['EXCHANGE_CONTAMINATION_PREVENTED', 'SERVICE_NODE_PROPAGATION_STOPPED']}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[('HUB_PATH_DISCOUNTED', 0.06)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0000`
- `risk_score`: `0.0600`
- `sanctions_evasion_score`: `0.0600`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.06,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Only shared service or hub connectivity was observed, so the path was discounted.",
  "evidence": [
    {
      "reason_code": "HUB_PATH_DISCOUNTED",
      "severity": "LOW",
      "score_contribution": 0.06,
      "path": [],
      "explanation": "Only shared service or hub connectivity was observed, so the path was discounted.",
      "decision_factors": {
        "path_edge_factors": [],
        "chain": "ETH",
        "asset": "USDT",
        "amount_usd": 1400.0,
        "guard_hints": [
          "EXCHANGE_CONTAMINATION_PREVENTED",
          "SERVICE_NODE_PROPAGATION_STOPPED"
        ]
      }
    }
  ]
}
```

## Dust exposure suppression

Scenario source: `isolated_dust_exposure` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

A one-off tiny indirect exposure should be discounted and not escalate to review.

**Expected decision**

- `recommended_action`: `NO_MATCH`
- `expected reason codes`: `DUST_EXPOSURE_DISCOUNTED`
- `observed decision`: `NO_MATCH`
- `observed reason codes`: `DUST_EXPOSURE_DISCOUNTED`

**Expected evidence package**

```json
[
  {
    "reason_code": "DUST_EXPOSURE_DISCOUNTED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000001041",
    "to_node_key": "ETH:0x4200000000000000000000000000000000001042",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 3.0,
    "transaction_count": 1,
    "first_seen": "2026-06-09",
    "last_seen": "2026-06-09",
    "confidence": 0.91
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000001042",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000001042",
    "node_type": "WALLET",
    "display_name": "WALLET:dust-recipient:1042",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000001041",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000001041",
    "node_type": "WALLET",
    "display_name": "WALLET:dust-source:1041",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `DUST_EXPOSURE_DISCOUNTED`
- `transaction pattern evidence`: `{'path_edge_factors': [], 'chain': 'ETH', 'asset': 'ETH', 'amount_usd': 3.0, 'guard_hints': ['DUST_EXPOSURE_IGNORED']}`
- `derived anchor explanation`: `None`
- `concentration/materiality evidence`: `[]`
- `final score contribution`: `[('DUST_EXPOSURE_DISCOUNTED', 0.02)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.0000`
- `risk_score`: `0.0200`
- `sanctions_evasion_score`: `0.0200`
- `discounts or uplifts`: `none`

**Actual CLI/demo output**

```json
{
  "verdict": "NO_MATCH",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.02,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Only isolated dust-level crypto exposure was observed and discounted.",
  "evidence": [
    {
      "reason_code": "DUST_EXPOSURE_DISCOUNTED",
      "severity": "LOW",
      "score_contribution": 0.02,
      "path": [],
      "explanation": "Only isolated dust-level crypto exposure was observed and discounted.",
      "decision_factors": {
        "path_edge_factors": [],
        "chain": "ETH",
        "asset": "ETH",
        "amount_usd": 3.0,
        "guard_hints": [
          "DUST_EXPOSURE_IGNORED"
        ]
      }
    }
  ]
}
```

## Repeated small transfers aggregate into material exposure

Scenario source: `repeated_small_transfers_to_risky_wallet` in `crypto_wallet_exposure`

**Why this case is suspicious or clean**

Ten thousand small transfers aggregate into a material amount and should not be treated as dust.

**Expected decision**

- `recommended_action`: `REVIEW`
- `expected reason codes`: `INBOUND_FROM_SANCTIONED, PROXY_ACCOUNT_BEHAVIOR`
- `observed decision`: `REVIEW`
- `observed reason codes`: `INBOUND_FROM_SANCTIONED, CRYPTO_DERIVED_RISK_ANCHOR, PROXY_ACCOUNT_BEHAVIOR`

**Expected evidence package**

```json
[
  {
    "reason_code": "INBOUND_FROM_SANCTIONED",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  },
  {
    "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
    "severity": "EXPECTED",
    "score_contribution": "scenario-dependent"
  }
]
```

**Synthetic transaction rows**

```json
[
  {
    "from_node_key": "ETH:0x4200000000000000000000000000000000000981",
    "to_node_key": "ETH:0x4200000000000000000000000000000000000982",
    "edge_type": "TRANSFERRED_TO",
    "total_usd_value": 50000.0,
    "transaction_count": 10000,
    "first_seen": "2026-03-15",
    "last_seen": "2026-06-12",
    "confidence": 0.93
  }
]
```

**Involved accounts, wallets, and entities**

```json
[
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000982",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000982",
    "node_type": "WALLET",
    "display_name": "WALLET:structuring-recipient:0982",
    "risk_level": "NONE"
  },
  {
    "node_key": "ETH:0x4200000000000000000000000000000000000981",
    "chain": "ETH",
    "address": "0x4200000000000000000000000000000000000981",
    "node_type": "WALLET",
    "display_name": "WALLET:structuring-source:0981",
    "risk_level": "SANCTIONED"
  }
]
```

**Decision factors**

- `base path evidence`: `INBOUND_FROM_SANCTIONED`
- `transaction pattern evidence`: `{'path_edge_factors': [{'node_key': 'ETH:0x4200000000000000000000000000000000000981', 'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'inbound_from_anchor', 'total_usd_value': 50000.0, 'transaction_count': 10000, 'average_transaction_value': 5.0, 'flow_concentration': 1.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 0.85, 'first_seen': '2026-03-15', 'last_seen': '2026-06-12'}], 'chain': 'ETH', 'asset': 'BNB', 'amount_usd': 850.0, 'guard_hints': [], 'derived_anchor_context': {'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000982', 'derived_anchor_reason_code': 'INBOUND_FROM_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass.'}}`
- `derived anchor explanation`: `{'derived_anchor_wallet': 'ETH:0x4200000000000000000000000000000000000982', 'derived_anchor_reason_code': 'INBOUND_FROM_SANCTIONED', 'derived_anchor_original_score': 0.0, 'derived_anchor_score': 0.55, 'derived_anchor_explanation': 'Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass.'}`
- `concentration/materiality evidence`: `[{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'inbound_from_anchor', 'total_usd_value': 50000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 0.85}]`
- `final score contribution`: `[('INBOUND_FROM_SANCTIONED', 0.48), ('CRYPTO_DERIVED_RISK_ANCHOR', 0.04), ('PROXY_ACCOUNT_BEHAVIOR', 0.1)]`

**Intermediate scoring math**

- `graph/exposure score`: `0.3093`
- `risk_score`: `0.6200`
- `sanctions_evasion_score`: `0.6200`
- `discounts or uplifts`: `none`
- `{'edge_type': 'TRANSFERRED_TO', 'semantic_flow': 'inbound_from_anchor', 'total_usd_value': 50000.0, 'crypto_materiality_weight': 0.86, 'concentration_score': 1.0, 'flow_concentration': 1.0, 'time_decay': 1.0, 'hub_penalty': 1.0, 'directional_multiplier': 0.85}`

**Actual CLI/demo output**

```json
{
  "verdict": "REVIEW",
  "risk_type": "SANCTIONS_EVASION",
  "risk_score": 0.62,
  "evasion_typology": "PROXY_NETWORK",
  "primary_reason": "Wallet received funds through a path originating from a sanctioned source.",
  "evidence": [
    {
      "reason_code": "INBOUND_FROM_SANCTIONED",
      "severity": "MEDIUM",
      "score_contribution": 0.48,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000982",
          "node_key": "ETH:0x4200000000000000000000000000000000000982",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000981",
          "edge_to": "ETH:0x4200000000000000000000000000000000000982",
          "node_key": "ETH:0x4200000000000000000000000000000000000981",
          "edge_from": "ETH:0x4200000000000000000000000000000000000981",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.93,
          "first_seen": "2026-03-15",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "total_usd_value": 50000.0,
          "override_allowed": true,
          "transaction_count": 10000,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 5.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Wallet received funds through a path originating from a sanctioned source.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000981",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "inbound_from_anchor",
            "total_usd_value": 50000.0,
            "transaction_count": 10000,
            "average_transaction_value": 5.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 0.85,
            "first_seen": "2026-03-15",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "BNB",
        "amount_usd": 850.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000982",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    },
    {
      "reason_code": "CRYPTO_DERIVED_RISK_ANCHOR",
      "severity": "LOW",
      "score_contribution": 0.04,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000982",
          "node_key": "ETH:0x4200000000000000000000000000000000000982",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000981",
          "edge_to": "ETH:0x4200000000000000000000000000000000000982",
          "node_key": "ETH:0x4200000000000000000000000000000000000981",
          "edge_from": "ETH:0x4200000000000000000000000000000000000981",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.93,
          "first_seen": "2026-03-15",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "total_usd_value": 50000.0,
          "override_allowed": true,
          "transaction_count": 10000,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 5.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "This wallet itself qualifies as a derived crypto sanctions-risk anchor for a later controlled upstream-funding pass.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000981",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "inbound_from_anchor",
            "total_usd_value": 50000.0,
            "transaction_count": 10000,
            "average_transaction_value": 5.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 0.85,
            "first_seen": "2026-03-15",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "BNB",
        "amount_usd": 850.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000982",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    },
    {
      "reason_code": "PROXY_ACCOUNT_BEHAVIOR",
      "severity": "LOW",
      "score_contribution": 0.1,
      "path": [
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000982",
          "node_key": "ETH:0x4200000000000000000000000000000000000982",
          "node_type": "WALLET"
        },
        {
          "chain": "ETH",
          "address": "0x4200000000000000000000000000000000000981",
          "edge_to": "ETH:0x4200000000000000000000000000000000000982",
          "node_key": "ETH:0x4200000000000000000000000000000000000981",
          "edge_from": "ETH:0x4200000000000000000000000000000000000981",
          "edge_type": "TRANSFERRED_TO",
          "last_seen": "2026-06-12",
          "node_type": "WALLET",
          "confidence": 0.93,
          "first_seen": "2026-03-15",
          "risk_level": "SANCTIONED",
          "hub_penalty": 1.0,
          "semantic_flow": "inbound_from_anchor",
          "edge_direction": "forward",
          "total_usd_value": 50000.0,
          "override_allowed": true,
          "transaction_count": 10000,
          "flow_concentration": 1.0,
          "concentration_score": 1.0,
          "directional_multiplier": 0.85,
          "incoming_concentration": 1.0,
          "outgoing_concentration": 1.0,
          "average_transaction_value": 5.0,
          "crypto_materiality_weight": 0.86
        }
      ],
      "explanation": "Intermediary routing, bridge usage, or pass-through behavior increases sanctions-evasion concern.",
      "decision_factors": {
        "path_edge_factors": [
          {
            "node_key": "ETH:0x4200000000000000000000000000000000000981",
            "edge_type": "TRANSFERRED_TO",
            "semantic_flow": "inbound_from_anchor",
            "total_usd_value": 50000.0,
            "transaction_count": 10000,
            "average_transaction_value": 5.0,
            "flow_concentration": 1.0,
            "crypto_materiality_weight": 0.86,
            "concentration_score": 1.0,
            "hub_penalty": 1.0,
            "directional_multiplier": 0.85,
            "first_seen": "2026-03-15",
            "last_seen": "2026-06-12"
          }
        ],
        "chain": "ETH",
        "asset": "BNB",
        "amount_usd": 850.0,
        "guard_hints": [],
        "derived_anchor_context": {
          "derived_anchor_wallet": "ETH:0x4200000000000000000000000000000000000982",
          "derived_anchor_reason_code": "INBOUND_FROM_SANCTIONED",
          "derived_anchor_original_score": 0.0,
          "derived_anchor_score": 0.55,
          "derived_anchor_explanation": "Current wallet already has strong enough crypto sanctions-evasion evidence to seed the controlled upstream-funding pass."
        }
      }
    }
  ]
}
```
