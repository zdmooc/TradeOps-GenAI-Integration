from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from services.ml_signal_quality import FeatureContract, load_synthetic_dataset
    from services.ml_signal_quality.experiment import run_signal_quality_experiment
    from services.ml_signal_quality.tracking import (
        local_file_tracking_uri,
        log_and_register_mlflow,
    )

    parser = argparse.ArgumentParser(description="Run I5 signal-quality experiment")
    parser.add_argument(
        "--dataset",
        default=str(ROOT / "data" / "ml" / "i5_signal_quality_dataset.json"),
    )
    parser.add_argument("--track", action="store_true", help="log/register to local MLflow")
    parser.add_argument(
        "--mlflow-dir",
        default=str(ROOT / ".mlruns-i5"),
        help="local MLflow store used only with --track",
    )
    args = parser.parse_args()

    contract = FeatureContract()
    records, dataset_hash, _ = load_synthetic_dataset(args.dataset, contract)
    report, model = run_signal_quality_experiment(records, dataset_hash, contract)
    output = report.to_dict()
    if args.track:
        matrix = contract.matrix(records[-5:])
        tracked = log_and_register_mlflow(
            report,
            model,
            matrix,
            tracking_uri=local_file_tracking_uri(args.mlflow_dir),
        )
        output["mlflow"] = {
            "run_id": tracked.run_id,
            "registered_model_name": tracked.registered_model_name,
            "model_version": tracked.model_version,
        }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
