"""Parser for OpenSanctions ``targets.simple.csv`` feeds.

One CSV layout serves all four feeds (sanctions / default / peps / crypto). For
the crypto feed we additionally emit :class:`CryptoWalletIn` rows (the wallet
address is the entity name).
"""
from __future__ import annotations

import csv
import pathlib

from ..schemas.crypto import CryptoWalletIn
from ..schemas.opensanctions import OpenSanctionsTargetIn
from ._util import clean, split_multi

# Multi-value cells in targets.simple.csv are ';'-separated.
_LIST_COLS = ("aliases", "countries", "addresses", "identifiers", "sanctions")


def parse_opensanctions(path: pathlib.Path, dataset: str) -> list[OpenSanctionsTargetIn]:
    """Parse a targets.simple CSV into validated target rows."""
    out: list[OpenSanctionsTargetIn] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out.append(
                OpenSanctionsTargetIn(
                    dataset=dataset,
                    entity_id=clean(row.get("id")),
                    schema=clean(row.get("schema")),
                    name=clean(row.get("name")),
                    aliases=split_multi(row.get("aliases")),
                    birth_date=clean(row.get("birth_date")),
                    countries=split_multi(row.get("countries")),
                    addresses=split_multi(row.get("addresses")),
                    identifiers=split_multi(row.get("identifiers")),
                    sanctions=split_multi(row.get("sanctions")),
                    first_seen=clean(row.get("first_seen")),
                    last_seen=clean(row.get("last_seen")),
                    raw=row,
                )
            )
    return out


def parse_opensanctions_wallets(path: pathlib.Path, source: str) -> list[CryptoWalletIn]:
    """Extract ``CryptoWallet`` entities from any OpenSanctions targets.simple feed.

    OpenSanctions retired the standalone crypto dataset; sanctioned wallets now
    live inside the main feeds as ``CryptoWallet``-schema rows whose ``name`` is
    the wallet address. ``source`` labels which feed they came from.
    """
    out: list[CryptoWalletIn] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            schema = clean(row.get("schema")) or ""
            address = clean(row.get("name"))
            if schema != "CryptoWallet" or not address:
                continue
            ident = split_multi(row.get("identifiers"))
            out.append(
                CryptoWalletIn(
                    address=address,
                    currency=ident[0] if ident else None,
                    source=source,
                    entity_ref=clean(row.get("id")),
                    entity_name=address,
                    raw=row,
                )
            )
    return out
