from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class SignalQualityRecord:
    record_id: str
    feature_time: datetime
    label_time: datetime
    features: dict[str, float]
    label: int
    source: str = "SYNTHETIC"

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", self.record_id.strip())
        object.__setattr__(self, "source", self.source.upper().strip())
        object.__setattr__(self, "feature_time", _utc(self.feature_time))
        object.__setattr__(self, "label_time", _utc(self.label_time))
        if not self.record_id:
            raise ValueError("record_id is required")
        if self.label not in {0, 1}:
            raise ValueError("label must be 0 or 1")
        if self.label_time <= self.feature_time:
            raise ValueError("label_time must be strictly after feature_time")
        if not self.features:
            raise ValueError("features are required")
        if not all(isfinite(float(value)) for value in self.features.values()):
            raise ValueError("all features must be finite")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("feature_time", "label_time"):
            data[key] = data[key].isoformat().replace("+00:00", "Z")
        return data


@dataclass(frozen=True, slots=True)
class TemporalMLSplit:
    train: tuple[int, int]
    validation: tuple[int, int]
    calibration: tuple[int, int]
    test: tuple[int, int]

    def to_dict(self) -> dict[str, list[int]]:
        return {
            "train": list(self.train),
            "validation": list(self.validation),
            "calibration": list(self.calibration),
            "test": list(self.test),
        }


@dataclass(frozen=True, slots=True)
class WalkForwardMLWindow:
    window_id: int
    train: tuple[int, int]
    validation: tuple[int, int]
    calibration: tuple[int, int]
    test: tuple[int, int]


@dataclass(frozen=True, slots=True)
class ModelEvaluation:
    model_name: str
    dataset_role: str
    status: str
    metrics: dict[str, float]


@dataclass(frozen=True, slots=True)
class DriftFeature:
    feature: str
    psi: float
    standardized_mean_shift: float
    status: str


@dataclass(frozen=True, slots=True)
class DriftReport:
    overall_status: str
    max_psi: float
    features: tuple[DriftFeature, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "max_psi": self.max_psi,
            "features": [asdict(item) for item in self.features],
        }


@dataclass(frozen=True, slots=True)
class SignalQualityExperimentReport:
    experiment_id: str
    dataset_hash: str
    feature_contract_version: str
    feature_names: tuple[str, ...]
    split: TemporalMLSplit
    baseline_validation: tuple[ModelEvaluation, ...]
    champion_model: str
    calibration_method: str
    raw_test_metrics: dict[str, float]
    calibrated_test_metrics: dict[str, float]
    probability_status: str
    qualification_reasons: tuple[str, ...]
    drift: DriftReport
    walk_forward_metrics: tuple[dict[str, float], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "dataset_hash": self.dataset_hash,
            "feature_contract_version": self.feature_contract_version,
            "feature_names": list(self.feature_names),
            "split": self.split.to_dict(),
            "baseline_validation": [asdict(item) for item in self.baseline_validation],
            "champion_model": self.champion_model,
            "calibration_method": self.calibration_method,
            "raw_test_metrics": self.raw_test_metrics,
            "calibrated_test_metrics": self.calibrated_test_metrics,
            "probability_status": self.probability_status,
            "qualification_reasons": list(self.qualification_reasons),
            "drift": self.drift.to_dict(),
            "walk_forward_metrics": list(self.walk_forward_metrics),
        }
