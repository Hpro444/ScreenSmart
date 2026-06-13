"""Backward-compatibility shim — domain models have been split into dedicated modules.

Use the domain package directly instead:
    from screensmart.domain import PaymentInstruction, SanctionedEntity, ...

Or import from the specific module:
    from screensmart.domain.payment import PaymentInstruction
    from screensmart.domain.entity import SanctionedEntity, NameVariant
    from screensmart.domain.features import MatchFeatures, MatchCandidate
    from screensmart.domain.result import ScreeningResult, ModelMetrics
"""
from .payment import PaymentInstruction
from .entity import SanctionedEntity, NameVariant
from .features import MatchFeatures, MatchCandidate
from .result import ScreeningResult, ModelMetrics

__all__ = [
    "PaymentInstruction",
    "SanctionedEntity", "NameVariant",
    "MatchFeatures", "MatchCandidate",
    "ScreeningResult", "ModelMetrics",
]
