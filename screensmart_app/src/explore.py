"""
Explore + visualise the sanctions data, and characterise the matching problem.

Outputs PNG charts to reports/visuals and prints a text profile. We lean on the
OpenSanctions consolidated "sanctions" file (clean schema) for most analysis, and
parse the OFAC enhanced XML for crypto wallet addresses.

Run: .venv\\Scripts\\python.exe src\\explore.py
"""
from __future__ import annotations
import pathlib, re, sys, collections, io
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from screensmart.config import settings

sys.stdout.reconfigure(encoding="utf-8")
sns.set_theme(style="whitegrid")
RAW = settings.raw_dir
VIS = settings.visuals_dir
PROC = settings.processed_dir
for _d in (VIS, PROC):
    _d.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    path = VIS / name
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  chart -> {path.name}")


def line(t=""):
    print(t)


# ---------------------------------------------------------------- load
line("Loading OpenSanctions consolidated sanctions file...")
san = pd.read_csv(RAW / "opensanctions_sanctions.csv", dtype=str, keep_default_na=False)
line(f"  {len(san):,} sanctioned entities, {san.shape[1]} columns")

# normalise helpers
san["n_aliases"] = san["aliases"].apply(lambda s: 0 if not s else len(s.split(";")))
san["name_len"] = san["name"].str.len().fillna(0).astype(int)
san["name_tokens"] = san["name"].apply(lambda s: len(re.findall(r"\w+", s)) if s else 0)
san["primary_country"] = san["countries"].apply(lambda s: s.split(";")[0] if s else "")
san["primary_program"] = san["sanctions"].apply(lambda s: s.split(";")[0][:40] if s else "")
san["first_seen_dt"] = pd.to_datetime(san["first_seen"], errors="coerce", utc=True)

# =============================================================== PROFILE
line("\n================ DATA PROFILE ================")
line(f"Entity types (schema):")
schema_counts = san["schema"].value_counts()
for k, v in schema_counts.head(12).items():
    line(f"   {k:<22} {v:>7,}")

line(f"\nEntities WITH >=1 alias: {(san['n_aliases']>0).mean()*100:.1f}%  "
     f"(max aliases on one entity: {san['n_aliases'].max()})")
top_alias = san.nlargest(5, "n_aliases")[["name", "n_aliases", "schema"]]
line("Most aliased entities (transliteration burden):")
for _, r in top_alias.iterrows():
    line(f"   {r['n_aliases']:>3} aliases  {r['name'][:60]}")

# =============================================================== CHARTS
# 1. entity types
fig, ax = plt.subplots(figsize=(8, 4.5))
schema_counts.head(10).iloc[::-1].plot.barh(ax=ax, color="#2c7fb8")
ax.set_title("Sanctioned entities by type (OpenSanctions consolidated)")
ax.set_xlabel("count")
save(fig, "01_entity_types.png")

# 2. top countries
cc = san[san["primary_country"] != ""]["primary_country"].value_counts().head(20)
fig, ax = plt.subplots(figsize=(8, 5))
cc.iloc[::-1].plot.barh(ax=ax, color="#d95f0e")
ax.set_title("Top 20 countries of sanctioned entities")
ax.set_xlabel("count")
save(fig, "02_top_countries.png")

# 3. alias count distribution (capped)
fig, ax = plt.subplots(figsize=(8, 4.5))
capped = san["n_aliases"].clip(upper=15)
sns.histplot(capped, bins=16, ax=ax, color="#756bb1")
ax.set_title("Aliases per entity (capped at 15) — the fuzzy-match surface")
ax.set_xlabel("number of aliases / a.k.a. spellings")
save(fig, "03_alias_distribution.png")

# 4. name token count (matters for tokenised matching)
fig, ax = plt.subplots(figsize=(8, 4.5))
sns.histplot(san["name_tokens"].clip(upper=10), bins=10, ax=ax, color="#31a354")
ax.set_title("Tokens per primary name (capped at 10)")
ax.set_xlabel("word tokens in name")
save(fig, "04_name_tokens.png")

# 5. growth over time (first_seen) -> 'lists update daily' reality
ts = san.dropna(subset=["first_seen_dt"]).copy()
if len(ts):
    by_month = ts.set_index("first_seen_dt").resample("ME").size().cumsum()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    by_month.plot(ax=ax, color="#c51b8a")
    ax.set_title("Cumulative sanctioned entities over time (first_seen)")
    ax.set_ylabel("cumulative entities")
    save(fig, "05_growth_over_time.png")

# 6. most common name tokens => false-positive hot spots
STOP = {"the", "of", "and", "co", "ltd", "llc", "company", "limited", "al",
        "group", "international", "trading", "inc", "corp", "for", "general"}
tok = collections.Counter()
for nm in san["name"]:
    for t in re.findall(r"[a-zA-ZÀ-ɏ]+", nm.lower()):
        if len(t) > 2 and t not in STOP:
            tok[t] += 1
common = pd.Series(dict(tok.most_common(25)))
fig, ax = plt.subplots(figsize=(8, 6))
common.iloc[::-1].plot.barh(ax=ax, color="#636363")
ax.set_title("Most common name tokens — likely false-positive triggers")
ax.set_xlabel("appears in N entity names")
save(fig, "06_common_tokens.png")
line("\nTop false-positive-prone tokens: " + ", ".join(list(common.index[:12])))

# =============================================================== CRYPTO
line("\n================ CRYPTO WALLETS (OFAC enhanced XML) ================")
xml = RAW / "ofac_sdn_advanced.xml"
wallets = collections.Counter()
wallet_examples = []
if xml.exists():
    # stream-scan the text for "Digital Currency Address - XBT" style features
    pat = re.compile(r"Digital Currency Address\s*-\s*([A-Z0-9]+)</[^>]+>\s*"
                     r"(?:<[^>]+>\s*)*?<.*?VersionDetail[^>]*>([^<]+)<", re.S)
    # simpler: find feature type then nearby value; do a robust two-pass regex
    text = xml.read_text(encoding="utf-8", errors="replace")
    # currency code appears as: Digital Currency Address - XBT
    for m in re.finditer(r"Digital Currency Address - ([A-Z0-9]{2,6})", text):
        wallets[m.group(1)] += 1
    # capture a few example address strings (base58/hex-ish tokens 26-64 chars)
    addrs = re.findall(r"<VersionDetail[^>]*>([13a-zA-HJ-NP-Za-km-z0-9x]{26,64})</VersionDetail>", text)
    wallet_examples = addrs[:5]
total_wallets = sum(wallets.values())
line(f"  total sanctioned wallet 'features': {total_wallets:,}")
for cur, n in wallets.most_common(15):
    line(f"     {cur:<6} {n:>5}")
if wallet_examples:
    line("  example addresses: " + ", ".join(a[:20] + '...' for a in wallet_examples[:3]))

if wallets:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    pd.Series(dict(wallets.most_common(15))).iloc[::-1].plot.barh(ax=ax, color="#1c9099")
    ax.set_title("Sanctioned crypto wallets by currency (OFAC)")
    ax.set_xlabel("count")
    save(fig, "07_crypto_wallets.png")

# =============================================================== PEPs (count only; big file)
line("\n================ PEPs (size only) ================")
pep_path = RAW / "opensanctions_peps.csv"
if pep_path.exists():
    # count rows cheaply
    with open(pep_path, "rb") as f:
        n = sum(1 for _ in f) - 1
    line(f"  PEP entities available: ~{n:,}")

# =============================================================== save processed
keep = ["id", "schema", "name", "aliases", "n_aliases", "name_tokens",
        "primary_country", "countries", "primary_program", "sanctions",
        "birth_date", "identifiers",          # secondary identifiers (DOB + passport/national IDs)
        "first_seen", "datasets" if "datasets" in san.columns else "dataset"]
keep = [c for c in keep if c in san.columns]
san[keep].to_parquet(PROC / "sanctions_clean.parquet", index=False)
line(f"\nSaved processed parquet -> {PROC/'sanctions_clean.parquet'}  ({len(san):,} rows)")
line("\nDONE. Charts in reports/visuals/.")
