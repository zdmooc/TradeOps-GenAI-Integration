from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np

from services.ml_signal_quality.contract import DEFAULT_FEATURE_NAMES

PRODUCTION_QUALIFICATION = "CALIBRATED_OUT_OF_SAMPLE_REAL_MARKET"
_ALLOWED_MODES = {"LAB", "PRODUCTION"}


@dataclass(frozen=True, slots=True)
class ServingIdentity:
    model_name: str
    model_uri: str
    qualification: str
    mode: str


class SignalQualityServingService:
    def __init__(self, model: Any, identity: ServingIdentity) -> None:
        if identity.mode not in _ALLOWED_MODES:
            raise ValueError(f"unsupported serving mode: {identity.mode}")
        if identity.mode == "PRODUCTION" and identity.qualification != PRODUCTION_QUALIFICATION:
            raise ValueError(
                "production serving requires a real-market out-of-sample calibrated model"
            )
        if not hasattr(model, "predict_proba"):
            raise TypeError("model must expose predict_proba")
        self.model = model
        self.identity = identity

    @staticmethod
    def _matrix(instances: Iterable[Mapping[str, float]]) -> np.ndarray:
        rows = list(instances)
        if not rows:
            raise ValueError("instances must not be empty")
        expected = set(DEFAULT_FEATURE_NAMES)
        matrix: list[list[float]] = []
        for index, row in enumerate(rows):
            keys = set(row)
            if keys != expected:
                missing = sorted(expected - keys)
                extra = sorted(keys - expected)
                raise ValueError(
                    f"feature contract mismatch at row {index}: missing={missing} extra={extra}"
                )
            values = [float(row[name]) for name in DEFAULT_FEATURE_NAMES]
            if not all(np.isfinite(values)):
                raise ValueError(f"non-finite feature value at row {index}")
            matrix.append(values)
        return np.asarray(matrix, dtype=float)

    def predict(self, instances: Iterable[Mapping[str, float]]) -> list[dict[str, Any]]:
        matrix = self._matrix(instances)
        probabilities = np.asarray(self.model.predict_proba(matrix), dtype=float)
        if probabilities.shape != (len(matrix), 2):
            raise ValueError("predict_proba must return an N x 2 matrix")
        positive = probabilities[:, 1]
        if not np.all(np.isfinite(positive)) or np.any((positive < 0.0) | (positive > 1.0)):
            raise ValueError("model returned invalid probability values")
        return [
            {
                "label": int(score >= 0.5),
                "quality_score": float(score),
                "probability_status": self.identity.qualification,
                "serving_mode": self.identity.mode,
            }
            for score in positive
        ]


def load_service_from_environment() -> SignalQualityServingService:
    model_uri = os.getenv("MODEL_URI", "").strip()
    qualification = os.getenv("MODEL_QUALIFICATION", "").strip()
    mode = os.getenv("MODEL_SERVING_MODE", "LAB").strip().upper()
    model_name = os.getenv("MODEL_NAME", "tradeops-signal-quality").strip()
    if not model_uri:
        raise RuntimeError("MODEL_URI is required")
    if not qualification:
        raise RuntimeError("MODEL_QUALIFICATION is required")

    import mlflow
    import mlflow.sklearn

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "").strip()
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_registry_uri(tracking_uri)
    model = mlflow.sklearn.load_model(model_uri)
    return SignalQualityServingService(
        model,
        ServingIdentity(
            model_name=model_name,
            model_uri=model_uri,
            qualification=qualification,
            mode=mode,
        ),
    )
