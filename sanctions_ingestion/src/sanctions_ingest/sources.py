"""The source registry — the single place that wires every feed end to end.

Each :class:`Source` binds a download (filename + URL) to a ``loader`` that parses
the file into one or more :class:`TableLoad`s (a repository + the rows to load +
the refresh ``scope``). The pipeline and scheduler are fully data-driven from this
list, so **adding a feed = one entry here + a parser + a model + a repo.**
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Callable

from . import parsers
from .db.repository import BaseRepository
from .repositories import (
    CryptoWalletRepository,
    OfacAddressRepository,
    OfacAliasRepository,
    OfacEnhancedEntryRepository,
    OfacEntityRepository,
    OfsiEntryRepository,
    OpenSanctionsTargetRepository,
    UnEntityRepository,
)
from .schemas.base import IngestSchema


@dataclass(frozen=True)
class TableLoad:
    """One atomic refresh: replace ``scope`` rows of ``repo_cls`` with ``rows``."""

    repo_cls: type[BaseRepository]
    rows: list[IngestSchema]
    scope: dict


@dataclass(frozen=True)
class Source:
    name: str
    filename: str
    url: str
    note: str
    loader: Callable[[pathlib.Path], list[TableLoad]]


# --- loaders (parse a downloaded file into TableLoads) -----------------------
def _load_opensanctions(dataset: str, *, extract_wallets: bool = False):
    def _loader(path: pathlib.Path) -> list[TableLoad]:
        loads = [TableLoad(
            OpenSanctionsTargetRepository,
            parsers.parse_opensanctions(path, dataset),
            {"dataset": dataset},
        )]
        if extract_wallets:
            source = f"opensanctions_{dataset}"
            loads.append(TableLoad(
                CryptoWalletRepository,
                parsers.parse_opensanctions_wallets(path, source),
                {"source": source},
            ))
        return loads
    return _loader


def _load_ofac_entities(list_source: str):
    def _loader(path: pathlib.Path) -> list[TableLoad]:
        return [TableLoad(
            OfacEntityRepository,
            parsers.parse_ofac_entities(path, list_source),
            {"list_source": list_source},
        )]
    return _loader


def _load_ofac_aliases(path: pathlib.Path) -> list[TableLoad]:
    return [TableLoad(OfacAliasRepository, parsers.parse_ofac_aliases(path), {})]


def _load_ofac_addresses(path: pathlib.Path) -> list[TableLoad]:
    return [TableLoad(OfacAddressRepository, parsers.parse_ofac_addresses(path), {})]


def _load_ofac_enhanced(path: pathlib.Path) -> list[TableLoad]:
    entries, wallets = parsers.parse_ofac_enhanced(path)
    return [
        TableLoad(OfacEnhancedEntryRepository, entries, {}),
        TableLoad(CryptoWalletRepository, wallets, {"source": "ofac_enhanced"}),
    ]


def _load_un(path: pathlib.Path) -> list[TableLoad]:
    return [TableLoad(UnEntityRepository, parsers.parse_un(path), {})]


def _load_ofsi(path: pathlib.Path) -> list[TableLoad]:
    return [TableLoad(OfsiEntryRepository, parsers.parse_ofsi(path), {})]


# --- the registry (same 11 sources as download_data.py) ----------------------
_OFAC = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports"
_OS = "https://data.opensanctions.org/datasets/latest"

SOURCES: list[Source] = [
    Source("ofac_sdn", "ofac_sdn.csv", f"{_OFAC}/SDN.CSV",
           "OFAC SDN primary records", _load_ofac_entities("sdn")),
    Source("ofac_sdn_alt", "ofac_sdn_alt.csv", f"{_OFAC}/ALT.CSV",
           "OFAC SDN alternate names", _load_ofac_aliases),
    Source("ofac_sdn_add", "ofac_sdn_add.csv", f"{_OFAC}/ADD.CSV",
           "OFAC SDN addresses", _load_ofac_addresses),
    Source("ofac_consolidated", "ofac_consolidated.csv", f"{_OFAC}/CONSOLIDATED.CSV",
           "OFAC non-SDN consolidated list", _load_ofac_entities("consolidated")),
    Source("ofac_enhanced", "ofac_sdn_advanced.xml", f"{_OFAC}/SDN_ENHANCED.XML",
           "OFAC enhanced XML (crypto wallets)", _load_ofac_enhanced),
    Source("un_consolidated", "un_consolidated.xml",
           "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
           "UN Security Council consolidated list", _load_un),
    Source("uk_ofsi", "uk_ofsi_conlist.csv",
           "https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.csv",
           "UK OFSI consolidated list", _load_ofsi),
    # The sanctions feed is the backbone; it also carries CryptoWallet entities,
    # so we extract wallets from it (OpenSanctions retired the standalone crypto feed).
    Source("opensanctions_sanctions", "opensanctions_sanctions.csv",
           f"{_OS}/sanctions/targets.simple.csv",
           "OpenSanctions: all sanctions targets merged (+ crypto wallets)",
           _load_opensanctions("sanctions", extract_wallets=True)),
    Source("opensanctions_default", "opensanctions_default.csv",
           f"{_OS}/default/targets.simple.csv",
           "OpenSanctions default: sanctions + PEPs + crime", _load_opensanctions("default")),
    Source("opensanctions_peps", "opensanctions_peps.csv",
           f"{_OS}/peps/targets.simple.csv",
           "OpenSanctions: Politically Exposed Persons", _load_opensanctions("peps")),
]

SOURCES_BY_NAME: dict[str, Source] = {s.name: s for s in SOURCES}
