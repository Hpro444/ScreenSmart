"""Closed vocabularies used across the domain."""
from __future__ import annotations
from enum import Enum


class VerdictType(str, Enum):
    MATCH = "MATCH"        # block the payment
    REVIEW = "REVIEW"      # route to a human analyst
    NO_MATCH = "NO_MATCH"  # release


class Channel(str, Enum):
    FIAT = "fiat"
    CRYPTO = "crypto"


class CountryMatch(str, Enum):
    """Agreement between the payment country and the entity's countries."""
    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"    # one side missing -> no signal

    def as_code(self) -> float:
        """Encode as a numeric feature: match=1.0, unknown=0.0, mismatch=-1.0."""
        return {"match": 1.0, "unknown": 0.0, "mismatch": -1.0}[self.value]


class EntitySchema(str, Enum):
    """OpenSanctions entity types we care about (others fall back to OTHER)."""
    PERSON = "Person"
    ORGANIZATION = "Organization"
    LEGAL_ENTITY = "LegalEntity"
    COMPANY = "Company"
    CRYPTO_WALLET = "CryptoWallet"
    SECURITY = "Security"
    VESSEL = "Vessel"
    AIRPLANE = "Airplane"
    OTHER = "Other"

    @classmethod
    def coerce(cls, value: str) -> "EntitySchema":
        """Parse a raw schema string, falling back to OTHER for unknown values."""
        try:
            return cls(value)
        except ValueError:
            return cls.OTHER

    @property
    def is_person(self) -> bool:
        """True only for the Person schema — used as a binary model feature."""
        return self is EntitySchema.PERSON

    @property
    def is_org(self) -> bool:
        """True for any organisational schema (Organization, LegalEntity, Company)."""
        return self in (EntitySchema.ORGANIZATION, EntitySchema.LEGAL_ENTITY,
                        EntitySchema.COMPANY)
