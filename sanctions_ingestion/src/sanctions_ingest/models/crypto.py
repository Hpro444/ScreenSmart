"""Sanctioned crypto wallet addresses (OFAC enhanced XML + OpenSanctions crypto)."""
from __future__ import annotations

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import BaseModel


class CryptoWallet(BaseModel):
    __tablename__ = "crypto_wallet"

    address: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    currency: Mapped[str | None] = mapped_column(Text)        # XBT, ETH, USDT, ...
    source: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # ofac_enhanced|opensanctions_crypto
    entity_ref: Mapped[str | None] = mapped_column(Text)      # uid / entity id the wallet belongs to
    entity_name: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_crypto_wallet_addr_lower", "address"),
    )
