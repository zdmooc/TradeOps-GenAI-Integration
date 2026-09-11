from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LogisticRegression

from .baselines import positive_class_score


class PlattCalibrator:
    def __init__(self, seed: int = 20260911) -> None:
        self.seed = seed
        self._model = LogisticRegression(
            solver="lbfgs",
            max_iter=1000,
            random_state=seed,
        )

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> "PlattCalibrator":
        scores = np.asarray(scores, dtype=float).reshape(-1, 1)
        labels = np.asarray(labels, dtype=int)
        if len(np.unique(labels)) < 2:
            raise ValueError("calibration labels must contain both classes")
        self._model.fit(scores, labels)
        return self

    def predict(self, scores: np.ndarray) -> np.ndarray:
        scores = np.asarray(scores, dtype=float).reshape(-1, 1)
        return self._model.predict_proba(scores)[:, 1]


class CalibratedSignalQualityModel(BaseEstimator, ClassifierMixin):
    def __init__(
        self,
        base_model: Any,
        calibrator: PlattCalibrator,
        feature_names: tuple[str, ...],
    ) -> None:
        self.base_model = base_model
        self.calibrator = calibrator
        self.feature_names = feature_names
        self.classes_ = np.asarray([0, 1], dtype=int)

    def predict_proba(self, matrix: Any) -> np.ndarray:
        raw = positive_class_score(self.base_model, matrix)
        calibrated = self.calibrator.predict(raw)
        return np.column_stack([1.0 - calibrated, calibrated])

    def predict(self, matrix: Any) -> np.ndarray:
        return (self.predict_proba(matrix)[:, 1] >= 0.5).astype(int)
