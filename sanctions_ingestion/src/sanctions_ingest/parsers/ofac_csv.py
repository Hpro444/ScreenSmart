"""Parsers for the OFAC flat files (SDN / CONSOLIDATED / ALT / ADD).

These files have **no header row**; columns are fixed and positional, and ``-0-``
marks an absent value (handled by ``_util.clean``).
"""
from __future__ import annotations

import csv
import pathlib

from ..schemas.ofac import OfacAddressIn, OfacAliasIn, OfacEntityIn
from ._util import clean, to_int

# Positional column layouts (OFAC data file specification).
_SDN_COLS = ["ent_num", "name", "sdn_type", "program", "title", "call_sign",
             "vess_type", "tonnage", "grt", "vess_flag", "vess_owner", "remarks"]
_ALT_COLS = ["ent_num", "alt_num", "alt_type", "alt_name", "alt_remarks"]
_ADD_COLS = ["ent_num", "add_num", "address", "city_state_zip", "country", "add_remarks"]


def _rows(path: pathlib.Path, cols: list[str]):
    """Yield dict rows mapping the positional columns by name."""
    with open(path, encoding="latin-1", newline="") as f:
        for rec in csv.reader(f):
            if not rec:
                continue
            yield {col: (rec[i] if i < len(rec) else None) for i, col in enumerate(cols)}


def parse_ofac_entities(path: pathlib.Path, list_source: str) -> list[OfacEntityIn]:
    """Parse SDN.CSV or CONSOLIDATED.CSV (identical layout) into entity rows."""
    out: list[OfacEntityIn] = []
    for row in _rows(path, _SDN_COLS):
        out.append(
            OfacEntityIn(
                list_source=list_source,
                ent_num=to_int(row.get("ent_num")),
                name=clean(row.get("name")),
                sdn_type=clean(row.get("sdn_type")),
                program=clean(row.get("program")),
                title=clean(row.get("title")),
                remarks=clean(row.get("remarks")),
                raw=row,
            )
        )
    return out


def parse_ofac_aliases(path: pathlib.Path) -> list[OfacAliasIn]:
    """Parse ALT.CSV into alias rows."""
    out: list[OfacAliasIn] = []
    for row in _rows(path, _ALT_COLS):
        out.append(
            OfacAliasIn(
                ent_num=to_int(row.get("ent_num")),
                alt_num=to_int(row.get("alt_num")),
                alt_type=clean(row.get("alt_type")),
                alt_name=clean(row.get("alt_name")),
                alt_remarks=clean(row.get("alt_remarks")),
                raw=row,
            )
        )
    return out


def parse_ofac_addresses(path: pathlib.Path) -> list[OfacAddressIn]:
    """Parse ADD.CSV into address rows."""
    out: list[OfacAddressIn] = []
    for row in _rows(path, _ADD_COLS):
        out.append(
            OfacAddressIn(
                ent_num=to_int(row.get("ent_num")),
                add_num=to_int(row.get("add_num")),
                address=clean(row.get("address")),
                city_state_zip=clean(row.get("city_state_zip")),
                country=clean(row.get("country")),
                add_remarks=clean(row.get("add_remarks")),
                raw=row,
            )
        )
    return out
