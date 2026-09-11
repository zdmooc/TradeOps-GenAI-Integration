from __future__ import annotations

from math import sqrt
from typing import Sequence

from .models import Bar, IndicatorSnapshot


def sma(values: Sequence[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be > 0")
    result: list[float | None] = [None] * len(values)
    running = 0.0
    for i, value in enumerate(values):
        running += float(value)
        if i >= period:
            running -= float(values[i - period])
        if i >= period - 1:
            result[i] = running / period
    return result


def ema(values: Sequence[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be > 0")
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    seed = sum(float(v) for v in values[:period]) / period
    result[period - 1] = seed
    alpha = 2.0 / (period + 1.0)
    prev = seed
    for i in range(period, len(values)):
        prev = alpha * float(values[i]) + (1.0 - alpha) * prev
        result[i] = prev
    return result


def _wilder(values: Sequence[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(values) < period:
        return result
    prev = sum(float(v) for v in values[:period]) / period
    result[period - 1] = prev
    for i in range(period, len(values)):
        prev = ((period - 1) * prev + float(values[i])) / period
        result[i] = prev
    return result


def rsi(closes: Sequence[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return result
    gains = [0.0]
    losses = [0.0]
    for prev, current in zip(closes, closes[1:]):
        delta = float(current) - float(prev)
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = _wilder(gains[1:], period)
    avg_loss = _wilder(losses[1:], period)
    for i in range(period, len(closes)):
        g = avg_gain[i - 1]
        l = avg_loss[i - 1]
        if g is None or l is None:
            continue
        if l == 0:
            result[i] = 100.0 if g > 0 else 50.0
        else:
            rs = g / l
            result[i] = 100.0 - 100.0 / (1.0 + rs)
    return result


def true_ranges(bars: Sequence[Bar]) -> list[float]:
    if not bars:
        return []
    result = [bars[0].high - bars[0].low]
    for prev, bar in zip(bars, bars[1:]):
        result.append(
            max(
                bar.high - bar.low,
                abs(bar.high - prev.close),
                abs(bar.low - prev.close),
            )
        )
    return result


def atr(bars: Sequence[Bar], period: int = 14) -> list[float | None]:
    return _wilder(true_ranges(bars), period)


def adx(
    bars: Sequence[Bar], period: int = 14
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    n = len(bars)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = bars[i].high - bars[i - 1].high
        down = bars[i - 1].low - bars[i].low
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0

    atr_series = _wilder(true_ranges(bars), period)
    plus_smoothed = _wilder(plus_dm, period)
    minus_smoothed = _wilder(minus_dm, period)
    plus_di: list[float | None] = [None] * n
    minus_di: list[float | None] = [None] * n
    dx: list[float | None] = [None] * n

    for i in range(n):
        tr = atr_series[i]
        p = plus_smoothed[i]
        m = minus_smoothed[i]
        if tr is None or p is None or m is None or tr == 0:
            continue
        plus_di[i] = 100.0 * p / tr
        minus_di[i] = 100.0 * m / tr
        denom = plus_di[i] + minus_di[i]
        dx[i] = 0.0 if denom == 0 else 100.0 * abs(plus_di[i] - minus_di[i]) / denom

    adx_result: list[float | None] = [None] * n
    valid = [(i, x) for i, x in enumerate(dx) if x is not None]
    if len(valid) >= period:
        seed_slice = valid[:period]
        seed_index = seed_slice[-1][0]
        prev = sum(float(x) for _, x in seed_slice) / period
        adx_result[seed_index] = prev
        for i, x in valid[period:]:
            prev = ((period - 1) * prev + float(x)) / period
            adx_result[i] = prev
    return adx_result, plus_di, minus_di


def macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast_series = ema(closes, fast)
    slow_series = ema(closes, slow)
    macd_line: list[float | None] = [None] * len(closes)
    for i, (f, s) in enumerate(zip(fast_series, slow_series)):
        if f is not None and s is not None:
            macd_line[i] = f - s

    valid = [float(x) for x in macd_line if x is not None]
    signal_valid = ema(valid, signal)
    signal_line: list[float | None] = [None] * len(closes)
    histogram: list[float | None] = [None] * len(closes)
    cursor = 0
    for i, value in enumerate(macd_line):
        if value is None:
            continue
        sig = signal_valid[cursor]
        if sig is not None:
            signal_line[i] = sig
            histogram[i] = value - sig
        cursor += 1
    return macd_line, signal_line, histogram


def bollinger(
    closes: Sequence[float], period: int = 20, deviations: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    middle = sma(closes, period)
    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = [float(x) for x in closes[i - period + 1 : i + 1]]
        mean = float(middle[i])
        variance = sum((x - mean) ** 2 for x in window) / period
        sd = sqrt(variance)
        upper[i] = mean + deviations * sd
        lower[i] = mean - deviations * sd
    return middle, upper, lower


def vwap(bars: Sequence[Bar]) -> list[float | None]:
    result: list[float | None] = []
    weighted = 0.0
    volume = 0.0
    for bar in bars:
        if bar.volume > 0:
            weighted += bar.typical_price * bar.volume
            volume += bar.volume
        result.append(weighted / volume if volume > 0 else None)
    return result


def snapshot(
    bars: Sequence[Bar],
    *,
    ema_fast_period: int = 9,
    ema_slow_period: int = 21,
) -> IndicatorSnapshot:
    if not bars:
        return IndicatorSnapshot()
    closes = [b.close for b in bars]
    e_fast = ema(closes, ema_fast_period)
    e_slow = ema(closes, ema_slow_period)
    vwap_series = vwap(bars)
    atr_series = atr(bars)
    adx_series, plus_di, minus_di = adx(bars)
    rsi_series = rsi(closes)
    macd_line, macd_signal, macd_hist = macd(closes)
    bb_mid, bb_upper, bb_lower = bollinger(closes)

    return IndicatorSnapshot(
        ema_fast=e_fast[-1],
        ema_slow=e_slow[-1],
        vwap=vwap_series[-1],
        atr=atr_series[-1],
        adx=adx_series[-1],
        plus_di=plus_di[-1],
        minus_di=minus_di[-1],
        rsi=rsi_series[-1],
        macd=macd_line[-1],
        macd_signal=macd_signal[-1],
        macd_histogram=macd_hist[-1],
        bb_middle=bb_mid[-1],
        bb_upper=bb_upper[-1],
        bb_lower=bb_lower[-1],
    )
