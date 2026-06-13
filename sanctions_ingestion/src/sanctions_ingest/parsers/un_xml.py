"""Parser for the UN Security Council consolidated list (``consolidated.xml``).

Stable, well-documented schema: ``<INDIVIDUALS><INDIVIDUAL>`` and
``<ENTITIES><ENTITY>`` records sharing the same field tags. Parsed
namespace-agnostically for resilience.
"""
from __future__ import annotations

import pathlib

from lxml import etree

from ..schemas.un import UnEntityIn
from ._util import clean, localname

_NAME_PARTS = ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")


def _iter_local(root, name: str):
    for el in root.iter():
        if isinstance(el.tag, str) and localname(el.tag) == name:
            yield el


def _texts(el, name: str) -> list[str]:
    return [t for t in (clean(c.text) for c in _iter_local(el, name)) if t]


def _text(el, name: str) -> str | None:
    vals = _texts(el, name)
    return vals[0] if vals else None


def _nested(el, parent: str, child: str) -> str | None:
    for p in _iter_local(el, parent):
        v = _text(p, child)
        if v:
            return v
    return None


def _parse_record(record, record_type: str) -> UnEntityIn:
    name = " ".join(t for part in _NAME_PARTS for t in [_text(record, part)] if t)
    nationalities = [v for nat in _iter_local(record, "NATIONALITY") for v in _texts(nat, "VALUE")]
    un_list_type = _nested(record, "UN_LIST_TYPE", "VALUE") or _text(record, "UN_LIST_TYPE")
    return UnEntityIn(
        un_id=_text(record, "DATAID"),
        record_type=record_type,
        name=name or None,
        aliases=_texts(record, "ALIAS_NAME"),
        un_list_type=un_list_type,
        reference_number=_text(record, "REFERENCE_NUMBER"),
        programs=[un_list_type] if un_list_type else [],
        nationalities=nationalities,
        listed_on=_text(record, "LISTED_ON"),
        comments=_text(record, "COMMENTS1"),
        raw={"un_id": _text(record, "DATAID"), "name": name, "type": record_type},
    )


def parse_un(path: pathlib.Path) -> list[UnEntityIn]:
    """Parse the UN consolidated XML into individual + entity records."""
    root = etree.parse(str(path)).getroot()
    out: list[UnEntityIn] = []
    for ind in _iter_local(root, "INDIVIDUAL"):
        out.append(_parse_record(ind, "individual"))
    for ent in _iter_local(root, "ENTITY"):
        out.append(_parse_record(ent, "entity"))
    return out
