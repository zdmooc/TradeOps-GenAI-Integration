from __future__ import annotations

from collections.abc import Sequence
from statistics import mean

from .indicators import ema
from .models import Bar, PatternSignal


def _signal(
    bars: Sequence[Bar],
    *,
    pattern: str,
    direction: str,
    entry: float,
    invalidation: float,
    preconditions: tuple[str, ...],
    invalidation_rule: str,
    evidence: dict,
    lookback: int,
) -> PatternSignal:
    return PatternSignal(
        pattern=pattern,
        direction=direction,
        timeframe=bars[-1].timeframe,
        detected_at=bars[-1].end_time,
        entry_reference=entry,
        invalidation=invalidation,
        preconditions=preconditions,
        invalidation_rule=invalidation_rule,
        evidence=evidence,
        lookback=lookback,
    )


def breakout_retest(
    bars: Sequence[Bar], lookback: int = 20, tolerance: float = 0.002
) -> PatternSignal | None:
    if len(bars) < lookback + 3:
        return None
    base = bars[-(lookback + 3) : -3]
    breakout, retest, confirm = bars[-3:]
    resistance = max(b.high for b in base)
    support = min(b.low for b in base)
    if (
        breakout.close > resistance
        and retest.low <= resistance * (1 + tolerance)
        and retest.close >= resistance
        and confirm.close > retest.close
        and confirm.close > resistance
    ):
        return _signal(
            bars,
            pattern="BREAKOUT_RETEST",
            direction="LONG",
            entry=confirm.close,
            invalidation=retest.low,
            preconditions=(
                "close breaks prior lookback resistance",
                "retest touches/revisits breakout level",
                "retest closes at/above level",
                "confirmation closes above retest and level",
            ),
            invalidation_rule="close below retest low invalidates the long setup",
            evidence={
                "resistance": resistance,
                "breakout_close": breakout.close,
                "retest_low": retest.low,
                "confirm_close": confirm.close,
            },
            lookback=lookback,
        )
    if (
        breakout.close < support
        and retest.high >= support * (1 - tolerance)
        and retest.close <= support
        and confirm.close < retest.close
        and confirm.close < support
    ):
        return _signal(
            bars,
            pattern="BREAKOUT_RETEST",
            direction="SHORT",
            entry=confirm.close,
            invalidation=retest.high,
            preconditions=(
                "close breaks prior lookback support",
                "retest revisits breakdown level",
                "retest closes at/below level",
                "confirmation closes below retest and level",
            ),
            invalidation_rule="close above retest high invalidates the short setup",
            evidence={
                "support": support,
                "breakout_close": breakout.close,
                "retest_high": retest.high,
                "confirm_close": confirm.close,
            },
            lookback=lookback,
        )
    return None


def failed_breakout(bars: Sequence[Bar], lookback: int = 20) -> PatternSignal | None:
    if len(bars) < lookback + 2:
        return None
    base = bars[-(lookback + 2) : -2]
    probe, confirm = bars[-2:]
    resistance = max(b.high for b in base)
    support = min(b.low for b in base)
    if probe.high > resistance and probe.close < resistance and confirm.close < probe.close:
        return _signal(
            bars,
            pattern="FAILED_BREAKOUT",
            direction="SHORT",
            entry=confirm.close,
            invalidation=probe.high,
            preconditions=(
                "price trades above prior resistance",
                "probe closes back inside the prior range",
                "next bar confirms lower",
            ),
            invalidation_rule="trade above failed-breakout high invalidates the short setup",
            evidence={"resistance": resistance, "probe_high": probe.high, "probe_close": probe.close},
            lookback=lookback,
        )
    if probe.low < support and probe.close > support and confirm.close > probe.close:
        return _signal(
            bars,
            pattern="FAILED_BREAKOUT",
            direction="LONG",
            entry=confirm.close,
            invalidation=probe.low,
            preconditions=(
                "price trades below prior support",
                "probe closes back inside the prior range",
                "next bar confirms higher",
            ),
            invalidation_rule="trade below failed-breakout low invalidates the long setup",
            evidence={"support": support, "probe_low": probe.low, "probe_close": probe.close},
            lookback=lookback,
        )
    return None


def pullback(
    bars: Sequence[Bar], fast_period: int = 9, slow_period: int = 21
) -> PatternSignal | None:
    if len(bars) < slow_period + 2:
        return None
    closes = [b.close for b in bars]
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    f = fast[-1]
    s = slow[-1]
    if f is None or s is None:
        return None
    recent = bars[-3:]
    if (
        f > s
        and min(b.low for b in recent) <= f
        and bars[-1].close > f
        and bars[-1].close > bars[-2].close
    ):
        return _signal(
            bars,
            pattern="PULLBACK",
            direction="LONG",
            entry=bars[-1].close,
            invalidation=min(b.low for b in recent),
            preconditions=(
                f"EMA{fast_period} above EMA{slow_period}",
                "recent bars retrace to/through fast EMA",
                "latest close reclaims fast EMA and closes higher",
            ),
            invalidation_rule="break below pullback swing low invalidates the long setup",
            evidence={"ema_fast": f, "ema_slow": s, "pullback_low": min(b.low for b in recent)},
            lookback=slow_period,
        )
    if (
        f < s
        and max(b.high for b in recent) >= f
        and bars[-1].close < f
        and bars[-1].close < bars[-2].close
    ):
        return _signal(
            bars,
            pattern="PULLBACK",
            direction="SHORT",
            entry=bars[-1].close,
            invalidation=max(b.high for b in recent),
            preconditions=(
                f"EMA{fast_period} below EMA{slow_period}",
                "recent bars retrace to/through fast EMA",
                "latest close rejects fast EMA and closes lower",
            ),
            invalidation_rule="break above pullback swing high invalidates the short setup",
            evidence={"ema_fast": f, "ema_slow": s, "pullback_high": max(b.high for b in recent)},
            lookback=slow_period,
        )
    return None


def support_resistance_rejection(
    bars: Sequence[Bar], lookback: int = 20, tolerance: float = 0.002
) -> PatternSignal | None:
    if len(bars) < lookback + 1:
        return None
    base = bars[-(lookback + 1) : -1]
    bar = bars[-1]
    resistance = max(b.high for b in base)
    support = min(b.low for b in base)
    span = max(bar.range, 1e-12)
    lower_wick = min(bar.open, bar.close) - bar.low
    upper_wick = bar.high - max(bar.open, bar.close)
    if bar.low <= support * (1 + tolerance) and bar.close > support and lower_wick / span >= 0.45:
        return _signal(
            bars,
            pattern="SUPPORT_RESISTANCE_REJECTION",
            direction="LONG",
            entry=bar.close,
            invalidation=bar.low,
            preconditions=(
                "bar tests established support",
                "bar closes above support",
                "lower wick is at least 45% of candle range",
            ),
            invalidation_rule="trade below rejection wick low invalidates the long setup",
            evidence={"support": support, "lower_wick_ratio": lower_wick / span},
            lookback=lookback,
        )
    if bar.high >= resistance * (1 - tolerance) and bar.close < resistance and upper_wick / span >= 0.45:
        return _signal(
            bars,
            pattern="SUPPORT_RESISTANCE_REJECTION",
            direction="SHORT",
            entry=bar.close,
            invalidation=bar.high,
            preconditions=(
                "bar tests established resistance",
                "bar closes below resistance",
                "upper wick is at least 45% of candle range",
            ),
            invalidation_rule="trade above rejection wick high invalidates the short setup",
            evidence={"resistance": resistance, "upper_wick_ratio": upper_wick / span},
            lookback=lookback,
        )
    return None


def compression_expansion(
    bars: Sequence[Bar], compression: int = 5, baseline: int = 20
) -> PatternSignal | None:
    if len(bars) < baseline + compression + 1:
        return None
    previous = bars[-(compression + 1) : -1]
    baseline_bars = bars[-(baseline + compression + 1) : -(compression + 1)]
    avg_recent = mean(b.range for b in previous)
    avg_base = mean(b.range for b in baseline_bars)
    current = bars[-1]
    if avg_base <= 0 or not (avg_recent <= 0.75 * avg_base and current.range >= 1.5 * avg_recent):
        return None
    direction = "LONG" if current.close > current.open else "SHORT"
    invalidation = current.low if direction == "LONG" else current.high
    return _signal(
        bars,
        pattern="COMPRESSION_EXPANSION",
        direction=direction,
        entry=current.close,
        invalidation=invalidation,
        preconditions=(
            "recent average range <= 75% of prior baseline range",
            "current range >= 150% of compressed average range",
        ),
        invalidation_rule="crossing the expansion candle opposite extreme invalidates the setup",
        evidence={
            "compressed_avg_range": avg_recent,
            "baseline_avg_range": avg_base,
            "expansion_range": current.range,
        },
        lookback=baseline + compression,
    )


def gap(bars: Sequence[Bar], minimum_fraction: float = 0.0) -> PatternSignal | None:
    if len(bars) < 2:
        return None
    prev, current = bars[-2:]
    reference = max(abs(prev.close), 1e-12)
    if current.low > prev.high and (current.low - prev.high) / reference >= minimum_fraction:
        return _signal(
            bars,
            pattern="GAP",
            direction="LONG",
            entry=current.open,
            invalidation=prev.high,
            preconditions=("current low is above previous high",),
            invalidation_rule="full gap fill below previous high invalidates gap continuation",
            evidence={"previous_high": prev.high, "current_low": current.low},
            lookback=2,
        )
    if current.high < prev.low and (prev.low - current.high) / reference >= minimum_fraction:
        return _signal(
            bars,
            pattern="GAP",
            direction="SHORT",
            entry=current.open,
            invalidation=prev.low,
            preconditions=("current high is below previous low",),
            invalidation_rule="full gap fill above previous low invalidates gap continuation",
            evidence={"previous_low": prev.low, "current_high": current.high},
            lookback=2,
        )
    return None


def liquidity_sweep(bars: Sequence[Bar], lookback: int = 20) -> PatternSignal | None:
    if len(bars) < lookback + 1:
        return None
    base = bars[-(lookback + 1) : -1]
    current = bars[-1]
    resistance = max(b.high for b in base)
    support = min(b.low for b in base)
    if current.high > resistance and current.close < resistance:
        return _signal(
            bars,
            pattern="LIQUIDITY_SWEEP",
            direction="SHORT",
            entry=current.close,
            invalidation=current.high,
            preconditions=(
                "candle trades above prior lookback high",
                "candle closes back below swept high",
            ),
            invalidation_rule="trade above sweep high invalidates the short setup",
            evidence={"swept_level": resistance, "sweep_high": current.high, "close": current.close},
            lookback=lookback,
        )
    if current.low < support and current.close > support:
        return _signal(
            bars,
            pattern="LIQUIDITY_SWEEP",
            direction="LONG",
            entry=current.close,
            invalidation=current.low,
            preconditions=(
                "candle trades below prior lookback low",
                "candle closes back above swept low",
            ),
            invalidation_rule="trade below sweep low invalidates the long setup",
            evidence={"swept_level": support, "sweep_low": current.low, "close": current.close},
            lookback=lookback,
        )
    return None


PATTERN_DETECTORS = (
    breakout_retest,
    failed_breakout,
    pullback,
    support_resistance_rejection,
    compression_expansion,
    gap,
    liquidity_sweep,
)


def detect_patterns(bars: Sequence[Bar]) -> list[PatternSignal]:
    signals: list[PatternSignal] = []
    for detector in PATTERN_DETECTORS:
        signal = detector(bars)
        if signal is not None:
            signals.append(signal)
    return signals
