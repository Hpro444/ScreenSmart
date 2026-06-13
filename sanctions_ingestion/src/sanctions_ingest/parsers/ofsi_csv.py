"""Parser for the UK OFSI consolidated list (``ConList.csv``).

The OFSI CSV begins with a one-cell "date generated" preamble line before the
real header, and the full name is split across ``Name 1`` … ``Name 6`` columns.
We locate the header row dynamically and reconstruct the name; the verbatim row
is always kept in ``raw``.
"""
from __future__ import annotations

import csv
import pathlib

from ..schemas.ofsi import OfsiEntryIn
from ._util import clean

_NAME_COLS = ["Name 1", "Name 2", "Name 3", "Name 4", "Name 5", "Name 6"]


def _find_header(rows: list[list[str]]) -> int:
    """Return the index of the real header row (the one naming 'Group ID')."""
    for i, row in enumerate(rows[:10]):
        cells = {c.strip().lower() for c in row}
        if "group id" in cells or "name 6" in cells:
            return i
    return 0


def _get(row: dict, *names: str) -> str | None:
    """First non-empty value among candidate column names (case/space-tolerant)."""
    norm = {k.strip().lower(): v for k, v in row.items() if k}
    for n in names:
        v = clean(norm.get(n.strip().lower()))
        if v:
            return v
    return None


def parse_ofsi(path: pathlib.Path) -> list[OfsiEntryIn]:
    """Parse ConList.csv into OFSI entry rows."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return []

    hdr_idx = _find_header(rows)
    header = [c.strip() for c in rows[hdr_idx]]
    out: list[OfsiEntryIn] = []
    for rec in rows[hdr_idx + 1:]:
        if not any(c.strip() for c in rec):
            continue
        row = {header[i]: (rec[i] if i < len(rec) else "") for i in range(len(header))}
        name = " ".join(p for p in (clean(row.get(c)) for c in _NAME_COLS) if p)
        out.append(
            OfsiEntryIn(
                group_id=_get(row, "Group ID"),
                name=name or _get(row, "Name 6"),
                name_type=_get(row, "Name Type", "Alias Type"),
                entity_type=_get(row, "Group Type", "Entity Type"),
                regime=_get(row, "Regime", "Regime Name"),
                country=_get(row, "Country", "Address Country"),
                listed_on=_get(row, "Listed On", "Date Designated"),
                raw=row,
            )
        )
    return out
