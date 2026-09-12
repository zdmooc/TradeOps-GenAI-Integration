from __future__ import annotations

import hashlib
from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from services.market_data.model import MarketEvent


@dataclass(frozen=True)
class ClosedPaperShadowOutcome:
    signal_id: str
    mode: str
    source: str
    state: str
    observed_at: str
    closed_at: str
    realized_r: float
    evidence_ref: str
    instrument: str
    strategy: str
    direction: str
    entry_price: float
    exit_price: float
    risk_unit: float
    horizon_bars: int

    def to_dict(self) -> dict[str, object]:
        return {
            "signal_id": self.signal_id,
            "mode": self.mode,
            "source": self.source,
            "state": self.state,
            "observed_at": self.observed_at,
            "closed_at": self.closed_at,
            "realized_r": self.realized_r,
            "evidence_ref": self.evidence_ref,
            "instrument": self.instrument,
            "strategy": self.strategy,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "risk_unit": self.risk_unit,
            "horizon_bars": self.horizon_bars,
        }


def _iso(event: MarketEvent) -> str:
    return event.event_time.isoformat().replace("+00:00", "Z")


def _price(event: MarketEvent) -> float:
    if event.midpoint is not None:
        return float(event.midpoint)
    if event.last is not None:
        return float(event.last)
    close = event.metadata.get("close")
    if isinstance(close, (int, float)):
        return float(close)
    if isinstance(close, dict):
        bid = close.get("bid")
        ask = close.get("ask")
        if bid is not None and ask is not None:
            return (float(bid) + float(ask)) / 2.0
        if bid is not None:
            return float(bid)
        if ask is not None:
            return float(ask)
    raise ValueError(f"event {event.event_id} has no usable close price")


def _bar_range(event: MarketEvent) -> float:
    high = event.metadata.get("high")
    low = event.metadata.get("low")
    if isinstance(high, (int, float)) and isinstance(low, (int, float)):
        return max(0.0, float(high) - float(low))
    if isinstance(high, dict) and isinstance(low, dict):
        high_values = [float(value) for value in high.values() if value is not None]
        low_values = [float(value) for value in low.values() if value is not None]
        if high_values and low_values:
            return max(0.0, mean(high_values) - mean(low_values))
    return 0.0


def build_closed_outcomes(
    events: Iterable[MarketEvent],
    *,
    count: int = 100,
    warmup: int = 10,
    horizon_bars: int = 3,
    mode: str = "SHADOW",
    source: str = "RECORDED_REAL_MARKET",
    strategy: str = "MOMENTUM_3BAR_ATR10_V1",
    evidence_ref_prefix: str,
) -> list[ClosedPaperShadowOutcome]:
    if count <= 0:
        raise ValueError("count must be positive")
    if warmup < 3:
        raise ValueError("warmup must be >= 3")
    if horizon_bars <= 0:
        raise ValueError("horizon_bars must be positive")
    if mode not in {"PAPER", "SHADOW"}:
        raise ValueError("mode must be PAPER or SHADOW")
    if source not in {"LIVE_MARKET", "RECORDED_REAL_MARKET"}:
        raise ValueError("source must be a real-market graduation source")

    ordered = sorted(events, key=lambda event: (event.event_time, event.event_id))
    required = warmup + horizon_bars + count
    if len(ordered) < required:
        raise ValueError(
            f"not enough real-market bars: got {len(ordered)}, need at least {required}"
        )

    outcomes: list[ClosedPaperShadowOutcome] = []
    for index in range(warmup, len(ordered) - horizon_bars):
        current = ordered[index]
        future = ordered[index + horizon_bars]
        entry = _price(current)
        exit_price = _price(future)
        momentum_reference = _price(ordered[index - 3])
        if entry == momentum_reference:
            continue

        direction = "LONG" if entry > momentum_reference else "SHORT"
        recent_ranges = [_bar_range(event) for event in ordered[index - warmup : index]]
        nonzero_ranges = [value for value in recent_ranges if value > 0]
        atr_proxy = mean(nonzero_ranges) if nonzero_ranges else 0.0
        risk_unit = max(atr_proxy, entry * 0.0005)
        signed_pnl = exit_price - entry if direction == "LONG" else entry - exit_price
        realized_r = signed_pnl / risk_unit

        identity = "|".join(
            [
                current.source,
                current.instrument,
                _iso(current),
                strategy,
                str(horizon_bars),
            ]
        )
        signal_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        signal_id = f"ps-{signal_hash}"
        evidence_ref = f"{evidence_ref_prefix}#event_id={current.event_id}"

        outcomes.append(
            ClosedPaperShadowOutcome(
                signal_id=signal_id,
                mode=mode,
                source=source,
                state="CLOSED",
                observed_at=_iso(current),
                closed_at=_iso(future),
                realized_r=round(float(realized_r), 8),
                evidence_ref=evidence_ref,
                instrument=current.instrument,
                strategy=strategy,
                direction=direction,
                entry_price=round(entry, 8),
                exit_price=round(exit_price, 8),
                risk_unit=round(risk_unit, 8),
                horizon_bars=horizon_bars,
            )
        )
        if len(outcomes) == count:
            break

    if len(outcomes) != count:
        raise ValueError(
            f"could only build {len(outcomes)} closed outcomes from {len(ordered)} bars"
        )
    if len({outcome.signal_id for outcome in outcomes}) != count:
        raise RuntimeError("paper/shadow signal ids are not unique")
    return outcomes
