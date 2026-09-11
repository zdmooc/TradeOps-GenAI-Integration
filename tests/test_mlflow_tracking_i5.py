from __future__ import annotations

from pathlib import Path

import pytest

from services.ml_signal_quality.contract import FeatureContract
from services.ml_signal_quality.dataset import load_synthetic_dataset
from services.ml_signal_quality.experiment import run_signal_quality_experiment
from services.ml_signal_quality.tracking import local_file_tracking_uri, log_and_register_mlflow


DATASET = Path(__file__).parents[1] / "data" / "ml" / "i5_signal_quality_dataset.json"


def test_mlflow_local_tracking_and_registry_smoke(tmp_path):
    pytest.importorskip("mlflow")
    contract = FeatureContract()
    records, dataset_hash, _ = load_synthetic_dataset(DATASET, contract)
    report, model = run_signal_quality_experiment(records, dataset_hash, contract)
    matrix = contract.matrix(records[-5:])
    result = log_and_register_mlflow(
        report=report,
        model=model,
        example_matrix=matrix,
        tracking_uri=local_file_tracking_uri(tmp_path / "mlruns"),
        experiment_name="i5-test-experiment",
        registered_model_name="i5-test-model",
    )
    assert result.run_id
    assert result.registered_model_name == "i5-test-model"
    assert int(result.model_version) >= 1
