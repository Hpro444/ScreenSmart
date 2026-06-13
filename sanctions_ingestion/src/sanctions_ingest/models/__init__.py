"""ORM models — importing this package registers every table on ``Base.metadata``.

Add a new source ⇒ add a model here (subclassing ``BaseModel``) and export it.
"""
from .crypto import CryptoWallet
from .ingest_run import IngestRun
from .ofac import OfacAddress, OfacAlias, OfacEnhancedEntry, OfacEntity
from .ofsi import OfsiEntry
from .opensanctions import OpenSanctionsTarget
from .un import UnEntity

__all__ = [
    "IngestRun",
    "OpenSanctionsTarget",
    "OfacEntity",
    "OfacAlias",
    "OfacAddress",
    "OfacEnhancedEntry",
    "UnEntity",
    "OfsiEntry",
    "CryptoWallet",
]
