from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class Bar:
    instrument: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    source: str = "CANONICAL"
    complete: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrument", self.instrument.upper().strip())
        object.__setattr__(self, "timeframe", self.timeframe.upper().strip())
        object.__setattr__(self, "source", self.source.upper().strip())
        object.__setattr__(self, "start_time", _utc(self.start_time))
        object.__setattr__(self, "end_time", _utc(self.end_time))
        values = (self.open, self.high, self.low, self.close, self.volume)
        if not all(isfinite(float(v)) for v in values):
            raise ValueError("bar values must be finite")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC envelope is inconsistent")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.volume < 0:
            raise ValueError("volume must be >= 0")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3.0

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("start_time", "end_time"):
            data[key] = data[key].isoformat().replace("+00:00", "Z")
        return data


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    ema_fast: float | None = None
    ema_slow: float | None = None
    vwap: float | None = None
    atr: float | None = None
    adx: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    bb_middle: float | None = None
    bb_upper: float | None = None
    bb_lower: float | None = None


@dataclass(frozen=True, slots=True)
class SwingPoint:
    index: int
    time: datetime
    price: float
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class MarketStructure:
    trend: str
    swings: tuple[SwingPoint, ...]
    last_swing_high: SwingPoint | None = None
    last_swing_low: SwingPoint | None = None


@dataclass(frozen=True, slots=True)
class PatternSignal:
    pattern: str
    direction: str
    timeframe: str
    detected_at: datetime
    entry_reference: float
    invalidation: float
    preconditions: tuple[str, ...]
    invalidation_rule: str
    evidence: dict[str, Any]
    lookback: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["detected_at"] = self.detected_at.isoformat().replace("+00:00", "Z")
        return data


@dataclass(frozen=True, slots=True)
class TechnicalAnalysis:
    instrument: str
    timeframe: str
    as_of: datetime
    indicators: IndicatorSnapshot
    structure: MarketStructure
    patterns: tuple[PatternSignal, ...]
