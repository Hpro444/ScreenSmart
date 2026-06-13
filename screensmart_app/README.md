# ScreenSmart — Sanctions Screening (Hackathon)

Turn a payment instruction (name + country, or a crypto wallet) into a
**MATCH / REVIEW / NO_MATCH** verdict in well under 1 second.

**Read [`ARCHITECTURE.md`](ARCHITECTURE.md)** — the full plan: data, models, system
design, training, parallelism, crypto, and the hackathon build order.

## Run with Docker (easiest)
From the **repo root** (one level up from this folder):
```bash
docker compose up --build      # API + Swagger at http://localhost:8000/docs
```
The image bakes in the trained model; the host `data/` is mounted read-only and the
structured audit log is written to `screensmart_app/logs/`.

## Run locally (PowerShell, from the repo root)
```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUNBUFFERED='1'
$env:PYTHONPATH='..\screensmart_app\src'      # or the absolute path to screensmart_app\src
$vpy='..\.venv\Scripts\python.exe'; $src='.\screensmart_app\src'
& $vpy $src\download_data.py          # pull all sanctions datasets
& $vpy $src\explore.py                # profile + charts 01–07
& $vpy $src\generate_transactions.py  # synthetic labelled payments
& $vpy $src\train_model.py            # train/select Stage-3 model -> models/precision_model.joblib
& $vpy $src\benchmark.py              # latency + quality, charts 08–09
& $vpy $src\serve.py                  # run the API (Swagger at :8000/docs)
```

## What's proven (real measurements, ensemble model)
- Index: **70,811 entities / 290,096 name variants / 1,456 wallets** in RAM.
- Quality: **block precision 0.85, flag-recall 0.90, over-block 0.55%**, review queue 6.3%.
- Latency: **p99 ≈ 92 ms** — well under the 1 s budget.

## Layout
This bundle (`screensmart_app/`) holds all code + docs + the trained model + logs:
- `src/screensmart/` — the engine package (domain, indexing, matching, model, screening).
- `src/*.py` — CLIs: download, explore, generate, train_model, benchmark, serve, diagnose.
- `models/` — trained `precision_model.joblib` (gitignored; regenerate via `train_model.py`).
- `logs/` — structured JSON-lines audit log (gitignored).

At the **repo root** (shared/large artifacts): `data/` (sanctions lists + parquet),
`reports/visuals/` (charts 01–11), `.venv/`, `docker-compose.yml`, `CLAUDE.md`.
