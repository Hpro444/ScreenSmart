# ScreenSmart — Sanctions Screening: Data, Models & System Architecture

> A senior-engineer's build plan for the hackathon. Everything below is grounded in
> data we actually downloaded and benchmarks we actually ran on this machine
> (Windows, 8 logical cores, Python 3.12). Numbers are real, not aspirational.

---

## 0. TL;DR

- **The hard part is NOT speed.** Our naive prototype already screens a payment in
  **p99 = 7.3 ms, max = 22.7 ms** against **70,811 entities / 290,096 name variants** —
  ~140× under the 1-second budget. Speed is a solved problem if you index correctly.
- **The hard part is precision.** That same naive matcher has **BLOCK precision 0.32**
  and **over-blocks 3.1 % of clean payments**. Recall is perfect (1.00) but it would
  destroy a real business. *Over-blocking is the engineering problem worth winning.*
- **Therefore the system is a funnel:** cheap recall stage (catch everything) →
  expensive precision stage (a calibrated ML scorer using secondary identifiers) →
  a tiered verdict (`MATCH` / `REVIEW` / `NO_MATCH`) → a usable human review queue.
- **Crypto is a different problem:** wallet matching is an O(1) set lookup; the value
  is in **graph-hop tracing** to sanctioned addresses.

---

## 1. Data we pulled (in `data/raw/`, manifest in `_manifest.json`)

| File | Source | Size | What it is |
|---|---|---|---|
| `ofac_sdn.csv` / `_alt` / `_add` | US Treasury OFAC | 5.3 / 1.0 / 1.6 MB | Primary list, aliases, addresses |
| `ofac_sdn_advanced.xml` | OFAC | 102.8 MB | Enhanced records incl. **crypto wallet features** |
| `un_consolidated.xml` | UN Security Council | 2.1 MB | UN consolidated list |
| `uk_ofsi_conlist.csv` | UK HM Treasury / OFSI | 15.9 MB | UK consolidated list |
| `opensanctions_sanctions.csv` | OpenSanctions | 62.7 MB | **All sanctions merged & normalised** (the workhorse) |
| `opensanctions_default.csv` | OpenSanctions | 457 MB | Sanctions + PEPs + crime, one schema |
| `opensanctions_peps.csv` | OpenSanctions | 184 MB | **~754,633** Politically Exposed Persons |

**Why OpenSanctions is the backbone:** it already merges OFAC/EU/UN/OFSI/+ into one
clean schema (`id, schema, name, aliases, birth_date, countries, addresses,
identifiers, sanctions, program_ids, …`), deduplicated across sources with stable
IDs. You *also* keep the raw authority files for the audit trail (a regulator wants
to see the OFAC record, not "OpenSanctions said so").

> Re-download anytime with `python src/download_data.py`. Lists change daily — see
> §7 on hot-reload. EU's official feed now needs a token; OpenSanctions carries EU
> content, so we rely on it for EU coverage.

### What the data actually looks like (from `src/explore.py`)

- **70,811 sanctioned entities:** 39,598 Person · 16,352 Organization · 5,016 LegalEntity
  · 2,825 Company · **2,463 CryptoWallet** · 2,271 Security · 1,918 Vessel · 344 Airplane.
- **68.4 % carry ≥1 alias.** One entity (`AL-QAIDA IN IRAQ`) has **262** aliases.
  This is the transliteration tax made concrete — see `reports/visuals/03_alias_distribution.png`.
- **Crypto (OFAC enhanced XML):** 814 wallet features — XBT 521, ETH 94, USDT 94,
  TRX 49, LTC 12, XMR 9 … (`07_crypto_wallets.png`).
- **False-positive hot-spots:** the most common name tokens are `muhammad, ali, ahmed,
  abdul, hussein, mahmoud …`. These are exactly the tokens that make `Kim`, `Mohammed`,
  `Wagner`, `Chen` over-match. (`06_common_tokens.png`)

All charts are regenerated into `reports/visuals/` (`01`–`09`).

---

## 2. How transactions look & behave (`src/generate_transactions.py`)

There is **no public dataset of real payment instructions** — they are proprietary and
privacy-sensitive. So we synthesise a **labelled** stream (`data/processed/transactions.parquet`,
20k rows, ground-truth `expected_verdict`). A payment instruction is:

```
txn_id, timestamp, amount, currency, rail (SWIFT/SEPA/FedWire/card/FPS/ACH),
channel (fiat|crypto),
orig_country, bene_name, bene_country,        # fiat
wallet,                                        # crypto
expected_verdict, scenario                     # ground truth
```

**Behavioural mix we model** (this is the realistic shape of the firehose):

| Scenario | Share | Why it matters |
|---|---|---|
| `clean` legit fiat | ~90 % | The overwhelming majority. Must flow invisibly. |
| `fp_bait` (Kim, Mohammed Ali, John Smith…) | ~4.5 % | Clean, but *looks* risky — the over-block trap. |
| `sanctioned_exact` / `_reorder` | ~1.6 % | True hits → must `MATCH`. |
| `sanctioned_translit` / `_typo` | ~1.5 % | True hits **degraded** (Sergey→Sergei, Qadhafi→Gaddafi) → grey-zone `REVIEW`. |
| `crypto_clean` | ~2 % | Random wallets, must pass. |
| `crypto_sanctioned` | ~0.5 % | Real OFAC wallets → `MATCH`. |

The positives are **sampled from the real list and then degraded** with the exact
noise operators that break naive matching (transliteration table, char swap/drop,
token reorder, alias substitution). This makes the benchmark honest: it rewards
systems that survive messy input, not just exact strings.

---

## 3. The matching problem, precisely

1. **Transliteration** — same name, many Latin spellings. Beaten by phonetic keys
   (Metaphone/Double-Metaphone) + edit-distance, not exact match.
2. **Aliases / shell companies** — 68 % have aliases; index *every* variant, not just
   the primary name. Beneficial-ownership links are a graph problem (stretch goal).
3. **False positives** — common tokens dominate; a name-only matcher over-blocks.
   The fix is **secondary identifiers** (DOB, country, ID numbers, entity type) and a
   **calibrated** score, not a higher threshold alone.
4. **Speed** — solved by an in-memory blocking index (§6). Already ~3 ms/check.
5. **Crypto** — addresses can't be fuzzy-matched; trace them (§8).
6. **Human-in-the-loop** — the grey zone is a *feature*: route to `REVIEW` with an
   explanation, don't force a binary call.

---

## 4. Models & scoring — the layered funnel

> Principle: **cheap stages recall everything, expensive stages buy precision.**
> Each payment only pays for the depth it needs; 90 % exit at Stage 1.

```
                    ┌────────────────────────────────────────────────┐
  payment ─────────▶│ S0  EXACT / WALLET  (hash-set, O(1))            │──hit──▶ MATCH
                    └───────────────┬────────────────────────────────┘
                                    │ miss
                    ┌───────────────▼────────────────────────────────┐
                    │ S1  RECALL  (phonetic + token blocking index)   │
                    │      → small candidate set (tens, not 70k)      │
                    └───────────────┬────────────────────────────────┘
                                    │ candidates
                    ┌───────────────▼────────────────────────────────┐
                    │ S2  FUZZY SCORE  (rapidfuzz token_sort+WRatio,  │
                    │      Jaro-Winkler, phonetic agreement)          │
                    └───────────────┬────────────────────────────────┘
                                    │ top candidate(s) + features
                    ┌───────────────▼────────────────────────────────┐
                    │ S3  PRECISION MODEL  (gradient-boosted classifier│
                    │      over name-sim + secondary identifiers)     │
                    │      → calibrated P(true match)                 │
                    └───────────────┬────────────────────────────────┘
                                    │ calibrated probability
                    ┌───────────────▼────────────────────────────────┐
                    │ S4  DECISION  thresholds → MATCH / REVIEW / NO  │
                    └─────────────────────────────────────────────────┘
```

### Stage-by-stage

- **S0 — Exact & wallet (implemented, `screener.py`):** normalised-name dict and a
  `wallet → entity_id` set. Microseconds. Instant `MATCH`.
- **S1 — Recall / blocking (implemented):** for each name token compute a Metaphone
  key; `phonetic_key → [candidate ids]` inverted index. Query gathers candidates by
  shared phonetic tokens. This is what keeps us at 3 ms — we score ~tens of candidates,
  never the whole list. Production swap-in: **vector recall** (encode names with a
  multilingual sentence embedding, ANN search via FAISS/HNSW) to catch semantic/script
  variants phonetics miss.
- **S2 — Fuzzy scoring (implemented):** `rapidfuzz` (C-backed) blend of
  `token_sort_ratio` + `WRatio`; add Jaro-Winkler and a phonetic-agreement ratio.
- **S3 — Precision model (IMPLEMENTED, see `screensmart/model/`):** the original
  prototype stopped at S2 and that is *exactly why its precision was 0.32*. The win,
  now built, is a **calibrated classifier** — we train and compare LightGBM, scikit-learn
  GBT and Logistic Regression (`train_model.py`) and auto-select the best. It takes the
  S2 similarity features **plus secondary signals**:
  - date-of-birth match / mismatch (huge precision lever for persons),
  - country agreement (payment country vs entity country),
  - entity-type compatibility (a person payment shouldn't hit a Vessel),
  - ID-number / passport exact hit (instant high confidence),
  - token-coverage & rare-token bonus (matching "Qadhafi" ≫ matching "Mohammed"),
  - alias-source weight, list authority, PEP-vs-sanction.
  Output a **calibrated probability** (Platt / isotonic) so thresholds mean something.
- **S4 — Decision:** two thresholds learned from the calibration curve to hit a target
  operating point, e.g. *block precision ≥ 0.95* while *recall ≥ 0.99*:
  - `p ≥ τ_high` → **MATCH** (auto-block)
  - `τ_low ≤ p < τ_high` → **REVIEW** (human)
  - `p < τ_low` → **NO_MATCH** (release)

### Adverse-media / NLP (stretch)
A separate text classifier (fine-tuned transformer or an LLM with structured output)
reads news about an entity and emits a risk signal that feeds S3 as a feature. "On a
list *and* in money-laundering reporting" is a far stronger signal than either alone.

---

## 5. How to train the models

**You don't need a labelled production dataset to start — you manufacture one.**

1. **Positive pairs (true matches):** for each list entity, pair its primary name with
   each of its own aliases, and with **programmatically degraded** versions
   (transliteration table, typos, token reorder, honorific drop). These are
   `label = 1`. The alias graph in the data gives tens of thousands for free.
2. **Hard negatives (the gold):** pairs that *score high but are different people* —
   two different `Mohammed`s, `John Smith` vs `John L. Smith` (our prototype's real
   false positive!), same surname different DOB. Mine these by running S1+S2 and taking
   high-similarity / different-`entity_id` pairs. `label = 0`.
3. **Easy negatives:** random clean names vs random entities. `label = 0`.
4. **Features:** the S2/S3 feature vector above, computed per (query, candidate) pair.
5. **Model:** LightGBM binary classifier → **calibrate** (isotonic) on a held-out
   split → pick `τ_low, τ_high` from the precision/recall curve for your SLA.
6. **Evaluate** on `transactions.parquet` (ground-truth `expected_verdict`). Track:
   **block precision, recall, over-block rate, REVIEW-queue volume** — the four numbers
   in `benchmark.py`. Target: precision 0.32 → ≥0.95 with recall held ≥0.99.
7. **Crypto graph model (bonus):** label addresses by hop-distance to a sanctioned
   wallet; train a classifier on graph features (hops, tainted-volume share, mixer
   exposure) → exposure score.

**Retraining cadence:** weekly, or whenever a list update shifts the candidate
distribution. Version every model + threshold set; log which version produced each
verdict (regulators ask "why did you block this, two years ago?").

---

## 6. System architecture

```
                       ┌───────────────────────────────────────────────┐
                       │   DATA PLANE  (runs on a schedule, daily+)      │
  OFAC/UN/OFSI/EU ────▶│  ingest → normalise → dedupe → build artifacts: │
  OpenSanctions   ────▶│   • name/alias index (phonetic + tokens)        │
                       │   • wallet set                                  │
                       │   • ANN vector index (optional)                 │
                       │  publish as an immutable, versioned snapshot    │
                       └───────────────┬───────────────────────────────-┘
                                       │ atomic pointer swap (no downtime)
   payment ──▶ API gateway ──▶ ┌───────▼─────────────────────────────────┐
   (REST/gRPC)                 │  SCREENING SERVICE (stateless, N replicas)│
                               │  loads snapshot into RAM, runs S0–S4      │
                               │  returns verdict + score + explanation    │
                               └───────┬─────────────────┬────────────────┘
                                       │ MATCH/REVIEW     │ every decision
                                       ▼                  ▼
                            ┌────────────────────┐  ┌──────────────────────┐
                            │  REVIEW QUEUE app   │  │  IMMUTABLE AUDIT LOG  │
                            │  analyst tooling    │  │ (verdict, model ver, │
                            │  (see §6.2)         │  │  snapshot ver, ts)   │
                            └────────────────────┘  └──────────────────────┘
```

### 6.1 Why this shape
- **Stateless screening replicas + in-RAM read-only index** → trivial horizontal
  scale and the per-check latency we measured (no DB round-trip on the hot path).
- **Data plane decoupled from the hot path** → list updates never touch live decisions
  until an **atomic snapshot swap** (§7).
- **Everything is logged immutably** → defensible audit trail (the brief's "prove it to
  a regulator in two years" requirement).

### 6.2 The REVIEW queue (don't skip this — it's where most products fail)
An analyst clearing 200 items at 4 pm on a Friday needs, per item, **on one screen**:
the payment, the matched entity, **the specific reason** (which tokens/identifiers
matched, DOB/country agreement), the list + program + date, similar past decisions,
and one-click **block / release / escalate** with a mandatory note. Pre-sort the queue
by score and by amount-at-risk. Cache decisions so the same alias next week auto-resolves.

---

## 7. Handling daily list updates with zero downtime

- Ingestion writes a **new immutable snapshot** (versioned directory / object key):
  index + wallet set + model + thresholds, all together.
- The screening service holds the current snapshot in RAM and serves from it.
- A new snapshot is loaded **in the background**; when ready, an **atomic pointer swap**
  flips live traffic to it. In-flight checks finish on the old one. No downtime, no
  half-updated state.
- Roll back = swap the pointer back. Every verdict records its snapshot version, so a
  re-screen is reproducible.

---

## 8. Crypto (the bonus, done right)

- **Direct hit:** wallet address → exact set membership. O(1), already in `screener.py`
  (`screen_wallet`). 2,463 sanctioned wallets in our data.
- **The real value — graph-hop tracing:** on-chain data is a public transaction graph.
  Build (or query) the graph; for a target wallet compute **shortest hop distance to any
  sanctioned address** and **tainted-value share** (how much of its balance traces back
  to a sanctioned source through mixers/bridges). Verdict by exposure:
  - direct = `MATCH`; 1–2 hops or high taint = `REVIEW`; far/clean = `NO_MATCH`.
- **Shared vs distinct logic:** S0/S4 (exact lookup, tiered decision, audit, queue) are
  **shared** with fiat. The *recall* mechanism is **distinct**: fuzzy/phonetic for names,
  graph traversal for wallets. Same funnel, different S1.
- **Data:** OFAC enhanced XML for the seed wallet list; on-chain graph from a public
  node / dataset (Bitcoin/Ethereum) or a commercial tracer for hop computation.

---

## 9. Parallelism & the < 1 s budget — what we measured, honestly

From `src/benchmark.py` over 20,000 payments on this 8-core box:

```
single-thread:  mean 2.9 ms | p50 3.1 | p95 5.4 | p99 7.3 | max 22.7 ms | 325 checks/s
8 threads:      352 checks/s   (speedup only 1.1×)   ← important!
```

**One check is already ~140× under budget.** The interesting finding is the **1.1×
thread speedup**: Python's GIL means threads don't parallelise CPU-bound scoring.
Conclusions for the architecture:

1. **Scale with processes/replicas, not threads.** Throughput scales ~linearly by
   running N screening *processes* (or pods), each with its own copy of the read-only
   index, behind a load balancer. 8 cores ≈ 8× ≈ ~2,600 checks/s/box; add boxes for more.
2. **Keep the hot path GIL-light.** The fuzzy core (`rapidfuzz`) is C and releases the
   GIL; the Python orchestration around it is the bottleneck. Push hot logic into
   vectorised/compiled code (rapidfuzz batch APIs, numpy, or a Rust/C++ extension) to
   make even in-process threading pay off.
3. **The 1 s budget is a *tail* SLA, not a mean.** Our max is 22.7 ms; even a 40× load
   spike stays under 1 s. Guard the tail with: a hard per-check timeout that fails to
   `REVIEW` (never silently release), bounded candidate sets (we cap at 400), and
   back-pressure at the gateway.
4. **Batch & async at the edges.** Screen originator + beneficiary concurrently;
   batch list-screening jobs; keep I/O (audit log, queue write) off the decision path
   (fire-and-forget / async).

> Net: speed is bought by the **index design** (already done) and **process-level
> horizontal scale**, not by threads. Spend your hackathon hours on **precision**.

---

## 10. Hackathon build order (what to do with the hours)

1. **(done)** Download + profile data; synthetic labelled stream; prototype screener;
   latency + quality benchmark. → proves speed, exposes the precision gap.
2. **Stage 3 precision model.** Manufacture pairs (§5), train LightGBM, calibrate, pick
   thresholds. Re-run `benchmark.py` — drive precision 0.32 → ≥0.95 at recall ≥0.99.
   **This is the demo's money slide.**
3. **Explanation payload + REVIEW queue UI.** Even a thin Streamlit/React table that
   shows the queue, the reason, and block/release buttons wins judges.
4. **Crypto graph hops** (bonus) — seed from OFAC wallets, show a traced exposure.
5. **Hot-reload demo** — swap a snapshot live while screening continues.

## 11. Repo map

The screening engine lives in a clean-architecture package (`src/screensmart/`);
inner layers (domain) depend on nothing, outer layers depend inward only.

```
data/raw/                 # original authority files + OpenSanctions (+ _manifest.json)
data/processed/           # sanctions_clean.parquet, transactions.parquet (+ sample csv)
models/                   # precision_model.joblib + comparison.json

src/screensmart/
  config.py               # pydantic-settings Settings (paths, thresholds, train knobs)
  normalization.py        # norm/tokens/phon (shared train+serve tokenisation)
  synthesis.py            # name-degradation operators + clean-name pools
  domain/                 # Pydantic models + enums (the contracts every layer speaks)
  indexing/index.py       # SanctionsIndex: blocking recall, wallet set, token IDF
  matching/scoring.py     # build_features() -> MatchFeatures  (Stage 2)
  model/                  # PrecisionModel ABC + 3 estimators + training-pair builder
  screening/screener.py   # SanctionsScreener: S0–S4 orchestrator -> ScreeningResult
  evaluation.py           # shared evaluate(screener, transactions) -> ModelMetrics

src/download_data.py      # pull all datasets
src/explore.py            # profile + charts 01–07
src/generate_transactions.py  # synthetic labelled payment stream
src/train_model.py        # train/compare/select Stage-3 model, charts 10–11
src/benchmark.py          # latency + parallel + quality, charts 08–09
src/screener.py           # back-compat shim -> screensmart.screening.screener
reports/visuals/          # all PNG charts
requirements.txt          # pinned deps (.venv)
```

Run end-to-end (set `PYTHONPATH=src` so the package is importable):
```
.venv\Scripts\python.exe src\download_data.py
.venv\Scripts\python.exe src\explore.py
.venv\Scripts\python.exe src\generate_transactions.py
.venv\Scripts\python.exe src\train_model.py     # builds models/precision_model.joblib
.venv\Scripts\python.exe src\benchmark.py
```
