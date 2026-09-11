from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .clock import DeterministicClock
from .model import MarketEvent
from .quality import DataQualityEngine, QualityDecision


@dataclass(frozen=True)
class ReplayRecord:
    event: MarketEvent
    quality: QualityDecision


@dataclass(frozen=True)
class ReplayResult:
    records: tuple[ReplayRecord, ...]

    @property
    def accepted(self) -> tuple[MarketEvent, ...]:
        return tuple(r.event for r in self.records if r.quality.accepted)

    @property
    def rejected(self) -> tuple[ReplayRecord, ...]:
        return tuple(r for r in self.records if not r.quality.accepted)


class ReplayEngine:
    def __init__(self, quality: DataQualityEngine | None = None):
        self.quality = quality or DataQualityEngine()

    @staticmethod
    def load_jsonl(path: str | Path) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    events.append(MarketEvent.from_dict(json.loads(line)))
                except Exception as exc:
                    raise ValueError(f"invalid replay line {line_no}: {exc}") from exc
        return events

    @staticmethod
    def write_jsonl(path: str | Path, events: Iterable[MarketEvent]) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def replay(
        self,
        events: Iterable[MarketEvent],
        *,
        emit: Callable[[MarketEvent], None] | None = None,
    ) -> ReplayResult:
        ordered = sorted(events, key=lambda e: (e.event_time, e.event_id))
        if not ordered:
            return ReplayResult(())
        self.quality.reset()
        clock = DeterministicClock(ordered[0].event_time)
        records: list[ReplayRecord] = []
        for event in ordered:
            clock.set(event.event_time)
            decision = self.quality.evaluate(event, now=clock.now(), check_stale=False)
            records.append(ReplayRecord(event, decision))
            if decision.accepted and emit is not None:
                emit(event)
        return ReplayResult(tuple(records))
