"""Concrete Stage-3 classifiers — interchangeable behind PrecisionModel.

We train all of these and let `train_model.py` pick the winner on held-out data.
"""
from __future__ import annotations
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb

from .base import PrecisionModel


class LightGBMModel(PrecisionModel):
    name = "lightgbm"

    def _build(self):
        """300 trees, low LR, subsample=0.9 — tuned for small-ish feature sets."""
        return lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, num_leaves=31,
            subsample=0.9, colsample_bytree=0.9, random_state=42,
            n_jobs=-1, verbose=-1,
        )


class SklearnGBTModel(PrecisionModel):
    name = "sklearn_gbt"

    def _build(self):
        """Sklearn GBT: shallower trees (depth=3) to regularise on small data."""
        return GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=3, random_state=42,
        )


class LogisticModel(PrecisionModel):
    name = "logistic"

    def _build(self):
        """Logistic regression baseline: fast, interpretable, balanced classes."""
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, C=1.0, class_weight="balanced"),
        )


class EnsembleModel(PrecisionModel):
    """Soft-voting ensemble: averages the *calibrated* probabilities of its members.

    Each member calibrates independently in its own fit(), so the averaged score
    stays a sensible probability. Mixing a boosted-tree view with a linear view
    typically trims the variance of either model alone.
    """
    name = "ensemble"

    def __init__(self):
        """Compose the ensemble from one instance of each base model."""
        super().__init__()
        self.members: list[PrecisionModel] = [
            LightGBMModel(), SklearnGBTModel(), LogisticModel()]

    def _build(self):  # not used; fit/predict are overridden
        """Unused — the ensemble fits its members directly."""
        raise NotImplementedError

    def fit(self, X, y, *, val_frac: float = 0.25, seed: int = 42) -> "EnsembleModel":
        """Fit (and self-calibrate) every member on the same data."""
        for m in self.members:
            m.fit(X, y, val_frac=val_frac, seed=seed)
        return self

    def predict_proba(self, X) -> np.ndarray:
        """Mean of members' calibrated probabilities."""
        return np.mean([m.predict_proba(X) for m in self.members], axis=0)


ALL_MODELS: list[type[PrecisionModel]] = [
    LightGBMModel, SklearnGBTModel, LogisticModel, EnsembleModel]
