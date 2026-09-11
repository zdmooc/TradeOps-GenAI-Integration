from dataclasses import replace
from datetime import UTC, datetime

import pytest

from services.market_regime.engine import MarketRegimeEngine
from services.market_regime.models import RegimeContext, RegimeSnapshot
from services.risk_engine.adapter import evaluate_payload
from services.risk_engine.models import RiskLimits, RiskState, TradeIntent
from services.risk_engine.policy import RiskPolicyEngine
from services.technical_analysis.models import (
    IndicatorSnapshot,
    MarketStructure,
    PatternSignal,
    TechnicalAnalysis,
)


NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def analysis(*, trend="BULLISH", adx=30.0, atr=1.0, patterns=()):
    return TechnicalAnalysis(
        instrument="IX.D.DAX.IFM.IP",
        timeframe="M5",
        as_of=NOW,
        indicators=IndicatorSnapshot(adx=adx, atr=atr),
        structure=MarketStructure(trend=trend, swings=()),
        patterns=patterns,
    )


def pattern(name="BREAKOUT_RETEST"):
    return PatternSignal(
        pattern=name,
        direction="LONG",
        timeframe="M5",
        detected_at=NOW,
        entry_reference=100.0,
        invalidation=99.0,
        preconditions=("rule",),
        invalidation_rule="close below level",
        evidence={"level": 100.0},
        lookback=20,
    )


def regime(name="TREND_UP", allowed=("PULLBACK",)):
    return RegimeSnapshot(
        regime=name,
        instrument="IX.D.DAX.IFM.IP",
        timeframe="M5",
        allowed_strategies=allowed,
        evidence={},
    )


def intent(**changes):
    base = TradeIntent(
        instrument="IX.D.DAX.IFM.IP",
        side="LONG",
        strategy="PULLBACK",
        entry=100.0,
        stop=99.5,
        quantity=10.0,
    )
    return replace(base, **changes)


def state(**changes):
    return replace(RiskState(equity=100_000.0), **changes)


def test_regime_trend_up_and_down():
    engine = MarketRegimeEngine()
    assert engine.classify(analysis(), last_price=100.0).regime == "TREND_UP"
    assert engine.classify(
        analysis(trend="BEARISH"), last_price=100.0
    ).regime == "TREND_DOWN"


def test_regime_range_high_and_low_volatility():
    engine = MarketRegimeEngine()
    assert engine.classify(
        analysis(trend="RANGE", adx=15, atr=1.0), last_price=100.0
    ).regime == "RANGE"
    assert engine.classify(
        analysis(adx=30, atr=3.0), last_price=100.0
    ).regime == "HIGH_VOLATILITY"
    assert engine.classify(
        analysis(adx=30, atr=0.4), last_price=100.0
    ).regime == "LOW_VOLATILITY"


def test_regime_breakout_post_event_and_sentiment_precedence():
    engine = MarketRegimeEngine()
    breakout = analysis(patterns=(pattern(),))
    assert engine.classify(breakout, last_price=100.0).regime == "BREAKOUT"
    risk_off = engine.classify(
        breakout,
        last_price=100.0,
        context=RegimeContext(risk_sentiment="risk_off"),
    )
    assert risk_off.regime == "RISK_OFF"
    post_event = engine.classify(
        breakout,
        last_price=100.0,
        context=RegimeContext(
            risk_sentiment="risk_on",
            minutes_since_high_impact_event=10,
        ),
    )
    assert post_event.regime == "POST_EVENT"


def test_unknown_regime_when_evidence_is_insufficient():
    result = MarketRegimeEngine().classify(
        analysis(trend="UNKNOWN", adx=None, atr=None),
        last_price=100.0,
    )
    assert result.regime == "UNKNOWN"
    assert result.allowed_strategies == ()


def test_safe_trade_is_approved_and_metrics_are_deterministic():
    engine = RiskPolicyEngine()
    decision = engine.evaluate(intent(), state(), regime())
    assert decision.approved
    assert decision.veto_reasons == ()
    assert decision.metrics["risk_per_trade_pct"] == pytest.approx(0.005)
    assert decision == engine.evaluate(intent(), state(), regime())


@pytest.mark.parametrize(
    ("state_changes", "reason"),
    [
        ({"daily_pnl": -3_000.0}, "DAILY_LOSS_LIMIT"),
        ({"gross_exposure": 300_000.0}, "GROSS_EXPOSURE_LIMIT"),
        ({"instrument_exposure": 25_000.0}, "CONCENTRATION_LIMIT"),
        ({"correlated_exposure": 50_000.0}, "CORRELATION_LIMIT"),
        ({"atr_pct": 3.1}, "VOLATILITY_LIMIT"),
        ({"event_blocked": True}, "EVENT_WINDOW_BLOCKED"),
        ({"spread_bps": 15.1}, "SPREAD_LIMIT"),
        ({"estimated_slippage_bps": 10.1}, "SLIPPAGE_LIMIT"),
        ({"market_data_age_seconds": 5.1}, "STALE_MARKET_DATA"),
    ],
)
def test_market_and_portfolio_gates_veto(state_changes, reason):
    decision = RiskPolicyEngine().evaluate(intent(), state(**state_changes), regime())
    assert not decision.approved
    assert reason in decision.veto_reasons


def test_risk_per_trade_gate_vetoes_large_stop_distance():
    trade = intent(stop=80.0, quantity=100.0)
    decision = RiskPolicyEngine().evaluate(trade, state(), regime())
    assert "RISK_PER_TRADE_LIMIT" in decision.veto_reasons


def test_strategy_allowlist_and_unknown_regime_are_fail_closed():
    policy = RiskPolicyEngine()
    blocked = policy.evaluate(
        intent(strategy="MEAN_REVERSION"),
        state(),
        regime("TREND_UP", ("PULLBACK",)),
    )
    assert "STRATEGY_NOT_ALLOWED_IN_REGIME" in blocked.veto_reasons
    unknown = policy.evaluate(intent(), state(), regime("UNKNOWN", ()))
    assert "UNKNOWN_REGIME" in unknown.veto_reasons


def test_post_event_regime_is_blocked_even_if_state_flag_is_false():
    decision = RiskPolicyEngine().evaluate(
        intent(strategy="BREAKOUT"), state(), regime("POST_EVENT", ())
    )
    assert "EVENT_WINDOW_BLOCKED" in decision.veto_reasons


def test_circuit_breakers_are_explicit_and_aggregate_reasons():
    broken = state(
        manual_kill_switch=True,
        feed_degraded=True,
        daily_pnl=-4_000.0,
        consecutive_losses=3,
    )
    decision = RiskPolicyEngine().evaluate(intent(), broken, regime())
    assert decision.circuit_breaker
    assert {
        "KILL_SWITCH_ACTIVE",
        "FEED_DEGRADED",
        "DAILY_LOSS_LIMIT",
        "MAX_CONSECUTIVE_LOSSES",
    }.issubset(decision.veto_reasons)


def test_custom_limits_are_honored():
    limits = RiskLimits(max_spread_bps=2.0)
    decision = RiskPolicyEngine(limits).evaluate(
        intent(), state(spread_bps=2.1), regime()
    )
    assert decision.veto_reasons == ("SPREAD_LIMIT",)


def test_trade_intent_side_stop_invariants():
    with pytest.raises(ValueError):
        intent(stop=101.0)
    with pytest.raises(ValueError):
        intent(side="SHORT", stop=99.0)


def test_payload_adapter_requires_explicit_i3_context():
    with pytest.raises(ValueError, match="risk_state"):
        evaluate_payload(
            {
                "risk_intent": {
                    "instrument": "DAX",
                    "side": "LONG",
                    "strategy": "PULLBACK",
                    "entry": 100,
                    "stop": 99,
                    "quantity": 1,
                }
            }
        )


def test_payload_adapter_evaluates_structured_event():
    payload = {
        "risk_intent": {
            "instrument": "DAX",
            "side": "LONG",
            "strategy": "PULLBACK",
            "entry": 100,
            "stop": 99,
            "quantity": 1,
        },
        "risk_state": {"equity": 100000},
        "regime": {
            "regime": "TREND_UP",
            "allowed_strategies": ["PULLBACK"],
            "timeframe": "M5",
        },
    }
    assert evaluate_payload(payload).approved
