from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.technical_analysis.engine import TechnicalAnalysisEngine
from services.technical_analysis.models import Bar


def _scenario_bars(payload: dict, scenario: dict) -> list[Bar]:
    base = datetime.fromisoformat(payload["base_time"].replace("Z", "+00:00"))
    rows: list[Bar] = []
    for i, (open_, high, low, close, volume) in enumerate(scenario["ohlcv"]):
        rows.append(
            Bar(
                instrument=payload["instrument"],
                timeframe=payload["timeframe"],
                start_time=base + timedelta(minutes=i),
                end_time=base + timedelta(minutes=i + 1),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                source="I2_FIXTURE",
            )
        )
    return rows


def main() -> None:
    payload = json.loads(Path("data/replay/i2_labelled_patterns.json").read_text())
    engine = TechnicalAnalysisEngine()
    for scenario in payload["scenarios"]:
        analysis = engine.analyze(_scenario_bars(payload, scenario))
        matched = any(
            p.pattern == scenario["expected_pattern"]
            and p.direction == scenario["expected_direction"]
            for p in analysis.patterns
        )
        print(
            f"{scenario['name']}: expected={scenario['expected_pattern']}/"
            f"{scenario['expected_direction']} matched={matched} "
            f"trend={analysis.structure.trend}"
        )


if __name__ == "__main__":
    main()
