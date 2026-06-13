# ScreenSmart — Sanctions Screening (Hackathon)

Turn a payment instruction (name + country, or a crypto wallet) into a
**MATCH / REVIEW / NO_MATCH** verdict in well under 1 second.

**Read [`ARCHITECTURE.md`](ARCHITECTURE.md)** — the full plan: data, models, system
design, training, parallelism, crypto, and the hackathon build order.

## Quick start
```powershell
# deps already installed in .venv
.venv\Scripts\python.exe src\download_data.py        # pull all sanctions datasets
.venv\Scripts\python.exe src\explore.py              # profile + charts 01–07
.venv\Scripts\python.exe src\generate_transactions.py# synthetic labelled payments
.venv\Scripts\python.exe src\benchmark.py            # latency + quality, charts 08–09
.venv\Scripts\python.exe src\screener.py             # smoke-test the engine
```

## What's proven so far (real measurements)
- Index: **70,811 entities / 290,096 name variants / ~1,456 wallets** in RAM.
- Latency: **p99 7.3 ms, max 22.7 ms** per check — ~140× under the 1 s budget.
- Recall **1.00**, but naive precision **0.32** (over-blocks 3.1% of clean payments)
  → the precision model (Stage 3, see ARCHITECTURE §4–5) is the thing to build next.

## Layout
- `data/raw/` — OFAC, UN, UK OFSI, OpenSanctions (sanctions + PEPs), OFAC crypto XML.
- `data/processed/` — cleaned parquet + synthetic transaction stream.
- `src/` — download, explore, generate, screener, benchmark.
- `reports/visuals/` — charts 01–09.
