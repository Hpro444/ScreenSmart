"""ScreenSmart — sanctions screening engine (clean-architecture package).

Layers (dependencies point inward only):
    domain/      pure Pydantic models + enums, no I/O, no heavy deps
    indexing/    in-RAM blocking index over the sanctions list
    matching/    feature extraction for a (payment, candidate) pair
    model/       the Stage-3 precision classifier(s) + training data
    screening/   the SanctionsScreener orchestrator (S0-S4)
"""
__version__ = "0.2.0"
