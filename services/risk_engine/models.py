from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class TradeIntent:
    instrument: str
    side: str
    strategy: str
    entry: float
    stop: float
    quantity: float
    point_value: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrument", self.instrument.upper().strip())
        object.__setattr__(self, "side", self.side.upper().strip())
        object.__setattr__(self, "strategy", self.strategy.upper().strip())
        values = (self.entry, self.stop, self.quantity, self.point_value)
        if not all(isfinite(float(value)) for value in values):
            raise ValueError("trade intent values must be finite")
        if self.side not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        if self.entry <= 0 or self.stop <= 0:
            raise ValueError("entry and stop must be > 0")
        if self.quantity <= 0 or self.point_value <= 0:
            raise ValueError("quantity and point_value must be > 0")
        if self.side == "LONG" and self.stop >= self.entry:
            raise ValueError("LONG stop must be below entry")
        if self.side == "SHORT" and self.stop <= self.entry:
            raise ValueError("SHORT stop must be above entry")


@dataclass(frozen=True, slots=True)
class RiskState:
    equity: float
    daily_pnl: float = 0.0
    gross_exposure: float = 0.0
    instrument_exposure: float = 0.0
    correlated_exposure: float = 0.0
    spread_bps: float = 0.0
    estimated_slippage_bps: float = 0.0
    market_data_age_seconds: float = 0.0
    atr_pct: float = 0.0
    event_blocked: bool = False
    consecutive_losses: int = 0
    manual_kill_switch: bool = False
    feed_degraded: bool = False

    def __post_init__(self) -> None:
        values = (
            self.equity,
            self.daily_pnl,
            self.gross_exposure,
            self.instrument_exposure,
            self.correlated_exposure,
            self.spread_bps,
            self.estimated_slippage_bps,
            self.market_data_age_seconds,
            self.atr_pct,
        )
        if not all(isfinite(float(value)) for value in values):
            raise ValueError("risk state values must be finite")
        if self.equity <= 0:
            raise ValueError("equity must be > 0")
        non_negative = values[2:]
        if any(value < 0 for value in non_negative):
            raise ValueError("risk state magnitudes must be >= 0")
        if self.consecutive_losses < 0:
            raise ValueError("consecutive_losses must be >= 0")


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_gross_exposure_pct: float = 300.0
    max_instrument_exposure_pct: float = 25.0
    max_correlated_exposure_pct: float = 50.0
    max_spread_bps: float = 15.0
    max_slippage_bps: float = 10.0
    max_market_data_age_seconds: float = 5.0
    max_atr_pct: float = 3.0
    max_consecutive_losses: int = 3

    def __post_init__(self) -> None:
        numeric_limits = (
            self.max_risk_per_trade_pct,
            self.max_daily_loss_pct,
            self.max_gross_exposure_pct,
            self.max_instrument_exposure_pct,
            self.max_correlated_exposure_pct,
            self.max_spread_bps,
            self.max_slippage_bps,
            self.max_market_data_age_seconds,
            self.max_atr_pct,
        )
        if any(value < 0 for value in numeric_limits):
            raise ValueError("risk limits must be >= 0")
        if self.max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be >= 1")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    approved: bool
    status: str
    regime: str
    veto_reasons: tuple[str, ...]
    circuit_breaker: bool
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["veto_reasons"] = list(self.veto_reasons)
        return data
