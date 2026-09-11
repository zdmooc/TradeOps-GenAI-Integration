from __future__ import annotations

from typing import Any

from services.market_regime.models import RegimeSnapshot

from .models import RiskDecision, RiskState, TradeIntent
from .policy import RiskPolicyEngine


def evaluate_payload(
    payload: dict[str, Any],
    engine: RiskPolicyEngine | None = None,
) -> RiskDecision:
    try:
        intent_raw = payload["risk_intent"]
        state_raw = payload["risk_state"]
        regime_raw = payload["regime"]
    except KeyError as exc:
        raise ValueError(f"missing I3 risk section: {exc.args[0]}") from exc

    intent = TradeIntent(**intent_raw)
    state = RiskState(**state_raw)
    regime = RegimeSnapshot(
        regime=regime_raw["regime"],
        instrument=regime_raw.get("instrument", intent.instrument),
        timeframe=regime_raw.get("timeframe", "UNKNOWN"),
        allowed_strategies=tuple(regime_raw.get("allowed_strategies", ())),
        evidence=dict(regime_raw.get("evidence", {})),
    )
    return (engine or RiskPolicyEngine()).evaluate(intent, state, regime)
