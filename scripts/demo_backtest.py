from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from services.backtesting import (
        BacktestEngine,
        chronological_split,
        load_experiment,
        walk_forward_windows,
    )

    fixture = ROOT / "data/replay/i4_backtest_dataset.json"
    experiment = load_experiment(fixture)
    report = BacktestEngine(experiment.config).run(
        experiment.bars,
        experiment.signals,
        experiment.dataset_id,
        experiment.dataset_sha256,
    )
    split = chronological_split(list(experiment.bars), train_fraction=0.75)
    windows = walk_forward_windows(list(experiment.bars), 6, 3, 3)
    output = {
        "report": report.to_dict(),
        "chronological_split": {
            "train_indices": split.train_indices,
            "test_indices": split.test_indices,
            "train_end": split.train_end.isoformat(),
            "test_start": split.test_start.isoformat(),
        },
        "walk_forward_windows": [
            {
                "window_id": window.window_id,
                "train_indices": window.train_indices,
                "test_indices": window.test_indices,
                "train_end": window.train_end.isoformat(),
                "test_start": window.test_start.isoformat(),
            }
            for window in windows
        ],
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
