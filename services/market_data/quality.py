from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .model import MarketEvent


class QualityReason(str, Enum):
    DUPLICATE = "DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    STALE = "STALE"
    BAD_SPREAD = "BAD_SPREAD"
    MISSING_PRICE = "MISSING_PRICE"
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"


@dataclass(frozen=True)
class QualityDecision:
    accepted: bool
    reasons: tuple[QualityReason, ...] = ()
    stale: bool = False


@dataclass
class DataQualityEngine:
    stale_after: timedelta = timedelta(seconds=5)
    max_out_of_order: timedelta = timedelta(milliseconds=250)
    max_future_skew: timedelta = timedelta(seconds=2)
    max_spread: float | None = None
    _seen: set[tuple] = field(default_factory=set, init=False)
    _latest: dict[tuple[str, str], datetime] = field(default_factory=dict, init=False)

    def evaluate(
        self,
        event: MarketEvent,
        *,
        now: datetime,
        check_stale: bool = True,
    ) -> QualityDecision:
        reasons: list[QualityReason] = []
        key = event.dedup_key()
        stream_key = (event.source, event.instrument)

        if key in self._seen:
            reasons.append(QualityReason.DUPLICATE)

        latest = self._latest.get(stream_key)
        if latest is not None and event.event_time < latest - self.max_out_of_order:
            reasons.append(QualityReason.OUT_OF_ORDER)

        if event.event_time > now + self.max_future_skew:
            reasons.append(QualityReason.FUTURE_TIMESTAMP)

        stale = check_stale and (now - event.event_time > self.stale_after)
        if stale:
            reasons.append(QualityReason.STALE)

        if event.bid is None and event.ask is None and event.last is None:
            reasons.append(QualityReason.MISSING_PRICE)

        spread = event.spread
        if spread is not None:
            if spread < 0 or (self.max_spread is not None and spread > self.max_spread):
                reasons.append(QualityReason.BAD_SPREAD)

        accepted = not reasons
        if accepted:
            self._seen.add(key)
            if latest is None or event.event_time > latest:
                self._latest[stream_key] = event.event_time
        return QualityDecision(accepted=accepted, reasons=tuple(reasons), stale=stale)

    def reset(self) -> None:
        self._seen.clear()
        self._latest.clear()
