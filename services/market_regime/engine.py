from __future__ import annotations

from services.technical_analysis.models import TechnicalAnalysis

from .models import RegimeConfig, RegimeContext, RegimeSnapshot


DEFAULT_STRATEGY_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "TREND_UP": ("BREAKOUT", "PULLBACK", "TREND_FOLLOW"),
    "TREND_DOWN": ("BREAKOUT", "PULLBACK", "TREND_FOLLOW"),
    "RANGE": ("MEAN_REVERSION", "SUPPORT_RESISTANCE"),
    "HIGH_VOLATILITY": ("BREAKOUT",),
    "LOW_VOLATILITY": ("COMPRESSION", "MEAN_REVERSION"),
    "BREAKOUT": ("BREAKOUT", "RETEST"),
    "POST_EVENT": (),
    "RISK_ON": ("BREAKOUT", "PULLBACK", "TREND_FOLLOW"),
    "RISK_OFF": ("BREAKOUT", "DEFENSIVE_SHORT"),
    "UNKNOWN": (),
}


class MarketRegimeEngine:
    def __init__(
        self,
        config: RegimeConfig | None = None,
        strategy_allowlist: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.config = config or RegimeConfig()
        self.strategy_allowlist = strategy_allowlist or DEFAULT_STRATEGY_ALLOWLIST

    def classify(
        self,
        analysis: TechnicalAnalysis,
        *,
        last_price: float,
        context: RegimeContext | None = None,
    ) -> RegimeSnapshot:
        if last_price <= 0:
            raise ValueError("last_price must be > 0")
        ctx = context or RegimeContext()
        indicators = analysis.indicators
        atr_pct = (
            indicators.atr / last_price * 100.0
            if indicators.atr is not None
            else None
        )
        breakout_patterns = {"BREAKOUT_RETEST", "COMPRESSION_EXPANSION"}
        breakout = any(pattern.pattern in breakout_patterns for pattern in analysis.patterns)
        evidence = {
            "structure": analysis.structure.trend,
            "adx": indicators.adx,
            "atr_pct": atr_pct,
            "breakout_pattern": breakout,
            "risk_sentiment": ctx.risk_sentiment,
            "minutes_since_high_impact_event": ctx.minutes_since_high_impact_event,
        }

        if (
            ctx.minutes_since_high_impact_event is not None
            and ctx.minutes_since_high_impact_event <= self.config.post_event_minutes
        ):
            regime = "POST_EVENT"
        elif ctx.risk_sentiment in {"RISK_ON", "RISK_OFF"}:
            regime = ctx.risk_sentiment
        elif breakout:
            regime = "BREAKOUT"
        elif atr_pct is not None and atr_pct >= self.config.high_volatility_atr_pct:
            regime = "HIGH_VOLATILITY"
        elif atr_pct is not None and atr_pct <= self.config.low_volatility_atr_pct:
            regime = "LOW_VOLATILITY"
        elif (
            analysis.structure.trend == "BULLISH"
            and indicators.adx is not None
            and indicators.adx >= self.config.trend_adx_min
        ):
            regime = "TREND_UP"
        elif (
            analysis.structure.trend == "BEARISH"
            and indicators.adx is not None
            and indicators.adx >= self.config.trend_adx_min
        ):
            regime = "TREND_DOWN"
        elif (
            analysis.structure.trend == "RANGE"
            or (indicators.adx is not None and indicators.adx <= self.config.range_adx_max)
        ):
            regime = "RANGE"
        else:
            regime = "UNKNOWN"

        return RegimeSnapshot(
            regime=regime,
            instrument=analysis.instrument,
            timeframe=analysis.timeframe,
            allowed_strategies=tuple(self.strategy_allowlist.get(regime, ())),
            evidence=evidence,
        )
