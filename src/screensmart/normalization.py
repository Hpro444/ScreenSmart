"""Text normalisation primitives (pure functions, no I/O).

Shared by the index builder, the matcher and the training-data synthesiser so
that train-time and serve-time tokenisation are guaranteed identical.
"""
from __future__ import annotations
import re
import jellyfish

_TOKEN = re.compile(r"[a-zA-ZÀ-ɏ]+")
_STOP = {"the", "of", "and", "co", "ltd", "llc", "company", "limited",
         "group", "inc", "corp", "al", "el", "bin", "ibn"}


def norm(s: str) -> str:
    """Lower-case, keep word tokens only, collapse whitespace."""
    return " ".join(_TOKEN.findall((s or "").lower()))


def tokens(s: str) -> list[str]:
    """Content tokens of a (possibly already normalised) string, minus stopwords."""
    return [t for t in _TOKEN.findall((s or "").lower()) if t not in _STOP and len(t) > 1]


def phon(tok: str) -> str:
    """Metaphone phonetic key for a token (falls back to a prefix)."""
    try:
        return jellyfish.metaphone(tok) or tok[:4]
    except Exception:
        return tok[:4]
