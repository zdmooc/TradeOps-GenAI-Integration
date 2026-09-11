from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from services.ml_signal_quality.baselines import baseline_factories
from services.ml_signal_quality.calibration import PlattCalibrator
from services.ml_signal_quality.contract import DEFAULT_FEATURE_NAMES, FeatureContract
from services.ml_signal_quality.dataset import canonical_dataset_hash, load_synthetic_dataset
from services.ml_signal_quality.drift import compute_drift
from services.ml_signal_quality.experiment import run_signal_quality_experiment
from services.ml_signal_quality.metrics import binary_classification_metrics
from services.ml_signal_quality.models import SignalQualityRecord
from services.ml_signal_quality.qualification import probability_qualification
from services.ml_signal_quality.splits import (
    temporal_train_validation_calibration_test_split,
    walk_forward_ml_windows,
)


DATASET = Path(__file__).parents[1] / "data" / "ml" / "i5_signal_quality_dataset.json"


@pytest.fixture(scope="module")
def dataset_bundle():
    contract = FeatureContract()
    records, dataset_hash, _ = load_synthetic_dataset(DATASET, contract)
    return contract, records, dataset_hash


@pytest.fixture(scope="module")
def experiment_bundle(dataset_bundle):
    contract, records, dataset_hash = dataset_bundle
    return run_signal_quality_experiment(records, dataset_hash, contract)


def test_dataset_contract_and_hash_are_stable(dataset_bundle):
    contract, records, dataset_hash = dataset_bundle
    assert len(records) == 480
    assert len(dataset_hash) == 64
    assert canonical_dataset_hash(records) == dataset_hash
    assert tuple(records[0].features) == contract.feature_names
    assert contract.matrix(records).shape == (480, len(DEFAULT_FEATURE_NAMES))


def test_feature_contract_rejects_target_leakage():
    with pytest.raises(ValueError, match="leakage-prone"):
        FeatureContract(feature_names=("rsi", "future_pnl")).validate_feature_names()


def test_record_rejects_label_at_feature_time():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="label_time"):
        SignalQualityRecord(
            record_id="bad",
            feature_time=now,
            label_time=now,
            features={"rsi": 50.0},
            label=1,
        )


def test_four_way_temporal_split_is_disjoint():
    split = temporal_train_validation_calibration_test_split(480)
    assert split.train == (0, 239)
    assert split.validation == (240, 335)
    assert split.calibration == (336, 407)
    assert split.test == (408, 479)
    assert split.train[1] < split.validation[0] < split.calibration[0] < split.test[0]


def test_walk_forward_windows_keep_future_data_out_of_training():
    windows = walk_forward_ml_windows(480, 100, 30, 30, 30, step_records=30)
    assert len(windows) == 10
    for window in windows:
        assert window.train[1] < window.validation[0]
        assert window.validation[1] < window.calibration[0]
        assert window.calibration[1] < window.test[0]


def test_baselines_include_sklearn_xgboost_and_lightgbm():
    names = set(baseline_factories())
    assert names == {
        "sklearn_logistic",
        "sklearn_hist_gradient_boosting",
        "xgboost",
        "lightgbm",
    }


def test_platt_calibrator_requires_two_classes():
    with pytest.raises(ValueError, match="both classes"):
        PlattCalibrator().fit(np.asarray([0.2, 0.4]), np.asarray([1, 1]))


def test_metric_output_is_bounded():
    metrics = binary_classification_metrics(
        np.asarray([0, 0, 1, 1]), np.asarray([0.1, 0.2, 0.8, 0.9])
    )
    assert metrics["roc_auc"] == 1.0
    assert 0.0 <= metrics["brier"] <= 1.0
    assert 0.0 <= metrics["ece"] <= 1.0


def test_drift_same_population_is_ok(dataset_bundle):
    contract, records, _ = dataset_bundle
    matrix = contract.matrix(records[:100])
    report = compute_drift(matrix, matrix.copy(), contract.feature_names)
    assert report.overall_status == "OK"
    assert report.max_psi == pytest.approx(0.0)


def test_drift_detects_shift(dataset_bundle):
    contract, records, _ = dataset_bundle
    matrix = contract.matrix(records[:100])
    shifted = matrix.copy()
    shifted[:, 0] += 40.0
    report = compute_drift(matrix, shifted, contract.feature_names)
    assert report.overall_status == "ALERT"
    assert report.features[0].status == "ALERT"


def test_experiment_runs_all_baselines_and_keeps_raw_output_as_score(experiment_bundle):
    report, _ = experiment_bundle
    assert len(report.baseline_validation) == 4
    assert all(item.status == "SCORE_UNCALIBRATED" for item in report.baseline_validation)
    assert report.champion_model in baseline_factories()
    assert report.calibration_method == "PLATT_LOGISTIC"


def test_calibrated_test_is_strictly_out_of_sample(experiment_bundle):
    report, _ = experiment_bundle
    assert report.split.calibration[1] < report.split.test[0]
    assert report.calibrated_test_metrics["n"] == 72.0
    assert report.raw_test_metrics["n"] == 72.0


def test_probability_status_is_guarded_by_qualification(experiment_bundle):
    report, _ = experiment_bundle
    status, reasons = probability_qualification(report.calibrated_test_metrics)
    assert status == "CALIBRATED_OUT_OF_SAMPLE"
    assert reasons == ()
    assert report.probability_status == "CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC"
    assert report.qualification_reasons == ()


def test_calibrated_model_outputs_probabilities(experiment_bundle, dataset_bundle):
    _, model = experiment_bundle
    contract, records, _ = dataset_bundle
    matrix = contract.matrix(records[-5:])
    probabilities = model.predict_proba(matrix)
    assert probabilities.shape == (5, 2)
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)
    assert np.allclose(probabilities.sum(axis=1), 1.0)


def test_experiment_is_deterministic(dataset_bundle, experiment_bundle):
    contract, records, dataset_hash = dataset_bundle
    first, _ = experiment_bundle
    second, _ = run_signal_quality_experiment(records, dataset_hash, contract)
    assert first.champion_model == second.champion_model
    assert first.probability_status == second.probability_status
    assert first.calibrated_test_metrics == pytest.approx(second.calibrated_test_metrics)


def test_walk_forward_metrics_are_out_of_sample(experiment_bundle):
    report, _ = experiment_bundle
    assert len(report.walk_forward_metrics) == 10
    for metrics in report.walk_forward_metrics:
        assert metrics["n"] == 30.0
        assert 0.0 <= metrics["brier"] <= 1.0


def test_probability_qualification_rejects_tiny_sample():
    metrics = {
        "n": 10.0,
        "positive_rate": 0.5,
        "brier": 0.1,
        "ece": 0.05,
        "roc_auc": 0.8,
    }
    status, reasons = probability_qualification(metrics)
    assert status == "SCORE_ONLY"
    assert "INSUFFICIENT_TEST_SAMPLE" in reasons


def test_labels_occur_after_features(dataset_bundle):
    _, records, _ = dataset_bundle
    assert all(record.label_time > record.feature_time for record in records)
    minimum_delay = min(record.label_time - record.feature_time for record in records)
    assert minimum_delay == timedelta(minutes=30)
