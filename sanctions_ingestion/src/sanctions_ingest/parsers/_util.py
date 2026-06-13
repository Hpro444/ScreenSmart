"""Small parsing helpers shared across source parsers."""
from __future__ import annotations

from typing import Iterable

# OFAC flat files use this sentinel for "no value".
_OFAC_NULL = {"-0-", "", "-0- "}


def clean(value: str | None) -> str | None:
    """Trim whitespace; map empty / OFAC ``-0-`` sentinels to ``None``."""
    if value is None:
        return None
    v = value.strip()
    return None if v in _OFAC_NULL else v


def to_int(value: str | None) -> int | None:
    """Best-effort int parse; ``None`` on empty/garbage."""
    v = clean(value)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def split_multi(value: str | None, sep: str = ";") -> list[str]:
    """Split a multi-value cell into a trimmed, empties-removed list."""
    v = clean(value)
    if not v:
        return []
    return [p.strip() for p in v.split(sep) if p.strip()]


def localname(tag: object) -> str:
    """Return an XML tag's local name (namespace stripped)."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def first_text(values: Iterable[str | None]) -> str | None:
    """Return the first non-empty cleaned value, else ``None``."""
    for v in values:
        c = clean(v)
        if c:
            return c
    return None
