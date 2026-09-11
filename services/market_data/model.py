from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any
from uuid import uuid4


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return _aware_utc(value)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for fmt in (None, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"unsupported timestamp: {value}")


@dataclass(frozen=True, slots=True)
class MarketEvent:
    instrument: str
    event_time: datetime
    ingest_time: datetime
    source: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    market_status: str = "UNKNOWN"
    event_type: str = "TICK"
    resolution: str | None = None
    source_sequence: str | None = None
    latency_ms: float | None = None
    stale: bool = False
    event_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrument", self.instrument.upper().strip())
        object.__setattr__(self, "source", self.source.upper().strip())
        object.__setattr__(self, "event_time", _aware_utc(self.event_time))
        object.__setattr__(self, "ingest_time", _aware_utc(self.ingest_time))
        if not self.instrument:
            raise ValueError("instrument is required")
        if not self.source:
            raise ValueError("source is required")
        for name in ("bid", "ask", "last"):
            value = getattr(self, name)
            if value is not None and (not isfinite(float(value)) or float(value) < 0):
                raise ValueError(f"{name} must be a finite non-negative number")

    @property
    def spread(self) -> float | None:
        if self.bid is None or self.ask is None:
            return None
        return self.ask - self.bid

    @property
    def midpoint(self) -> float | None:
        if self.bid is None or self.ask is None:
            return self.last
        return (self.bid + self.ask) / 2.0

    def dedup_key(self) -> tuple[Any, ...]:
        return (
            self.source,
            self.instrument,
            self.event_type,
            self.resolution,
            self.event_time.isoformat(),
            self.bid,
            self.ask,
            self.last,
            self.source_sequence,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_time"] = self.event_time.isoformat().replace("+00:00", "Z")
        data["ingest_time"] = self.ingest_time.isoformat().replace("+00:00", "Z")
        data["spread"] = self.spread
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarketEvent":
        payload = dict(data)
        payload.pop("spread", None)
        payload["event_time"] = parse_utc(payload["event_time"])
        payload["ingest_time"] = parse_utc(payload["ingest_time"])
        return cls(**payload)
