"""Stage-3 precision model: a common interface over interchangeable classifiers.

Every model is trained then wrapped in an **isotonic calibrator** so that
`predict_proba` returns a *calibrated* P(true match) — which is what makes the
MATCH/REVIEW/NO_MATCH thresholds meaningful and defensible.

A trained model is persisted with joblib as a self-describing bundle (estimator +
calibrator + feature order + chosen thresholds + metrics + timestamp).
"""
from __future__ import annotations
import abc
import pathlib
import warnings
from typing import Optional
import numpy as np
import joblib

# We fit on numpy arrays and predict on numpy arrays; LightGBM still emits a
# per-call "X does not have valid feature names" warning. Silence it once here.
warnings.filterwarnings("ignore", message="X does not have valid feature names")
from sklearn.model_selection import train_test_split
from sklearn.isotonic import IsotonicRegression

from ..domain.models import MatchFeatures, ModelMetrics


class PrecisionModel(abc.ABC):
    """Trainable wrapper. Subclasses only supply `name` and `_build()`."""

    name: str = "base"

    def __init__(self) -> None:
        """Initialise to unfitted state."""
        self.estimator = None
        self.calibrator: Optional[IsotonicRegression] = None
        self.feature_names = list(MatchFeatures.FEATURE_NAMES)

    @abc.abstractmethod
    def _build(self):
        """Return an unfitted sklearn-style estimator with predict_proba."""

    def fit(self, X: np.ndarray, y: np.ndarray, *, val_frac: float = 0.25,
            seed: int = 42) -> "PrecisionModel":
        """Split data, fit the estimator, then isotonic-calibrate on the held-out fold."""
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=int)
        Xtr, Xcal, ytr, ycal = train_test_split(
            X, y, test_size=val_frac, random_state=seed, stratify=y)
        self.estimator = self._build()
        self.estimator.fit(Xtr, ytr)
        # calibrate raw scores -> probabilities on held-out fold
        raw = self._raw_proba(Xcal)
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.calibrator.fit(raw, ycal)
        return self

    def _raw_proba(self, X: np.ndarray) -> np.ndarray:
        """Uncalibrated positive-class probability from the raw estimator."""
        return self.estimator.predict_proba(np.asarray(X, dtype=float))[:, 1]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Calibrated P(true match) ∈ [0, 1] for a batch of feature vectors."""
        raw = self._raw_proba(X)
        if self.calibrator is not None:
            return self.calibrator.predict(raw)
        return raw

    def _bundle(self, *, tau_high: float, tau_low: float,
                metrics: Optional[ModelMetrics], created_at: str) -> dict:
        # We pickle the whole trained model object (estimator + calibrator, or an
        # ensemble of them) so any PrecisionModel — single or composite — persists
        # the same way and reloads with a uniform predict interface.
        return {
            "model": self,
            "model_name": self.name,
            "feature_names": self.feature_names,
            "tau_high": tau_high,
            "tau_low": tau_low,
            "metrics": metrics.model_dump() if metrics else {},
            "created_at": created_at,
        }

    def save(self, path: str | pathlib.Path, *, tau_high: float, tau_low: float,
             metrics: ModelMetrics, created_at: str) -> None:
        """Persist the trained model + thresholds + metadata to disk."""
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._bundle(tau_high=tau_high, tau_low=tau_low,
                                  metrics=metrics, created_at=created_at), path)

    def as_loaded(self, *, tau_high: float, tau_low: float,
                  metrics: Optional[ModelMetrics] = None,
                  created_at: str = "") -> "LoadedModel":
        """Wrap this freshly-trained model for serving without a disk round-trip."""
        return LoadedModel(self._bundle(tau_high=tau_high, tau_low=tau_low,
                                        metrics=metrics, created_at=created_at))


class LoadedModel:
    """A read-only, already-calibrated model for serving (single model or ensemble)."""

    def __init__(self, bundle: dict):
        """Unpack the bundle; keep a reference to the model's predict_proba."""
        self._model: PrecisionModel = bundle["model"]
        self.model_name: str = bundle["model_name"]
        self.feature_names: list[str] = bundle["feature_names"]
        self.tau_high: float = bundle["tau_high"]
        self.tau_low: float = bundle["tau_low"]
        self.metrics: dict = bundle.get("metrics", {})
        self.created_at: str = bundle.get("created_at", "")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Calibrated P(true match) ∈ [0, 1] for a batch of feature vectors."""
        return self._model.predict_proba(np.asarray(X, dtype=float))

    def predict_one(self, vector: list[float]) -> float:
        """Single-sample inference; returns a plain float in [0, 1]."""
        return float(self.predict_proba(np.asarray([vector], dtype=float))[0])


def load_model(path: str | pathlib.Path) -> LoadedModel:
    """Load a previously saved model bundle from disk."""
    return LoadedModel(joblib.load(pathlib.Path(path)))
