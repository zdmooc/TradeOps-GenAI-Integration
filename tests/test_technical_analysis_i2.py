from datetime import datetime, timedelta, timezone

import pytest

from services.technical_analysis.aggregation import build_multi_timeframe, resample_bars
from services.technical_analysis.engine import TechnicalAnalysisEngine
from services.technical_analysis.indicators import (
    adx,
    atr,
    bollinger,
    ema,
    macd,
    rsi,
    snapshot,
    vwap,
)
from services.technical_analysis.models import Bar
from services.technical_analysis.patterns import (
    breakout_retest,
    compression_expansion,
    failed_breakout,
    gap,
    liquidity_sweep,
    pullback,
    support_resistance_rejection,
)
from services.technical_analysis.structure import classify_structure


UTC = timezone.utc
BASE = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def bar(i, o, h, low, c, v=100.0, tf="M1"):
    return Bar(
        instrument="IX.D.DAX.IFM.IP",
        timeframe=tf,
        start_time=BASE + timedelta(minutes=i),
        end_time=BASE + timedelta(minutes=i + 1),
        open=float(o),
        high=float(h),
        low=float(low),
        close=float(c),
        volume=float(v),
        source="TEST",
    )


def trend_bars(n=60, step=1.0):
    rows = []
    for i in range(n):
        c = 100 + i * step
        rows.append(bar(i, c - 0.3, c + 0.8, c - 0.8, c, 100 + i))
    return rows


def test_indicators_are_deterministic_and_bounded():
    bars = trend_bars(80)
    closes = [b.close for b in bars]
    snap = snapshot(bars)
    assert snap.ema_fast > snap.ema_slow
    assert snap.rsi == pytest.approx(100.0)
    assert snap.atr > 0
    assert 0 <= snap.adx <= 100
    assert snap.plus_di > snap.minus_di
    assert snap.macd > 0
    assert snap.bb_upper > snap.bb_middle > snap.bb_lower
    assert snap.vwap is not None
    assert ema(closes, 9) == ema(closes, 9)
    assert atr(bars) == atr(bars)
    assert rsi(closes) == rsi(closes)
    assert adx(bars) == adx(bars)
    assert macd(closes) == macd(closes)
    assert bollinger(closes) == bollinger(closes)
    assert vwap(bars) == vwap(bars)


def test_multi_timeframe_aggregation_preserves_ohlcv():
    bars = [bar(i, 100 + i, 101 + i, 99 + i, 100.5 + i, 10) for i in range(15)]
    m5 = resample_bars(bars, "M5")
    assert len(m5) == 3
    assert m5[0].open == 100
    assert m5[0].close == 104.5
    assert m5[0].high == 105
    assert m5[0].low == 99
    assert m5[0].volume == 50
    frames = build_multi_timeframe(bars, ["M5", "M15"])
    assert len(frames["M5"]) == 3
    assert len(frames["M15"]) == 1


def test_market_structure_labels_hh_hl_bullish():
    highs = [102, 105, 103, 108, 104, 111, 106, 114, 108]
    lows = [98, 99, 97, 101, 99, 104, 102, 107, 105]
    bars = []
    for i, (high, low) in enumerate(zip(highs, lows)):
        mid = (high + low) / 2
        bars.append(bar(i, mid, high, low, mid))
    structure = classify_structure(bars, left=1, right=1)
    labels = [s.label for s in structure.swings]
    assert "HH" in labels
    assert "HL" in labels
    assert structure.trend == "BULLISH"


def test_breakout_retest_long():
    base = [bar(i, 99.5, 100, 99, 99.7) for i in range(20)]
    bars = base + [
        bar(20, 99.8, 102, 99.8, 101.5),
        bar(21, 101.4, 101.8, 99.95, 100.4),
        bar(22, 100.5, 102.5, 100.3, 102.0),
    ]
    sig = breakout_retest(bars)
    assert sig and sig.direction == "LONG"
    assert sig.pattern == "BREAKOUT_RETEST"
    assert sig.invalidation == pytest.approx(99.95)
    assert sig.preconditions and sig.invalidation_rule and sig.evidence


def test_failed_breakout_and_liquidity_sweep_short():
    base = [bar(i, 99.5, 100, 99, 99.7) for i in range(20)]
    bars = base + [
        bar(20, 99.8, 101.5, 99.6, 99.6),
        bar(21, 99.5, 99.8, 98.8, 99.0),
    ]
    failed = failed_breakout(bars)
    assert failed and failed.direction == "SHORT"
    sweep = liquidity_sweep(base + [bar(20, 99.8, 101.5, 99.4, 99.6)])
    assert sweep and sweep.direction == "SHORT"


def test_pullback_long():
    bars = trend_bars(30)
    bars[-3] = bar(27, 125.5, 126.0, 122.0, 123.0)
    bars[-2] = bar(28, 123.0, 124.0, 121.5, 122.5)
    bars[-1] = bar(29, 122.5, 128.5, 122.0, 128.0)
    sig = pullback(bars)
    assert sig and sig.direction == "LONG"


def test_support_rejection_long():
    base = [bar(i, 101, 102, 100, 101) for i in range(20)]
    rejection = bar(20, 100.7, 101.2, 99.9, 101.0)
    sig = support_resistance_rejection(base + [rejection])
    assert sig and sig.direction == "LONG"


def test_compression_expansion_long():
    baseline = [bar(i, 100, 102, 98, 101) for i in range(20)]
    compressed = [bar(20 + i, 100, 100.5, 99.5, 100.1) for i in range(5)]
    expansion = bar(25, 100, 103, 99.5, 102.8)
    sig = compression_expansion(baseline + compressed + [expansion])
    assert sig and sig.direction == "LONG"


def test_gap_up():
    bars = [bar(0, 100, 101, 99, 100), bar(1, 103, 104, 102, 103.5)]
    sig = gap(bars)
    assert sig and sig.direction == "LONG"


def test_engine_returns_formal_pattern_evidence():
    base = [bar(i, 99.5, 100, 99, 99.7) for i in range(20)]
    bars = base + [
        bar(20, 99.8, 102, 99.8, 101.5),
        bar(21, 101.4, 101.8, 99.95, 100.4),
        bar(22, 100.5, 102.5, 100.3, 102.0),
    ]
    result = TechnicalAnalysisEngine().analyze(bars)
    assert result.instrument == "IX.D.DAX.IFM.IP"
    breakout = next(p for p in result.patterns if p.pattern == "BREAKOUT_RETEST")
    payload = breakout.to_dict()
    assert payload["timeframe"] == "M1"
    assert payload["preconditions"]
    assert payload["invalidation_rule"]
    assert payload["evidence"]


def test_labelled_replay_examples_match_expected_patterns():
    import json
    from pathlib import Path

    payload = json.loads(Path("data/replay/i2_labelled_patterns.json").read_text())
    engine = TechnicalAnalysisEngine()
    base_time = datetime.fromisoformat(payload["base_time"].replace("Z", "+00:00"))
    for scenario in payload["scenarios"]:
        bars = [
            Bar(
                instrument=payload["instrument"],
                timeframe=payload["timeframe"],
                start_time=base_time + timedelta(minutes=i),
                end_time=base_time + timedelta(minutes=i + 1),
                open=row[0],
                high=row[1],
                low=row[2],
                close=row[3],
                volume=row[4],
                source="I2_FIXTURE",
            )
            for i, row in enumerate(scenario["ohlcv"])
        ]
        analysis = engine.analyze(bars)
        matches = [
            signal
            for signal in analysis.patterns
            if signal.pattern == scenario["expected_pattern"]
            and signal.direction == scenario["expected_direction"]
        ]
        assert matches, scenario["name"]
