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

    @model_validator(mode="after")
    def _check_channel(self) -> "PaymentInstruction":
        """Enforce channel-specific required fields before the object is used."""
        if self.channel is Channel.CRYPTO and not self.wallet:
            raise ValueError("crypto payment requires a wallet address")
        if self.channel is Channel.FIAT and not self.bene_name:
            raise ValueError("fiat payment requires a beneficiary name")
        return self
