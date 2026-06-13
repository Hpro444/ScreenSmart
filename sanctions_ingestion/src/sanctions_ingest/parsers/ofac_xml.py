"""Parser for OFAC's enhanced SDN XML (``SDN_ENHANCED.XML``).

Schema (default namespace ``…/ENHANCED_XML``)::

    <sanctionsData><entities>
      <entity id="36">
        <generalInfo><entityType>Entity</entityType></generalInfo>
        <sanctionsPrograms><sanctionsProgram>CUBA</sanctionsProgram></sanctionsPrograms>
        <names>…<formattedFullName>ACME LTD</formattedFullName>…</names>
        <features>
          <feature id="…"><type featureTypeId="344">Digital Currency Address - XBT</type>
            <value>1A1zP1…</value></feature>
        </features>
      </entity>
    </entities></sanctionsData>

We stream entities with ``iterparse`` (the file is ~100 MB), emit one
:class:`OfacEnhancedEntryIn` each, and a :class:`CryptoWalletIn` for every
"Digital Currency Address - <CUR>" feature (currency is inline in ``<type>``,
address is the feature's ``<value>``).
"""
from __future__ import annotations

import pathlib

from lxml import etree

from ..schemas.crypto import CryptoWalletIn
from ..schemas.ofac import OfacEnhancedEntryIn
from ._util import clean, localname

_WALLET_PREFIX = "Digital Currency Address"


def _find_text(el, name: str) -> str | None:
    """First non-empty text among descendants of ``el`` with local tag ``name``."""
    for d in el.iter():
        if isinstance(d.tag, str) and localname(d.tag) == name:
            t = clean(d.text)
            if t:
                return t
    return None


def _all_texts(el, name: str) -> list[str]:
    out = []
    for d in el.iter():
        if isinstance(d.tag, str) and localname(d.tag) == name:
            t = clean(d.text)
            if t:
                out.append(t)
    return out


def _feature_type_and_value(feature) -> tuple[str | None, str | None]:
    """Return (type-text, value-text) for a ``<feature>`` element."""
    ftype = value = None
    for d in feature.iter():
        if not isinstance(d.tag, str):
            continue
        ln = localname(d.tag)
        if ln == "type" and ftype is None:
            ftype = clean(d.text)
        elif ln == "value" and value is None:
            value = clean(d.text)
    return ftype, value


def parse_ofac_enhanced(path: pathlib.Path) -> tuple[list[OfacEnhancedEntryIn], list[CryptoWalletIn]]:
    """Stream-parse the enhanced XML into (entries, wallets)."""
    entries: list[OfacEnhancedEntryIn] = []
    wallets: list[CryptoWalletIn] = []

    context = etree.iterparse(str(path), events=("end",))
    for _event, el in context:
        if not isinstance(el.tag, str) or localname(el.tag) != "entity":
            continue

        uid = el.get("id")
        name = _find_text(el, "formattedFullName") or _find_text(el, "formattedLastName")
        entity_type = _find_text(el, "entityType")
        programs = _all_texts(el, "sanctionsProgram")
        entries.append(
            OfacEnhancedEntryIn(
                uid=clean(uid),
                name=name,
                entity_type=entity_type,
                programs=programs,
                raw={"uid": uid, "name": name, "entity_type": entity_type},
            )
        )

        for feat in el.iter():
            if not isinstance(feat.tag, str) or localname(feat.tag) != "feature":
                continue
            ftype, value = _feature_type_and_value(feat)
            if not ftype or not ftype.startswith(_WALLET_PREFIX) or not value:
                continue
            currency = ftype.split("-", 1)[-1].strip() or None
            wallets.append(
                CryptoWalletIn(
                    address=value,
                    currency=currency,
                    source="ofac_enhanced",
                    entity_ref=clean(uid),
                    entity_name=name,
                    raw={"uid": uid, "currency": currency, "address": value},
                )
            )

        # Free memory: clear the finished entity and drop processed siblings.
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]

    return entries, wallets
