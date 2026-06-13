"""Text normalisation primitives (pure functions, no I/O).

Shared by the index builder, the matcher and the training-data synthesiser so
that train-time and serve-time tokenisation are guaranteed identical.
"""
from __future__ import annotations
import re
import jellyfish
from unidecode import unidecode

_TOKEN = re.compile(r"[a-z]+")
_STOP = {"the", "of", "and", "co", "ltd", "llc", "company", "limited",
         "group", "inc", "corp", "al", "el", "bin", "ibn"}


def norm(s: str) -> str:
    """Transliterate to ASCII, lower-case, keep word tokens, collapse whitespace.

    The unidecode pass is critical: sanctioned names (and the payments naming them)
    arrive in Cyrillic, Arabic, Chinese, etc. Transliterating BOTH sides to a common
    ASCII form ('Олексій'->'oleksii') is what makes cross-script matching possible —
    without it any native-script name normalises to empty and is silently released.
    """
    return " ".join(_TOKEN.findall(unidecode(s or "").lower()))


def tokens(s: str) -> list[str]:
    """Content tokens of a (possibly already normalised) string, minus stopwords."""
    return [t for t in _TOKEN.findall((s or "").lower()) if t not in _STOP and len(t) > 1]


def phon(tok: str) -> str:
    """Metaphone phonetic key for a token (falls back to a prefix)."""
    try:
        return jellyfish.metaphone(tok) or tok[:4]
    except Exception:
        return tok[:4]


_NONALNUM = re.compile(r"[^a-z0-9]")


def norm_id(s: str) -> str:
    """Canonicalise an identity number (passport / national ID) for exact comparison:
    keep only alphanumerics, upper-cased ('NRN 89.01-529' -> 'NRN8901529')."""
    return _NONALNUM.sub("", (s or "").lower()).upper()
