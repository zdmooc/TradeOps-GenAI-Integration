from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_equity: float = 10_000.0
    spread_bps: float = 2.0
    slippage_bps: float = 1.0
    commission_per_order: float = 0.50
    ambiguity_policy: str = "STOP_FIRST"

    def __post_init__(self) -> None:
        numeric = (
            self.initial_equity,
            self.spread_bps,
            self.slippage_bps,
            self.commission_per_order,
        )
        if not all(isfinite(float(value)) for value in numeric):
            raise ValueError("backtest config values must be finite")
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be > 0")
        if any(value < 0 for value in numeric[1:]):
            raise ValueError("cost assumptions must be >= 0")
        policy = self.ambiguity_policy.upper().strip()
        if policy not in {"STOP_FIRST", "TARGET_FIRST"}:
            raise ValueError("ambiguity_policy must be STOP_FIRST or TARGET_FIRST")
        object.__setattr__(self, "ambiguity_policy", policy)


@dataclass(frozen=True, slots=True)
class BacktestSignal:
    signal_id: str
    instrument: str
    side: str
    generated_at: datetime
    stop: float
    target: float
    quantity: float
    point_value: float = 1.0
    pattern: str = "UNSPECIFIED"
    regime: str = "UNKNOWN"
    session: str = "UNSPECIFIED"
    timeframe: str = "M1"
    risk_status: str = "APPROVED"

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrument", self.instrument.upper().strip())
        object.__setattr__(self, "side", self.side.upper().strip())
        object.__setattr__(self, "pattern", self.pattern.upper().strip())
        object.__setattr__(self, "regime", self.regime.upper().strip())
        object.__setattr__(self, "session", self.session.upper().strip())
        object.__setattr__(self, "timeframe", self.timeframe.upper().strip())
        object.__setattr__(self, "risk_status", self.risk_status.upper().strip())
        object.__setattr__(self, "generated_at", _utc(self.generated_at))
        numeric = (self.stop, self.target, self.quantity, self.point_value)
        if not self.signal_id.strip():
            raise ValueError("signal_id is required")
        if self.side not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        if not all(isfinite(float(value)) for value in numeric):
            raise ValueError("signal values must be finite")
        if self.stop <= 0 or self.target <= 0:
            raise ValueError("stop and target must be > 0")
        if self.quantity <= 0 or self.point_value <= 0:
            raise ValueError("quantity and point_value must be > 0")
        if self.side == "LONG" and self.stop >= self.target:
            raise ValueError("LONG stop must be below target")
        if self.side == "SHORT" and self.stop <= self.target:
            raise ValueError("SHORT stop must be above target")


@dataclass(frozen=True, slots=True)
class TradeResult:
    signal_id: str
    instrument: str
    side: str
    pattern: str
    regime: str
    session: str
    timeframe: str
    entry_time: datetime
    exit_time: datetime
    entry_reference: float
    entry_fill: float
    exit_reference: float
    exit_fill: float
    quantity: float
    point_value: float
    pnl: float
    r_multiple: float
    mfe_r: float
    mae_r: float
    exit_reason: str
    bars_held: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("entry_time", "exit_time"):
            data[key] = data[key].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return data


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    trade_count: int
    win_rate_pct: float
    total_pnl: float
    average_pnl: float
    average_r: float
    expectancy_r: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    max_drawdown: float
    max_drawdown_pct: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BacktestReport:
    dataset_id: str
    dataset_sha256: str
    config_sha256: str
    trades: tuple[TradeResult, ...]
    skipped_signals: tuple[str, ...]
    metrics: PerformanceMetrics
    breakdowns: dict[str, dict[str, PerformanceMetrics]]
    baseline: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_sha256": self.dataset_sha256,
            "config_sha256": self.config_sha256,
            "trades": [trade.to_dict() for trade in self.trades],
            "skipped_signals": list(self.skipped_signals),
            "metrics": self.metrics.to_dict(),
            "breakdowns": {
                dimension: {key: value.to_dict() for key, value in groups.items()}
                for dimension, groups in self.breakdowns.items()
            },
            "baseline": dict(self.baseline),
        }
