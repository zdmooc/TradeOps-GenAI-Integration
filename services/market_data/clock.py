from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class DeterministicClock:
    current: datetime

    def __post_init__(self) -> None:
        if self.current.tzinfo is None or self.current.utcoffset() is None:
            raise ValueError("clock requires timezone-aware datetime")
        self.current = self.current.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self.current

    def set(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock requires timezone-aware datetime")
        self.current = value.astimezone(timezone.utc)
        return self.current

    def advance(self, *, milliseconds: float = 0, seconds: float = 0) -> datetime:
        self.current += timedelta(milliseconds=milliseconds, seconds=seconds)
        return self.current
