# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---
# PART A — The full streaming platform (multi-service; runs on Docker)

The repo has grown from a single screening engine into a **real-time streaming sanctions
platform** spanning several top-level modules that share one Postgres and one Kafka.

## Repo layout (top-level)
| Dir | What it is | Package | Runs as |
|---|---|---|---|
| `screensmart_app/` | name/identity screening engine + REST API + **Kafka worker** | `screensmart` | api + `screensmart-worker` |
| `exposure_graph/` | crypto graph-hop exposure engine + **Kafka worker** | `screensmart` (⚠ same name) | `exposure-worker` |
| `sanctions_ingestion/` | downloads/parses OFAC/OFSI/UN/OpenSanctions → Postgres | `sanctions_ingest` | `sanctions-ingest` |
| `streaming/pipeline/` | **glue services**: ingest gateway, accumulator, ws-gateway | `pipeline` | `ingest`, `accumulator`, `ws-gateway` |
| `frontend/` | React+Vite dashboard (live dots + analyst review queue) | — | `frontend` (nginx) |
| `data/`, `reports/`, `models/` | datasets, charts, trained model | — | mounted volumes |
| `docker-compose.yml`, `.env.example` | the whole system | — | — |

⚠ **`screensmart_app` and `exposure_graph` both use the top-level package name `screensmart`** —
they must NEVER run in the same process/venv. They only ever talk over Kafka topics, and the
`streaming/pipeline` package imports neither of them.

## Data flow (event-driven scatter-gather)
```
ingest (POST /ingest, /ingest/replay) ─▶ kafka: screening.txns
     │ group:screensmart-name                    │ group:exposure
     ▼                                            ▼
screensmart-worker (name+wallet)          exposure-worker (graph hops)
     │ results.name                              │ results.exposure
     └──────────────────┬─────────────────────────┘
                        ▼
            accumulator  (join by txn_id, worst-of combine, build dossier)
              │ upsert                       │ produce
              ▼                              ▼
          Postgres (pipeline_verdict)   kafka: screening.verdicts
                        │                      │
       REST /review,/txn,/stats  ◀── ws-gateway ──▶ WS /ws/feed
                        └──────────► FRONTEND (live 🟢🟡🔴 dots + login + review queue)
```
- **Fan out to both always**: each worker marks `applicable:false` when it has nothing to
  screen; the accumulator combines only applicable parts (worst-of: MATCH>REVIEW>NO_MATCH).
- **Verdict→status→colour**: MATCH=blocked=🔴, REVIEW=review=🟡, NO_MATCH=allowed=🟢.
- Event contracts: `streaming/pipeline/contracts.py` (`TxnEvent`, `ModuleResult`, `VerdictRecord`).
  Workers emit plain dicts matching `ModuleResult`.

## Run the whole platform (on a machine WITH Docker)
```bash
cp .env.example .env                 # compose interpolates POSTGRES_*, JWT_SECRET
docker compose up --build            # brings up kafka, postgres, all services, frontend
# one-time data prep (in separate shells / exec):
docker compose run --rm sanctions-ingest si-init-db && docker compose run --rm sanctions-ingest si-ingest   # fill sanctions DB
docker compose exec exposure-worker sh -lc "eg-init-db && eg-build-graph && eg-precompute"                   # build crypto graph
# drive the live feed:
curl -X POST "http://localhost:8090/ingest/replay?count=2000&rate=30"
```
**Ports**: frontend `:8080` · ws-gateway `:8091` (REST+WS) · ingest `:8090` · screensmart-api `:8000` · kafka host `:29092` · postgres `:5432`. Analyst login: `analyst` / `analyst`.

## Build/verify status (IMPORTANT — built on a no-Docker machine)
- ✅ **Verified here**: all Python modules import; `streaming` services + both workers compile;
  the React frontend `npm run build` succeeds; `docker-compose.yml` parses.
- ❌ **NOT run here**: Kafka, Postgres, and the containers — **Docker is not installed on the
  build machine** (nor Java). The system is build-complete and wired, but the end-to-end
  `docker compose up` has not been executed. First real run happens on the Docker host —
  expect to debug image builds / topic timing there (the Kafka healthcheck gates startup).
- Known gap: `exposure_graph`'s graph is **synthetic** — real OFAC wallets aren't graph nodes,
  so live crypto exposure only fires for graph-resident node_keys (screensmart-worker still
  exact-matches real sanctioned wallets). Seeding the graph with real anchors is future work.

---
# PART B — The screening engine (`screensmart_app`)

## What this is
ScreenSmart — a sanctions-screening engine. A payment (a name + country for fiat, or a
wallet address for crypto) is turned into a **MATCH / REVIEW / NO_MATCH** verdict in well
under one second. All project code, docs, **`models/`** and **`logs/`** live in the **`screensmart_app/`**
bundle; the large/shared artifacts (`data/`, `reports/`, `.venv/`) and this file stay at
the repo root. Problem statement: `screensmart_app/ScreenSmart_Brief_Humanized.md`. Full
design + measured results: `screensmart_app/ARCHITECTURE.md`. Quick start:
`screensmart_app/README.md`.

## Environment & how to run
- **No global Python** (Windows). Use the venv interpreter directly:
  `.venv\Scripts\python.exe`.
- The engine package lives in `screensmart_app/src/screensmart/` and is **not installed** —
  scripts under `screensmart_app/src/` that `import screensmart` need `PYTHONPATH` set to
  that `src/` dir. `serve.py` inserts it automatically; the other CLIs do not.
- The project root (where `data/`/`models/` live) is found via the `.screensmart-root`
  marker file at the repo root — `config.py` walks up to it, so code can sit in the bundle
  while artifacts stay at the root. Don't delete that marker.
- Always export `PYTHONIOENCODING=utf-8` (sanctions names are Unicode; the Windows console
  is cp1252 and will crash on print otherwise). For long-running scripts also set
  `PYTHONUNBUFFERED=1`, or stdout block-buffers and you see no progress until the end.

PowerShell prelude used for every command below (run from the repo root):
```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUNBUFFERED='1'; $env:PYTHONPATH='C:\Users\MatejaSubin\Documents\Hakathon\screensmart_app\src'
$vpy = 'C:\Users\MatejaSubin\Documents\Hakathon\.venv\Scripts\python.exe'
$src = 'C:\Users\MatejaSubin\Documents\Hakathon\screensmart_app\src'
```

| Task | Command |
|---|---|
| Download sanctions datasets → `data/raw/` | `& $vpy $src\download_data.py` |
| Profile data + charts 01–07 → `data/processed/sanctions_clean.parquet` | `& $vpy $src\explore.py` |
| Generate labelled synthetic payments → `data/processed/transactions.parquet` | `& $vpy $src\generate_transactions.py` |
| Train/compare/select Stage-3 model → `models/precision_model.joblib` + charts 10–11 | `& $vpy $src\train_model.py` |
| Benchmark latency + quality on the model → charts 08–09 | `& $vpy $src\benchmark.py` |
| Validation report (bootstrap CIs + dangerous-miss + per-scenario) | `& $vpy $src\validate.py` |
| Run the REST API (Swagger at http://127.0.0.1:8000/docs) | `& $vpy $src\serve.py` |
| Demo identity + risk layers against a running API | `& $vpy $src\api_demo_identity.py` |
| Run the API in Docker (from repo root) | `docker compose up --build` |

Install: `pip install -r requirements.txt` is the **runtime/serving** set only; use
`requirements-dev.txt` for training/exploration (adds matplotlib/seaborn/etc.). The
Docker image installs runtime-only.

There is **no test suite** and no linter configured. Validation is done by running
`train_model.py` (prints a 4-model comparison) and `benchmark.py` (prints precision /
recall / flag-recall / over-block / latency), and `api_demo_identity.py` against a
running server.

## Data pipeline (strict order — each step consumes the previous output)
`download_data.py` → `data/raw/*` (OpenSanctions consolidated CSV is the backbone; it
already merges OFAC/EU/UN/OFSI/PEPs) → `explore.py` writes `sanctions_clean.parquet` →
`generate_transactions.py` writes `transactions.parquet` → `train_model.py` writes
`models/precision_model.joblib` (+ `comparison.json`) → `benchmark.py` / `validate.py` /
`serve.py` load both the parquet and the model. The raw/processed parquets are large
regenerable artifacts; regenerate rather than edit.

## Sibling services & the database (separate top-level dirs, shared Postgres)
- `sanctions_ingestion/` — downloads + parses OFAC/OFSI/UN/OpenSanctions into Postgres
  (`opensanctions_target`, `crypto_wallet`, `ingest_run`). Package `sanctions_ingest`.
- `exposure_graph/` — crypto graph-hop tracing; writes precomputed `exposure_index`.
  ⚠ Its package is ALSO named `screensmart` (collides with this one) — so screensmart_app
  must NEVER import it; it reads the shared tables instead (see `screensmart/db.py`).
- **DB mode**: set `SCREENSMART_SANCTIONS_SOURCE=db` + `DATABASE_URL=...` and the screener
  loads entities from `opensanctions_target` and crypto exposure from `exposure_index`
  (`db.py` + `SanctionsIndex.from_db` + `screen_wallet`). Default is `parquet` (offline).
  `sqlalchemy`/`psycopg` are only imported on the DB path.

## Architecture — the screening funnel
The engine is a clean-architecture package; dependencies point inward (domain depends on
nothing). A screen runs S0→S4 in `screening/screener.py`:

- **S0a** exact passport/national-ID hit (`index.id_entity`) → instant MATCH (definitive,
  even with a garbled name). **S0b** exact normalised-name gated by token *rarity*
  (distinctive exacts auto-block, common ones fall through) / exact wallet → MATCH.
- **S1** recall: `indexing/index.py` `SanctionsIndex` — IDF-weighted phonetic+token
  blocking index → small candidate set of `entity_id`s.
- **S2** features: `matching/scoring.py` `build_features()` → a `MatchFeatures` (15 name/
  context features). DOB/ID are computed too but are NOT model features (see gotcha 13).
- **S3** Stage-3 model: `model/` — a `PrecisionModel` (LightGBM / sklearn GBT / Logistic /
  soft-voting Ensemble) outputs a **calibrated probability**. If no model is loaded the
  screener falls back to the raw fuzzy score.
- **S4** risk-adjusted thresholds `tau_low`/`tau_high` (lowered by `risk.py` for risky
  payments) → verdict. **S4b** identity RULES on the chosen candidate: exact DOB promotes
  REVIEW→MATCH; a DOB mismatch demotes MATCH→REVIEW (never auto-block a different DOB).

Layers: `domain/` (Pydantic models + enums, split across `payment.py`/`entity.py`/
`features.py`/`result.py`), `indexing/`, `matching/`, `model/`, `screening/`, plus
`config.py` (pydantic-settings), `normalization.py`, `synthesis.py`, `risk.py`,
`logging_setup.py`, `evaluation.py`.

## Invariants & gotchas (the things that will bite you)
1. **Train/serve feature parity is sacred.** Training pairs (`model/dataset.py`) and live
   screening (`matching/scoring.py`) must compute features through the *same*
   `build_features()` + `normalization`. `MatchFeatures.FEATURE_NAMES` / `to_vector()`
   define the canonical vector order — change features in lockstep and retrain, or the
   model silently reads garbage.
2. **`normalization.norm()` transliterates to ASCII (unidecode) on BOTH sides.** This is
   what lets Cyrillic/Arabic names match. Do not revert to a Latin-only regex — native
   scripts would normalise to empty and be silently released.
3. **`rare_token_overlap` is fuzzy (Jaro-Winkler), not exact** — so a typo'd distinctive
   surname still scores. It is the core anti-false-positive signal.
4. **Thresholds are tuned on the LIVE transaction distribution, not the training set.**
   The synthetic training set is ~50% positive; real traffic is ~2%. `train_model.py`
   `choose_thresholds()` tunes `tau_high` for block precision and `tau_low` for sanctioned-
   recall vs a review-queue budget, on a held-out slice of `transactions.parquet`.
5. **Metrics are scenario-based (sanctioned vs clean), not the policy labels.** See
   `evaluation.py` `_SANCTIONED` / `_CLEAN`. Headline numbers: `block_precision`,
   `flag_recall` (sanctioned NOT released — the safety metric), `over_block_rate`.
6. **DOB / passport-ID are applied as RULES, not model features** (gotcha 13). They are
   computed in `build_features` for the screener's exact-ID short-circuit + DOB
   promote/demote rules and the explanation, but excluded from `to_vector()`.
7. **Model persistence pickles the whole `PrecisionModel`** (`model/base.py`) so the
   ensemble round-trips; `load_model()` returns a `LoadedModel` (predict + thresholds).
   The `.joblib` is fully reproducible from `train_model.py` — treat it as disposable; the
   pipeline is the asset.
8. **Training and TEST noise are DIFFERENT on purpose.** Training pairs (`dataset.py`) use
   `synthesis.degrade` (transliterate/typo/reorder); the test stream (`generate_transactions.py`)
   uses `synthesis.eval_degrade` (vowel-drop/double/middle-initial/alt-translit). This
   makes the benchmark measure GENERALISATION, not memorisation. Clean-name pools + the
   `random_dob`/`random_id` helpers are shared. Don't "unify" the two noise families.
9. **Scale with processes, not threads** — screening is CPU-bound Python; the GIL means
   threads give ~no speedup (benchmarked). `serve.py` is a single-worker dev server;
   scale via uvicorn `--workers` or `docker compose up --scale`.
10. **Logging is structured JSON-lines** (`logging_setup.py` → `screensmart_app/logs/screensmart.jsonl`).
    The API emits one `screen` event per verdict — this is the audit trail. Use
    `log_event("name", **fields)`, not `print()`, for anything that should be auditable.
11. **Paths come from `config.py` only.** `data/`/`reports/` resolve to the repo root (via
    the `.screensmart-root` marker); `models/`/`logs/` resolve to the bundle (`_BUNDLE`).
    Never hardcode `__file__`-relative data paths in scripts — import `settings`.
12. **Docker**: `Dockerfile` in `screensmart_app/` bakes the model; `data/` is a runtime
    volume; `.screensmart-root` is created at `/app` so config resolves inside the container.
13. **Identity (DOB/ID) is a rule layer, risk is a threshold layer — neither is in the
    match model.** `risk.py` scores payment context (amount/rail/country/currency) and
    LOWERS `tau_high`/`tau_low` for risky payments (S4). The screener's S0a (exact-ID →
    MATCH) and S4b (DOB promote/demote) are deterministic. Keeping these out of the model
    is intentional: they're sparse on real payments and diluted the classifier's precision
    when tried as features.
14. **The train/test split is ENTITY-DISJOINT** (`synthesis.entity_split`, fixed
    `SPLIT_SEED`). `train_model.py` trains pairs only on `train_ids`; `generate_transactions.py`
    builds the test stream only from `eval_ids`. This + the independent noise (gotcha 8) is
    why the metrics are trustworthy — don't let the two share entities again.
15. **`choose_thresholds` `tau_low` uses a TIE-ROBUST budget search** (`_budget_threshold`),
    not `np.quantile` — tree models pile identical calibrated probs on one value, which made
    `np.quantile` flood REVIEW to 90%. The headline metric is **dangerous-miss** (sanctioned
    released) from `validate.py`, which bootstraps 95% CIs — report ranges, not point values.
