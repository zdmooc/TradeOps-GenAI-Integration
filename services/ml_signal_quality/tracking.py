from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .models import SignalQualityExperimentReport


@dataclass(frozen=True, slots=True)
class MlflowTrackingResult:
    run_id: str
    registered_model_name: str
    model_version: str


def log_and_register_mlflow(
    report: SignalQualityExperimentReport,
    model: Any,
    example_matrix: np.ndarray,
    tracking_uri: str,
    experiment_name: str = "tradeops-i5-signal-quality",
    registered_model_name: str = "tradeops-signal-quality",
) -> MlflowTrackingResult:
    import mlflow
    import mlflow.sklearn
    from mlflow import MlflowClient
    from mlflow.models import infer_signature

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    signature = infer_signature(example_matrix, model.predict_proba(example_matrix))
    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "champion_model": report.champion_model,
                "calibration_method": report.calibration_method,
                "feature_contract_version": report.feature_contract_version,
                "dataset_hash": report.dataset_hash,
                "probability_status": report.probability_status,
            }
        )
        for prefix, metrics in (
            ("raw_test", report.raw_test_metrics),
            ("calibrated_test", report.calibrated_test_metrics),
        ):
            for name, value in metrics.items():
                mlflow.log_metric(f"{prefix}.{name}", float(value))
        mlflow.log_dict(report.to_dict(), "i5-report.json")
        model_info = mlflow.sklearn.log_model(
            sk_model=model,
            name="signal-quality-model",
            signature=signature,
            input_example=example_matrix[:2],
            registered_model_name=registered_model_name,
        )
        run_id = run.info.run_id

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    versions = [
        version
        for version in client.search_model_versions(f"name='{registered_model_name}'")
        if version.run_id == run_id
    ]
    if not versions:
        raise RuntimeError("MLflow model version was not created")
    version = max(versions, key=lambda item: int(item.version))
    model_uri = getattr(model_info, "model_uri", "")
    if model_uri:
        client.set_model_version_tag(
            registered_model_name,
            version.version,
            "model_uri",
            model_uri,
        )
    client.set_model_version_tag(
        registered_model_name,
        version.version,
        "qualification",
        report.probability_status,
    )
    return MlflowTrackingResult(
        run_id=run_id,
        registered_model_name=registered_model_name,
        model_version=str(version.version),
    )


def local_file_tracking_uri(directory: str | Path) -> str:
    return Path(directory).resolve().as_uri()
