from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


REGIMES = (
    "TREND_UP",
    "TREND_DOWN",
    "RANGE",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "BREAKOUT",
    "POST_EVENT",
    "RISK_ON",
    "RISK_OFF",
    "UNKNOWN",
)


@dataclass(frozen=True, slots=True)
class RegimeContext:
    minutes_since_high_impact_event: float | None = None
    risk_sentiment: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.minutes_since_high_impact_event is not None:
            if self.minutes_since_high_impact_event < 0:
                raise ValueError("minutes_since_high_impact_event must be >= 0")
        if self.risk_sentiment is not None:
            value = self.risk_sentiment.upper().strip()
            if value not in {"RISK_ON", "RISK_OFF"}:
                raise ValueError("risk_sentiment must be RISK_ON or RISK_OFF")
            object.__setattr__(self, "risk_sentiment", value)


@dataclass(frozen=True, slots=True)
class RegimeConfig:
    trend_adx_min: float = 25.0
    range_adx_max: float = 20.0
    high_volatility_atr_pct: float = 2.0
    low_volatility_atr_pct: float = 0.5
    post_event_minutes: float = 30.0

    def __post_init__(self) -> None:
        if self.range_adx_max > self.trend_adx_min:
            raise ValueError("range_adx_max must be <= trend_adx_min")
        if self.low_volatility_atr_pct > self.high_volatility_atr_pct:
            raise ValueError("low volatility threshold must be <= high threshold")
        if self.post_event_minutes < 0:
            raise ValueError("post_event_minutes must be >= 0")


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    regime: str
    instrument: str
    timeframe: str
    allowed_strategies: tuple[str, ...]
    evidence: dict[str, Any]

    def __post_init__(self) -> None:
        if self.regime not in REGIMES:
            raise ValueError(f"unsupported regime: {self.regime}")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["allowed_strategies"] = list(self.allowed_strategies)
        return data
