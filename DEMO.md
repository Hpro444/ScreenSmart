# ScreenSmart Demo

Snapshot date: 2026-06-13

This demo covers only the graph/account exposure branch.

The important design choice is:

- account exposure is evaluated independently from name screening
- name fuzzy/vector screening is owned by a separate parallel branch
- the graph runtime does not depend on the name screener

## What Runs Realtime

### Account-only path

Realtime account exposure screening uses only:

- `recipient_iban` / `account_number`
- in-memory `exposure_index`
- in-memory `graph_nodes`

It does not do:

- online BFS
- online graph traversal
- per-request graph expansion

All graph propagation remains offline in `src/screensmart/exposure/precompute.py`.

For `SENT_TO` edges, the graph does not use only absolute amount. It computes
`flow_materiality_weight`, which combines:

- absolute transfer size
- relative counterparty concentration

This helps distinguish:

- a large transfer that is only a tiny fraction of a hub account's total flow
- a smaller transfer that represents most of a proxy account's outgoing behavior

## How To Reproduce

Bring up Postgres:

```bash
docker compose up -d
docker compose ps
```

Rebuild the synthetic graph dataset and exposure index:

```bash
PYTHONPATH=src python -m screensmart.exposure.synthetic_graph --seed 42 --reset
PYTHONPATH=src python -m screensmart.exposure.precompute --max-depth 3 --top-k 20 --reset
```

Run the account-only evaluation at the current production demo threshold:

```bash
PYTHONPATH=src python -m screensmart.exposure.evaluate
```

Optional threshold sweep:

```bash
PYTHONPATH=src python -m screensmart.exposure.evaluate --sweep
```

Manual account lookup:

```bash
PYTHONPATH=src python -m screensmart.exposure.lookup --iban TR32SS42000000000000000556
```

Manual account-focused example:

```bash
PYTHONPATH=src python -m screensmart.exposure.lookup \
  --iban TR32SS42000000000000000556
```

## Large-Scale Dataset

Default generation with seed `42` produces:

| Metric | Value |
|---|---:|
| graph_nodes | 13,392 |
| graph_edges | 37,110 |
| synthetic_payments | 1,750 |
| exposure_index rows | 9,545 |
| risk anchors | 2,867 |
| clean nodes | 10,525 |
| average degree | 5.54 |
| max degree | 240 |
| hub-like nodes | 12 |

Measured end-to-end process runtimes:

| Job | Runtime |
|---|---:|
| synthetic generation + Postgres insert | 1.943 s |
| offline exposure precompute | 2.475 s |

The graph contains aggregated relationships only. It does not create transaction
nodes or one edge row per transaction.

## Account-Only Performance

Benchmark target:

- `AccountExposureLookup.screen_account()`
- 1,750 synthetic account lookups
- threshold `0.08`
- lookup already loaded in memory

### Latency

| Metric | Value |
|---|---:|
| p50 | 0.0020 ms |
| p95 | 0.0078 ms |

Interpretation:

- account lookup is effectively O(1) at runtime
- it is far below any payment-execution SLA concern

## Account-Only Quality

These are the metrics that matter for the graph feature itself.

Threshold in use: `0.08`

| Metric | Value |
|---|---:|
| account_accuracy | 1.000 |
| dangerous_miss_rate | 0.000 |
| false_positive_friction_rate | 0.000 |
| review_rate | 0.429 |
| p50 latency | 0.0020 ms |
| p95 latency | 0.0078 ms |

Interpretation:

- every risky synthetic account case is caught
- no clean synthetic account case is escalated by the account graph
- current graph thresholding and two-hop override behave correctly on the synthetic set

## Account-Only Confusion Matrix

Account verdict vs expected verdict:

| Expected \ Predicted | MATCH | REVIEW | NO_MATCH |
|---|---:|---:|---:|
| MATCH | 150 | 0 | 0 |
| REVIEW | 0 | 750 | 0 |
| NO_MATCH | 0 | 0 | 850 |

This is the cleanest view of what the graph feature currently does.

## Account-Only Scenario Breakdown

| Scenario | Count | Expected | Observed account behavior |
|---|---:|---|---|
| `direct_sanctioned_iban` | 150 | MATCH | 150 MATCH |
| `one_hop_exposure` | 200 | REVIEW | 200 REVIEW |
| `high_volume_proxy` | 200 | REVIEW | 200 REVIEW |
| `shell_company` | 150 | REVIEW | 150 REVIEW |
| `two_hop_exposure` | 200 | REVIEW | 200 REVIEW |
| `old_tiny_exposure` | 150 | NO_MATCH | 150 NO_MATCH |
| `clean_common_name` | 300 | NO_MATCH | 300 NO_MATCH |
| `background_clean` | 400 | NO_MATCH | 400 NO_MATCH |

## Threshold Sweep

Account-only threshold sweep summary:

| Threshold | account_accuracy | dangerous_miss_rate | false_positive_friction_rate |
|---|---:|---:|---:|
| 0.05 | 1.000 | 0.000 | 0.000 |
| 0.08 | 1.000 | 0.000 | 0.000 |
| 0.10 | 1.000 | 0.000 | 0.000 |
| 0.15 | 1.000 | 0.000 | 0.000 |
| 0.25 | 0.960 | 0.078 | 0.000 |
| 0.45 | 0.762 | 0.463 | 0.000 |

Takeaway:

- `0.45` is much too high for this scoring scale
- `0.08` is a safe demo threshold
- `0.08` preserves the intended two-hop sanctioned-path behavior

## Sample Input Data

Representative synthetic payments:

| Case | Scenario | Name | IBAN | Country | Amount | Expected |
|---|---|---|---|---|---:|---|
| `direct_sanctioned_iban-s42-0001` | `direct_sanctioned_iban` | Farid Nasser | `ES11SS42000000000000000001` | ES | 8500 | MATCH |
| `one_hop_exposure-s42-0151` | `one_hop_exposure` | Rashid Baranov Trading Counterparty | `RS73SS42000000000000000152` | RS | 6200 | REVIEW |
| `two_hop_exposure-s42-0352` | `two_hop_exposure` | Omar Khalaf Logistics Payee | `TR32SS42000000000000000556` | TR | 4895 | REVIEW |
| `old_tiny_exposure-s42-0551` | `old_tiny_exposure` | Rashid Mansouri Legacy Counterparty | `DE94SS42000000000000001152` | DE | 2100 | NO_MATCH |
| `clean_common_name-s42-0701` | `clean_common_name` | Mohammed Hassan | `DE37SS42000000000000001451` | DE | 1400 | NO_MATCH |
| `background_clean-s42-1351` | `background_clean` | Ion Works Ltd | `DE19SS42000000000000002501` | DE | 250 | NO_MATCH |

## Account-Only Examples

### 1. Direct sanctioned IBAN

Observed:

- verdict: `MATCH`
- exposure score: `1.0000`

Account reason:

```text
MATCH: recipient account is directly sanctioned.
```

### 2. One-hop exposure

Observed:

- verdict: `REVIEW`
- exposure score: `0.3395`

Account reason:

```text
REVIEW: recipient account has exposure score 0.3395 from sanctioned anchor GB72SS42000000000000000151 at depth 1 via SENT_TO.
```

### 3. Two-hop sanctioned-path override

Observed:

- verdict: `REVIEW`
- exposure score: `0.0441`

Account reason:

```text
REVIEW: recipient account is 2 hops from a sanctioned account via SENT_TO -> SENT_TO; routed to review despite low decayed exposure score 0.0441.
```

This is the key Step 3 behavior:

- the decayed score alone is low
- the path still reaches a sanctioned source within 2 hops
- the payment is therefore routed to review

### 4. Old tiny exposure

Observed:

- verdict: `NO_MATCH`
- exposure score: `0.0000`

Account reason:

```text
NO_MATCH: no exposure index entry found for recipient account.
```

### 5. Clean account behind a scary common name

Observed in account-only evaluation:

- verdict: `NO_MATCH`
- exposure score: `0.0000`

Interpretation:

- the graph feature stays clean
- the account branch is not fooled by the name

## Visuals Already In Repo

The original sanctions-data exploration charts are in:

- [reports/visuals/01_entity_types.png](reports/visuals/01_entity_types.png)
- [reports/visuals/02_top_countries.png](reports/visuals/02_top_countries.png)
- [reports/visuals/03_alias_distribution.png](reports/visuals/03_alias_distribution.png)
- [reports/visuals/04_name_tokens.png](reports/visuals/04_name_tokens.png)
- [reports/visuals/05_growth_over_time.png](reports/visuals/05_growth_over_time.png)
- [reports/visuals/06_common_tokens.png](reports/visuals/06_common_tokens.png)
- [reports/visuals/07_crypto_wallets.png](reports/visuals/07_crypto_wallets.png)

## Current Takeaway

If you want to demo the account graph feature honestly, use the account-only section above.

The right message is:

1. account exposure lookup is extremely fast
2. account exposure catches indirect risky counterparties
3. account graph currently has zero synthetic false positives
4. account exposure scoring now includes behavioral flow materiality, not just raw amount
5. the graph branch is isolated from the existing name-screening code
