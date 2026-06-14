"""Payment-side domain model — the input contract for the screening pipeline."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator

from .enums import Channel


class PaymentInstruction(BaseModel):
    """A payment to be screened. Mirrors a row of transactions.parquet."""
    model_config = ConfigDict(frozen=True)

    txn_id: str
    channel: Channel
    timestamp: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    rail: Optional[str] = None
    orig_country: Optional[str] = None
    bene_name: str = ""
    bene_country: str = ""
    wallet: str = ""
    # secondary identifiers (often absent on a real payment; used when present)
    bene_dob: Optional[str] = None            # ISO birth date of the beneficiary
    bene_passport: Optional[str] = None       # passport number
    bene_national_id: Optional[str] = None    # national / tax ID

    @property
    def identifiers(self) -> list[str]:
        """All identity numbers carried on the payment (passport + national id)."""
        return [v for v in (self.bene_passport, self.bene_national_id) if v]

    @model_validator(mode="after")
    def _check_channel(self) -> "PaymentInstruction":
        """Enforce channel-specific required fields before the object is used."""
        if self.channel is Channel.CRYPTO and not self.wallet:
            raise ValueError("crypto payment requires a wallet address")
        if self.channel is Channel.FIAT and not self.bene_name:
            raise ValueError("fiat payment requires a beneficiary name")
        return self
