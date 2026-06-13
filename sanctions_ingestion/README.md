# sanctions_ingestion

A standalone service that downloads **every public sanctions source** used by
ScreenSmart (the same 11 feeds as `screensmart_app/src/download_data.py`) and
loads them, **fresh on a daily schedule**, into Postgres behind clean SQLAlchemy
ORM models and Pydantic schemas.

It does **not** import or modify `screensmart_app` — wiring the screening engine
to read from these tables is a later task. The database is the product; raw files
are kept under `data/raw/` as an audit trail.

## Design — extending it is one entry per layer

```
src/sanctions_ingest/
  db/base.py         BaseModel  — every table subclasses this (id, raw JSONB, ingest_run_id, timestamps)
  db/repository.py   BaseRepository[ModelT] — generic CRUD + refresh() (atomic per-source reload)
  db/session.py      engine + session_scope()
  models/            one ORM table per source schema
  schemas/           one Pydantic class per source (validated parse output)
  repositories/      one repo per model (e.g. `class OfacEntityRepository(BaseRepository[OfacEntity])`)
  parsers/           raw file -> list[schema]
  sources.py         SOURCES registry: url -> parser -> repo + refresh scope
  pipeline.py        download -> parse -> refresh -> audit (one IngestRun per source)
  scheduler.py       APScheduler daily trigger
  cli.py             init-db | ingest [--source] | run-scheduler
```

**Add a new source** = add a model (subclass `BaseModel`), a Pydantic schema, a
repo (subclass `BaseRepository`), a parser, and one `Source(...)` entry in
`sources.py`. Nothing else changes.

## Tables
`ingest_run` (audit) · `opensanctions_target` (sanctions/default/peps/crypto,
keyed by `dataset`) · `ofac_entity` · `ofac_alias` · `ofac_address` ·
`ofac_enhanced_entry` · `un_entity` · `ofsi_entry` · `crypto_wallet`.

Every table carries a `raw` JSONB column holding the verbatim upstream row, so a
feed adding a column never loses data.

## Run it

```bash
# 1. Install (uv or pip), from this directory
pip install -e .          # or: uv pip install -e .

# 2. Point at the database (defaults to the docker-compose Postgres)
cp .env.example .env      # edit DATABASE_URL if needed

# 3. Create the schema
python -m sanctions_ingest.cli init-db

# 4. One full ingest of all 11 sources
python -m sanctions_ingest.cli ingest
#    ...or a single feed:
python -m sanctions_ingest.cli ingest --source opensanctions_sanctions

# 5. Run the daily scheduler (blocks; Ctrl-C to stop)
python -m sanctions_ingest.cli run-scheduler
```

Console scripts `si-init-db`, `si-ingest`, `si-scheduler` are equivalent.

## Docker

The root `docker-compose.yml` defines a `sanctions-ingest` service that runs the
scheduler against the shared Postgres:

```bash
docker compose up --build sanctions-ingest
```

## Upstream notes (as of June 2026)

- **OpenSanctions retired the standalone `crypto` dataset.** Sanctioned wallets now
  live inside the main `sanctions` feed as `CryptoWallet`-schema rows, so the service
  extracts them from there (plus the OFAC enhanced XML) — there is no separate crypto
  download.
- **OFAC `CONSOLIDATED.CSV` currently returns an empty body.** The `ofac_consolidated`
  source is kept (it may repopulate); an empty download simply loads 0 rows and is
  recorded as `ok` in `ingest_run`.
- The OFAC enhanced XML uses the lowercase `sanctionsData / entity / feature` schema;
  wallet currency is inline in each feature's `<type>` ("Digital Currency Address - XBT")
  and the address is its `<value>`.

## Configuration (env, prefix `SANCTIONS_INGEST_`)

| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://screensmart:screensmart@localhost:5432/screensmart` | DB connection (un-prefixed, project-wide convention) |
| `SANCTIONS_INGEST_INGEST_HOUR` | `3` | Daily run hour (0–23) |
| `SANCTIONS_INGEST_INGEST_MINUTE` | `0` | Daily run minute |
| `SANCTIONS_INGEST_RUN_ON_STARTUP` | `true` | Run once on scheduler start if the DB has no successful run yet |
| `SANCTIONS_INGEST_HTTP_TIMEOUT` | `120` | Per-download timeout (s) |
| `SANCTIONS_INGEST_RAW_DIR` | `<repo>/data/raw` | Where raw files are written |
