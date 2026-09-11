from __future__ import annotations

from typing import Any

import numpy as np

from .baselines import baseline_factories, positive_class_score
from .calibration import CalibratedSignalQualityModel, PlattCalibrator
from .contract import FeatureContract
from .drift import compute_drift
from .metrics import binary_classification_metrics
from .models import ModelEvaluation, SignalQualityExperimentReport, SignalQualityRecord
from .qualification import probability_qualification
from .splits import (
    slice_for,
    temporal_train_validation_calibration_test_split,
    walk_forward_ml_windows,
)


def _fit_and_score(
    model: Any,
    train_x: np.ndarray,
    train_y: np.ndarray,
    score_x: np.ndarray,
) -> np.ndarray:
    model.fit(train_x, train_y)
    return np.asarray(positive_class_score(model, score_x), dtype=float)


def run_signal_quality_experiment(
    records: list[SignalQualityRecord],
    dataset_hash: str,
    contract: FeatureContract | None = None,
    seed: int = 20260911,
) -> tuple[SignalQualityExperimentReport, CalibratedSignalQualityModel]:
    feature_contract = contract or FeatureContract()
    matrix = feature_contract.matrix(records)
    labels = feature_contract.labels(records)
    split = temporal_train_validation_calibration_test_split(len(records))

    train_x = matrix[slice_for(split.train)]
    train_y = labels[slice_for(split.train)]
    validation_x = matrix[slice_for(split.validation)]
    validation_y = labels[slice_for(split.validation)]
    calibration_x = matrix[slice_for(split.calibration)]
    calibration_y = labels[slice_for(split.calibration)]
    test_x = matrix[slice_for(split.test)]
    test_y = labels[slice_for(split.test)]

    evaluations: list[ModelEvaluation] = []
    fitted_models: dict[str, Any] = {}
    for name, factory in baseline_factories(seed).items():
        model = factory()
        validation_scores = _fit_and_score(model, train_x, train_y, validation_x)
        metrics = binary_classification_metrics(validation_y, validation_scores)
        evaluations.append(
            ModelEvaluation(
                model_name=name,
                dataset_role="VALIDATION",
                status="SCORE_UNCALIBRATED",
                metrics=metrics,
            )
        )
        fitted_models[name] = model

    evaluations.sort(
        key=lambda item: (
            item.metrics["roc_auc"],
            -item.metrics["brier"],
            item.model_name,
        ),
        reverse=True,
    )
    champion_name = evaluations[0].model_name
    champion = fitted_models[champion_name]

    calibration_raw = positive_class_score(champion, calibration_x)
    calibrator = PlattCalibrator(seed).fit(calibration_raw, calibration_y)
    test_raw = positive_class_score(champion, test_x)
    test_calibrated = calibrator.predict(test_raw)
    raw_test_metrics = binary_classification_metrics(test_y, test_raw)
    calibrated_test_metrics = binary_classification_metrics(test_y, test_calibrated)
    probability_status, reasons = probability_qualification(calibrated_test_metrics)

    drift = compute_drift(train_x, test_x, feature_contract.feature_names)
    if drift.overall_status == "ALERT":
        probability_status = "SCORE_ONLY"
        reasons = tuple((*reasons, "FEATURE_DRIFT_ALERT"))
    elif probability_status == "CALIBRATED_OUT_OF_SAMPLE" and all(
        record.source.startswith("SYNTHETIC") for record in records
    ):
        probability_status = "CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC"

    calibrated_model = CalibratedSignalQualityModel(
        base_model=champion,
        calibrator=calibrator,
        feature_names=feature_contract.feature_names,
    )

    walk_forward_metrics: list[dict[str, float]] = []
    windows = walk_forward_ml_windows(
        len(records),
        train_records=100,
        validation_records=30,
        calibration_records=30,
        test_records=30,
        step_records=30,
    )
    logistic_factory = baseline_factories(seed)["sklearn_logistic"]
    for window in windows:
        wf_model = logistic_factory()
        wf_train_x = matrix[slice_for(window.train)]
        wf_train_y = labels[slice_for(window.train)]
        wf_cal_x = matrix[slice_for(window.calibration)]
        wf_cal_y = labels[slice_for(window.calibration)]
        wf_test_x = matrix[slice_for(window.test)]
        wf_test_y = labels[slice_for(window.test)]
        wf_model.fit(wf_train_x, wf_train_y)
        wf_cal_raw = positive_class_score(wf_model, wf_cal_x)
        wf_test_raw = positive_class_score(wf_model, wf_test_x)
        calibration_valid = len(np.unique(wf_cal_y)) == 2
        if calibration_valid:
            wf_calibrator = PlattCalibrator(seed + window.window_id).fit(
                wf_cal_raw, wf_cal_y
            )
            wf_scores = wf_calibrator.predict(wf_test_raw)
        else:
            wf_scores = wf_test_raw
        metrics = binary_classification_metrics(wf_test_y, wf_scores)
        metrics["window_id"] = float(window.window_id)
        metrics["calibration_valid"] = 1.0 if calibration_valid else 0.0
        walk_forward_metrics.append(metrics)

    report = SignalQualityExperimentReport(
        experiment_id="i5-signal-quality-v1",
        dataset_hash=dataset_hash,
        feature_contract_version=feature_contract.version,
        feature_names=feature_contract.feature_names,
        split=split,
        baseline_validation=tuple(evaluations),
        champion_model=champion_name,
        calibration_method="PLATT_LOGISTIC",
        raw_test_metrics=raw_test_metrics,
        calibrated_test_metrics=calibrated_test_metrics,
        probability_status=probability_status,
        qualification_reasons=reasons,
        drift=drift,
        walk_forward_metrics=tuple(walk_forward_metrics),
    )
    return report, calibrated_model
