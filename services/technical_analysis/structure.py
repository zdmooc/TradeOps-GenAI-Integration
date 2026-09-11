from __future__ import annotations

from collections.abc import Sequence

from .models import Bar, MarketStructure, SwingPoint


def detect_swings(bars: Sequence[Bar], left: int = 2, right: int = 2) -> list[SwingPoint]:
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")
    raw: list[tuple[int, str, float]] = []
    for i in range(left, len(bars) - right):
        window_left = bars[i - left : i]
        window_right = bars[i + 1 : i + right + 1]
        if all(bars[i].high > b.high for b in (*window_left, *window_right)):
            raw.append((i, "HIGH", bars[i].high))
        if all(bars[i].low < b.low for b in (*window_left, *window_right)):
            raw.append((i, "LOW", bars[i].low))

    last_high: float | None = None
    last_low: float | None = None
    result: list[SwingPoint] = []
    for index, kind, price in sorted(raw, key=lambda row: (row[0], row[1])):
        if kind == "HIGH":
            label = "SH" if last_high is None else ("HH" if price > last_high else "LH")
            last_high = price
        else:
            label = "SL" if last_low is None else ("HL" if price > last_low else "LL")
            last_low = price
        result.append(SwingPoint(index, bars[index].end_time, price, kind, label))
    return result


def classify_structure(bars: Sequence[Bar], left: int = 2, right: int = 2) -> MarketStructure:
    swings = detect_swings(bars, left=left, right=right)
    highs = [s for s in swings if s.kind == "HIGH"]
    lows = [s for s in swings if s.kind == "LOW"]
    trend = "UNKNOWN"
    if len(highs) >= 2 and len(lows) >= 2:
        high_up = highs[-1].price > highs[-2].price
        low_up = lows[-1].price > lows[-2].price
        high_down = highs[-1].price < highs[-2].price
        low_down = lows[-1].price < lows[-2].price
        if high_up and low_up:
            trend = "BULLISH"
        elif high_down and low_down:
            trend = "BEARISH"
        else:
            trend = "RANGE"
    return MarketStructure(
        trend=trend,
        swings=tuple(swings),
        last_swing_high=highs[-1] if highs else None,
        last_swing_low=lows[-1] if lows else None,
    )
