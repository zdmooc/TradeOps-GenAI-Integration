from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.technical_analysis.models import Bar


@dataclass(frozen=True, slots=True)
class ChronologicalSplit:
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_indices: tuple[int, int]
    test_indices: tuple[int, int]


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_indices: tuple[int, int]
    test_indices: tuple[int, int]


def chronological_split(bars: list[Bar], train_fraction: float = 0.7) -> ChronologicalSplit:
    if len(bars) < 2:
        raise ValueError("at least two bars are required")
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between 0 and 1")
    ordered = sorted(bars, key=lambda bar: bar.start_time)
    train_count = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    return ChronologicalSplit(
        train_start=ordered[0].start_time,
        train_end=ordered[train_count - 1].end_time,
        test_start=ordered[train_count].start_time,
        test_end=ordered[-1].end_time,
        train_indices=(0, train_count - 1),
        test_indices=(train_count, len(ordered) - 1),
    )


def walk_forward_windows(
    bars: list[Bar],
    train_bars: int,
    test_bars: int,
    step_bars: int | None = None,
) -> tuple[WalkForwardWindow, ...]:
    if train_bars < 1 or test_bars < 1:
        raise ValueError("train_bars and test_bars must be >= 1")
    step = test_bars if step_bars is None else step_bars
    if step < 1:
        raise ValueError("step_bars must be >= 1")
    ordered = sorted(bars, key=lambda bar: bar.start_time)
    windows: list[WalkForwardWindow] = []
    start = 0
    window_id = 1
    while start + train_bars + test_bars <= len(ordered):
        train_start_idx = start
        train_end_idx = start + train_bars - 1
        test_start_idx = train_end_idx + 1
        test_end_idx = test_start_idx + test_bars - 1
        windows.append(
            WalkForwardWindow(
                window_id=window_id,
                train_start=ordered[train_start_idx].start_time,
                train_end=ordered[train_end_idx].end_time,
                test_start=ordered[test_start_idx].start_time,
                test_end=ordered[test_end_idx].end_time,
                train_indices=(train_start_idx, train_end_idx),
                test_indices=(test_start_idx, test_end_idx),
            )
        )
        start += step
        window_id += 1
    return tuple(windows)
