from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

from services.market_data.model import MarketEvent

from .models import Bar

TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}

IG_RESOLUTION_TO_TIMEFRAME = {
    "MINUTE": "M1",
    "MINUTE_5": "M5",
    "MINUTE_15": "M15",
    "MINUTE_30": "M30",
    "HOUR": "H1",
    "HOUR_4": "H4",
    "DAY": "D1",
}


def _timeframe_seconds(timeframe: str) -> int:
    tf = timeframe.upper()
    if tf not in TIMEFRAME_SECONDS:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    return TIMEFRAME_SECONDS[tf]


def _floor_time(value: datetime, timeframe: str) -> datetime:
    seconds = _timeframe_seconds(timeframe)
    ts = int(value.astimezone(timezone.utc).timestamp())
    floored = ts - (ts % seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def _quote_mid(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        bid = value.get("bid")
        ask = value.get("ask")
        last = value.get("lastTraded")
        if bid is not None and ask is not None:
            return (float(bid) + float(ask)) / 2.0
        if last is not None:
            return float(last)
        if bid is not None:
            return float(bid)
        if ask is not None:
            return float(ask)
    return None


def historical_event_to_bar(event: MarketEvent) -> Bar:
    if event.event_type.upper() != "BAR":
        raise ValueError("historical_event_to_bar requires event_type=BAR")
    timeframe = IG_RESOLUTION_TO_TIMEFRAME.get(
        (event.resolution or "").upper(),
        (event.resolution or "").upper(),
    )
    seconds = _timeframe_seconds(timeframe)
    meta = event.metadata
    open_ = _quote_mid(meta.get("open"))
    high = _quote_mid(meta.get("high"))
    low = _quote_mid(meta.get("low"))
    close = _quote_mid(meta.get("close")) or event.midpoint
    if None in (open_, high, low, close):
        raise ValueError("historical BAR event missing OHLC metadata")
    return Bar(
        instrument=event.instrument,
        timeframe=timeframe,
        start_time=event.event_time,
        end_time=event.event_time + timedelta(seconds=seconds),
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=float(meta.get("last_traded_volume") or 0.0),
        source=event.source,
        metadata={"event_id": event.event_id},
    )


def events_to_bars(events: Iterable[MarketEvent], timeframe: str) -> list[Bar]:
    tf = timeframe.upper()
    seconds = _timeframe_seconds(tf)
    grouped: dict[tuple[str, datetime], list[tuple[MarketEvent, float]]] = defaultdict(list)
    direct: list[Bar] = []
    for event in events:
        if event.event_type.upper() == "BAR":
            bar = historical_event_to_bar(event)
            if bar.timeframe == tf:
                direct.append(bar)
                continue
        price = event.midpoint
        if price is None:
            continue
        bucket = _floor_time(event.event_time, tf)
        grouped[(event.instrument, bucket)].append((event, float(price)))

    bars = list(direct)
    for (instrument, start), rows in grouped.items():
        rows.sort(key=lambda item: (item[0].event_time, item[0].event_id))
        prices = [price for _, price in rows]
        volume = sum(float(e.metadata.get("volume") or 0.0) for e, _ in rows)
        bars.append(
            Bar(
                instrument=instrument,
                timeframe=tf,
                start_time=start,
                end_time=start + timedelta(seconds=seconds),
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=volume,
                source=rows[-1][0].source,
                metadata={"event_count": len(rows)},
            )
        )
    return sorted(bars, key=lambda b: (b.instrument, b.start_time))


def resample_bars(bars: Iterable[Bar], target_timeframe: str) -> list[Bar]:
    tf = target_timeframe.upper()
    seconds = _timeframe_seconds(tf)
    grouped: dict[tuple[str, datetime], list[Bar]] = defaultdict(list)
    for bar in bars:
        if _timeframe_seconds(bar.timeframe) > seconds:
            raise ValueError("cannot downsample a coarser bar into a finer timeframe")
        start = _floor_time(bar.start_time, tf)
        grouped[(bar.instrument, start)].append(bar)

    result: list[Bar] = []
    for (instrument, start), rows in grouped.items():
        rows.sort(key=lambda b: b.start_time)
        result.append(
            Bar(
                instrument=instrument,
                timeframe=tf,
                start_time=start,
                end_time=start + timedelta(seconds=seconds),
                open=rows[0].open,
                high=max(b.high for b in rows),
                low=min(b.low for b in rows),
                close=rows[-1].close,
                volume=sum(b.volume for b in rows),
                source=rows[-1].source,
                complete=all(b.complete for b in rows),
                metadata={"component_bars": len(rows), "base_timeframe": rows[0].timeframe},
            )
        )
    return sorted(result, key=lambda b: (b.instrument, b.start_time))


def build_multi_timeframe(bars: Iterable[Bar], timeframes: Iterable[str]) -> dict[str, list[Bar]]:
    base = sorted(list(bars), key=lambda b: (b.instrument, b.start_time))
    return {tf.upper(): resample_bars(base, tf) for tf in timeframes}
