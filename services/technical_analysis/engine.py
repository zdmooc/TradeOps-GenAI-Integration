from __future__ import annotations

from collections.abc import Iterable, Sequence

from .aggregation import build_multi_timeframe
from .indicators import snapshot
from .models import Bar, TechnicalAnalysis
from .patterns import detect_patterns
from .structure import classify_structure


class TechnicalAnalysisEngine:
    def analyze(self, bars: Sequence[Bar]) -> TechnicalAnalysis:
        if not bars:
            raise ValueError("at least one bar is required")
        ordered = sorted(bars, key=lambda b: b.start_time)
        instrument = ordered[-1].instrument
        timeframe = ordered[-1].timeframe
        if any(b.instrument != instrument for b in ordered):
            raise ValueError("all bars must belong to one instrument")
        if any(b.timeframe != timeframe for b in ordered):
            raise ValueError("all bars must belong to one timeframe")
        return TechnicalAnalysis(
            instrument=instrument,
            timeframe=timeframe,
            as_of=ordered[-1].end_time,
            indicators=snapshot(ordered),
            structure=classify_structure(ordered),
            patterns=tuple(detect_patterns(ordered)),
        )

    def analyze_multi_timeframe(
        self,
        base_bars: Iterable[Bar],
        timeframes: Iterable[str],
    ) -> dict[str, TechnicalAnalysis]:
        frames = build_multi_timeframe(base_bars, timeframes)
        return {tf: self.analyze(bars) for tf, bars in frames.items() if bars}
