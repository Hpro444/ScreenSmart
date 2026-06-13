"""Concrete repositories — each binds one ORM model to ``BaseRepository``.

Add a new source ⇒ add a one-line repo class here and export it.
"""
from ..db.repository import BaseRepository
from ..models import (
    CryptoWallet,
    IngestRun,
    OfacAddress,
    OfacAlias,
    OfacEnhancedEntry,
    OfacEntity,
    OfsiEntry,
    OpenSanctionsTarget,
    UnEntity,
)


class IngestRunRepository(BaseRepository[IngestRun]):
    model = IngestRun


class OpenSanctionsTargetRepository(BaseRepository[OpenSanctionsTarget]):
    model = OpenSanctionsTarget


class OfacEntityRepository(BaseRepository[OfacEntity]):
    model = OfacEntity


class OfacAliasRepository(BaseRepository[OfacAlias]):
    model = OfacAlias


class OfacAddressRepository(BaseRepository[OfacAddress]):
    model = OfacAddress


class OfacEnhancedEntryRepository(BaseRepository[OfacEnhancedEntry]):
    model = OfacEnhancedEntry


class UnEntityRepository(BaseRepository[UnEntity]):
    model = UnEntity


class OfsiEntryRepository(BaseRepository[OfsiEntry]):
    model = OfsiEntry


class CryptoWalletRepository(BaseRepository[CryptoWallet]):
    model = CryptoWallet


__all__ = [
    "IngestRunRepository",
    "OpenSanctionsTargetRepository",
    "OfacEntityRepository",
    "OfacAliasRepository",
    "OfacAddressRepository",
    "OfacEnhancedEntryRepository",
    "UnEntityRepository",
    "OfsiEntryRepository",
    "CryptoWalletRepository",
]
