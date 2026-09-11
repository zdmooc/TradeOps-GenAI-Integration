from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.risk_engine.adapter import evaluate_payload


FIXTURE = ROOT / "data" / "replay" / "i3_risk_scenarios.json"


def main() -> None:
    scenarios = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for scenario in scenarios:
        decision = evaluate_payload(scenario)
        expected = scenario["expected_status"]
        print(
            f"{scenario['name']}: status={decision.status} "
            f"expected={expected} vetoes={list(decision.veto_reasons)}"
        )
        if decision.status != expected:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
