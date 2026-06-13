# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
| Inspect per-scenario model probabilities (debugging) | `& $vpy $src\diagnose.py` |
| Run the REST API (Swagger at http://127.0.0.1:8000/docs) | `& $vpy $src\serve.py` |
| Run the API in Docker (from repo root) | `docker compose up --build` |

There is **no test suite** and no linter configured. Validation is done by running
`train_model.py` (prints a 4-model comparison) and `benchmark.py` (prints precision /
recall / flag-recall / over-block / latency), and `screensmart_app/src/api_demo.py`
against a running server.

## Data pipeline (strict order — each step consumes the previous output)
`download_data.py` → `data/raw/*` (OpenSanctions consolidated CSV is the backbone; it
already merges OFAC/EU/UN/OFSI/PEPs) → `explore.py` writes `sanctions_clean.parquet` →
`generate_transactions.py` writes `transactions.parquet` → `train_model.py` writes
`models/precision_model.joblib` (+ `comparison.json`) → `benchmark.py` / `serve.py` load
both the parquet and the model. The raw/processed parquets are large regenerable
artifacts; regenerate rather than edit.

## Architecture — the screening funnel
The engine is a clean-architecture package; dependencies point inward (domain depends on
nothing). A screen runs S0→S4 in `screening/screener.py`:

- **S0** exact normalised-name (gated by token *rarity* — distinctive exacts auto-block,
  common ones fall through) / exact wallet → instant MATCH.
- **S1** recall: `indexing/index.py` `SanctionsIndex` — IDF-weighted phonetic+token
  blocking index → small candidate set of `entity_id`s.
- **S2** features: `matching/scoring.py` `build_features()` → a `MatchFeatures`.
- **S3** Stage-3 model: `model/` — a `PrecisionModel` (LightGBM / sklearn GBT / Logistic /
  soft-voting Ensemble) outputs a **calibrated probability**. If no model is loaded the
  screener falls back to the raw fuzzy score.
- **S4** thresholds `tau_low` / `tau_high` → verdict + human-readable `reasons`.

Layers: `domain/` (Pydantic models + enums, split across `payment.py`/`entity.py`/
`features.py`/`result.py`), `indexing/`, `matching/`, `model/`, `screening/`, plus
`config.py` (pydantic-settings), `normalization.py`, `synthesis.py`, `evaluation.py`.
`screensmart_app/src/screener.py` is a back-compat shim re-exporting `SanctionsScreener`.

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
6. **DOB / passport-ID features are deliberately excluded** — synthetic payments carry
   none, so adding them would create train/serve skew. Documented future work, not a bug.
7. **Model persistence pickles the whole `PrecisionModel`** (`model/base.py`) so the
   ensemble round-trips; `load_model()` returns a `LoadedModel` (predict + thresholds).
   The `.joblib` is fully reproducible from `train_model.py` — treat it as disposable; the
   pipeline is the asset.
8. **`synthesis.py` is shared** by the transaction generator and the training-pair builder
   so the noise operators (transliterate/typo/reorder) and clean-name pools stay identical.
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
