"""Name-degradation operators — the realistic noise that breaks naive matching.

Used in two places that must agree: the synthetic transaction generator and the
training-pair builder. Each operator takes a name and a seeded `random.Random`.
"""
from __future__ import annotations
import random

# common transliteration / spelling drift seen across official lists
TRANSLIT = {"sergey": "sergei", "muhammad": "mohammed", "ahmad": "ahmed",
            "qadhafi": "gaddafi", "yusuf": "yousef", "abdallah": "abdullah",
            "ii": "y", "ov": "off"}

# clean name pools used to manufacture easy negatives / clean payments. Kept large
# and diverse so synthetic clean traffic mostly does NOT collide with the list — the
# realistic case (a tiny, surname-overlapping pool makes the review rate look worse
# than production, where the vast majority of payees match nothing at all).
CLEAN_FIRST = ["James", "Mary", "Wei", "Emma", "Carlos", "Priya", "Olivia", "Yuki",
               "Liam", "Sofia", "Lucas", "Elena", "David", "Grace", "Noah", "Mei",
               "Ethan", "Chloe", "Daniel", "Hannah", "Ryan", "Laura", "Kevin", "Aisha",
               "Thomas", "Julia", "Henry", "Nadia", "Oscar", "Lena", "Felix", "Tara",
               "Diego", "Ingrid", "Marco", "Sara", "Victor", "Nina", "Paul", "Rebecca"]
CLEAN_LAST = ["Johnson", "Whitfield", "Nguyen", "Mueller", "Rossi", "Lindqvist",
              "Tanaka", "Andersson", "Okafor", "Brennan", "Holloway", "Schmidt",
              "Costa", "Delgado", "Fairbanks", "Underwood", "Kingsley", "Bauer",
              "Castellano", "Hartmann", "Larsson", "Beaumont", "Sinclair", "Vanderberg",
              "Ashworth", "Montgomery", "Fitzgerald", "Pemberton", "Lockwood", "Hawkins"]

# common-name FALSE-POSITIVE bait: legitimate names that PARTIALLY collide with
# sanctioned entries on common tokens (Kim, Mohammed, Wagner ...). Shared by the
# transaction generator and the training-pair builder so the model is explicitly
# taught that a common-token-only overlap is NOT a match.
COMMON_BAIT = ["Kim", "Chen", "Mohammed Ali", "Wagner", "Mohammed", "Ivan Petrov",
               "John Smith", "Maria Garcia", "Li Wei", "Ahmed Hassan", "Ali Khan",
               "Hassan Ahmed", "Wei Chen", "Omar Mohammed", "Sergei Petrov"]


def add_typo(s: str, rng: random.Random) -> str:
    """Single-character corruption: randomly swap adjacent chars, drop, or duplicate."""
    if len(s) < 4:
        return s
    i = rng.randrange(1, len(s) - 1)
    op = rng.choice(["swap", "drop", "dup"])
    if op == "swap":
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if op == "drop":
        return s[:i] + s[i + 1:]
    return s[:i] + s[i] + s[i:]


def transliterate(s: str) -> str:
    """Apply common cross-list transliteration variants (e.g. Qadhafi → Gaddafi)."""
    out = s.lower()
    for a, b in TRANSLIT.items():
        out = out.replace(a, b)
    return out.title()


def reorder(s: str, rng: random.Random) -> str:
    """Shuffle token order to simulate name-field transposition (surname, given → given surname)."""
    parts = s.split()
    if len(parts) >= 2:
        rng.shuffle(parts)
    return " ".join(parts)


def degrade(name: str, rng: random.Random) -> tuple[str, str]:
    """Apply one random degradation; return (degraded_name, mode)."""
    mode = rng.choice(["translit", "typo", "reorder"])
    if mode == "translit":
        return transliterate(name), mode
    if mode == "typo":
        return add_typo(name, rng), mode
    return reorder(name, rng), mode


def random_clean_name(rng: random.Random) -> str:
    """Sample a random first + last name from the clean-name pool (used for easy negatives)."""
    return f"{rng.choice(CLEAN_FIRST)} {rng.choice(CLEAN_LAST)}"
