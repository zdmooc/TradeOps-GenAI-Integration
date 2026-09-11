from __future__ import annotations

from services.common.observability_metrics import RISK_DECISIONS
from services.common.otel import start_span
from services.market_regime.models import RegimeSnapshot

from .models import RiskDecision, RiskLimits, RiskState, TradeIntent


CIRCUIT_BREAKER_REASONS = {
    "KILL_SWITCH_ACTIVE",
    "FEED_DEGRADED",
    "DAILY_LOSS_LIMIT",
    "MAX_CONSECUTIVE_LOSSES",
}


class RiskPolicyEngine:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def evaluate(
        self,
        intent: TradeIntent,
        state: RiskState,
        regime: RegimeSnapshot,
    ) -> RiskDecision:
        with start_span(
            "risk.evaluate",
            attributes={
                "tradeops.regime": regime.regime,
                "tradeops.strategy": intent.strategy,
            },
        ) as span:
            notional = abs(intent.entry * intent.quantity * intent.point_value)
            risk_amount = (
                abs(intent.entry - intent.stop) * intent.quantity * intent.point_value
            )
            equity = state.equity
            metrics = {
                "notional": notional,
                "risk_amount": risk_amount,
                "risk_per_trade_pct": risk_amount / equity * 100.0,
                "daily_loss_pct": max(0.0, -state.daily_pnl) / equity * 100.0,
                "gross_exposure_after_pct": (
                    state.gross_exposure + notional
                ) / equity * 100.0,
                "instrument_exposure_after_pct": (
                    state.instrument_exposure + notional
                ) / equity * 100.0,
                "correlated_exposure_after_pct": (
                    state.correlated_exposure + notional
                ) / equity * 100.0,
                "spread_bps": state.spread_bps,
                "estimated_slippage_bps": state.estimated_slippage_bps,
                "market_data_age_seconds": state.market_data_age_seconds,
                "atr_pct": state.atr_pct,
            }

            reasons: list[str] = []
            if state.manual_kill_switch:
                reasons.append("KILL_SWITCH_ACTIVE")
            if state.feed_degraded:
                reasons.append("FEED_DEGRADED")
            if metrics["daily_loss_pct"] >= self.limits.max_daily_loss_pct:
                reasons.append("DAILY_LOSS_LIMIT")
            if state.consecutive_losses >= self.limits.max_consecutive_losses:
                reasons.append("MAX_CONSECUTIVE_LOSSES")
            if metrics["risk_per_trade_pct"] > self.limits.max_risk_per_trade_pct:
                reasons.append("RISK_PER_TRADE_LIMIT")
            if metrics["gross_exposure_after_pct"] > self.limits.max_gross_exposure_pct:
                reasons.append("GROSS_EXPOSURE_LIMIT")
            if (
                metrics["instrument_exposure_after_pct"]
                > self.limits.max_instrument_exposure_pct
            ):
                reasons.append("CONCENTRATION_LIMIT")
            if (
                metrics["correlated_exposure_after_pct"]
                > self.limits.max_correlated_exposure_pct
            ):
                reasons.append("CORRELATION_LIMIT")
            if state.atr_pct > self.limits.max_atr_pct:
                reasons.append("VOLATILITY_LIMIT")
            if state.event_blocked or regime.regime == "POST_EVENT":
                reasons.append("EVENT_WINDOW_BLOCKED")
            if state.spread_bps > self.limits.max_spread_bps:
                reasons.append("SPREAD_LIMIT")
            if state.estimated_slippage_bps > self.limits.max_slippage_bps:
                reasons.append("SLIPPAGE_LIMIT")
            if state.market_data_age_seconds > self.limits.max_market_data_age_seconds:
                reasons.append("STALE_MARKET_DATA")
            if regime.regime == "UNKNOWN":
                reasons.append("UNKNOWN_REGIME")
            elif intent.strategy not in regime.allowed_strategies:
                reasons.append("STRATEGY_NOT_ALLOWED_IN_REGIME")

            unique_reasons = tuple(dict.fromkeys(reasons))
            circuit_breaker = any(
                reason in CIRCUIT_BREAKER_REASONS for reason in unique_reasons
            )
            status = "APPROVED" if not unique_reasons else "VETOED"
            RISK_DECISIONS.labels(status=status).inc()
            span.set_attribute("tradeops.risk.status", status)
            span.set_attribute("tradeops.risk.veto_reason_count", len(unique_reasons))
            span.set_attribute("tradeops.risk.circuit_breaker", circuit_breaker)
            return RiskDecision(
                approved=not unique_reasons,
                status=status,
                regime=regime.regime,
                veto_reasons=unique_reasons,
                circuit_breaker=circuit_breaker,
                metrics=metrics,
            )
