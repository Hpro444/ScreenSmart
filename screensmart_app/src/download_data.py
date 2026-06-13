"""
Download public sanctions / screening datasets for the ScreenSmart project.

All sources are free & public. We grab raw originals (so we keep an audit trail
of exactly what each authority published) plus OpenSanctions' consolidated,
already-normalised view (which merges OFAC/EU/UN/OFSI/PEPs into one schema).

Run:  .venv\\Scripts\\python.exe src\\download_data.py
"""
from __future__ import annotations
import os
import sys
import time
import json
import pathlib
import requests

from screensmart.config import settings

RAW = settings.raw_dir
RAW.mkdir(parents=True, exist_ok=True)

# (filename, url, note).  Order = roughly most -> least important.
SOURCES = [
    # ---- OFAC (US Treasury) : the canonical primary list ----
    ("ofac_sdn.csv",
     "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV",
     "OFAC Specially Designated Nationals - primary records"),
    ("ofac_sdn_alt.csv",
     "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ALT.CSV",
     "OFAC SDN alternate names / aliases (a.k.a.)"),
    ("ofac_sdn_add.csv",
     "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ADD.CSV",
     "OFAC SDN addresses"),
    ("ofac_consolidated.csv",
     "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONSOLIDATED.CSV",
     "OFAC non-SDN consolidated list"),
    ("ofac_sdn_advanced.xml",
     "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_ENHANCED.XML",
     "OFAC SDN enhanced XML (contains crypto wallet 'features')"),

    # ---- UN Security Council consolidated list ----
    ("un_consolidated.xml",
     "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
     "UN Security Council consolidated sanctions list"),

    # ---- UK OFSI consolidated list ----
    ("uk_ofsi_conlist.csv",
     "https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.csv",
     "UK OFSI consolidated list (HM Treasury)"),

    # ---- OpenSanctions : consolidated + normalised (the workhorse) ----
    ("opensanctions_sanctions.csv",
     "https://data.opensanctions.org/datasets/latest/sanctions/targets.simple.csv",
     "OpenSanctions: ALL sanctions targets merged (OFAC+EU+UN+OFSI+...)"),
    ("opensanctions_default.csv",
     "https://data.opensanctions.org/datasets/latest/default/targets.simple.csv",
     "OpenSanctions default: sanctions + PEPs + crime + more"),
    ("opensanctions_peps.csv",
     "https://data.opensanctions.org/datasets/latest/peps/targets.simple.csv",
     "OpenSanctions: Politically Exposed Persons"),
    ("opensanctions_crypto.csv",
     "https://data.opensanctions.org/datasets/latest/crypto/targets.simple.csv",
     "OpenSanctions: sanctioned crypto wallets"),
]

HEADERS = {"User-Agent": "ScreenSmart-Hackathon/1.0 (research; data download)"}


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def download(fname: str, url: str, note: str) -> dict:
    dest = RAW / fname
    rec = {"file": fname, "url": url, "note": note}
    try:
        t0 = time.time()
        with requests.get(url, headers=HEADERS, stream=True, timeout=120) as r:
            r.raise_for_status()
            size = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
                        size += len(chunk)
        rec.update(status="OK", bytes=size, seconds=round(time.time() - t0, 1))
        print(f"  OK   {fname:<32} {human(size):>10}  ({rec['seconds']}s)  {note}")
    except Exception as e:  # keep going on any single failure
        rec.update(status="FAIL", error=str(e)[:200])
        print(f"  FAIL {fname:<32} {'-':>10}  {e!s:.120}")
    return rec


def main():
    print(f"Downloading {len(SOURCES)} sources into {RAW}\n")
    results = [download(*s) for s in SOURCES]
    ok = [r for r in results if r["status"] == "OK"]
    print(f"\nDone: {len(ok)}/{len(results)} succeeded.")
    manifest = RAW / "_manifest.json"
    manifest.write_text(json.dumps(results, indent=2))
    print(f"Manifest written -> {manifest}")
    if len(ok) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
