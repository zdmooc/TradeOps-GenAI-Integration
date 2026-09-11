from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from services.technical_analysis.models import Bar

from .models import BacktestConfig, BacktestSignal


@dataclass(frozen=True, slots=True)
class ExperimentData:
    dataset_id: str
    dataset_sha256: str
    bars: tuple[Bar, ...]
    signals: tuple[BacktestSignal, ...]
    config: BacktestConfig
    manifest: dict[str, Any]


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_experiment(path: str | Path) -> ExperimentData:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = dict(payload["manifest"])
    dataset_id = str(manifest["dataset_id"])
    dataset_payload = {
        "manifest": manifest,
        "bars": payload["bars"],
        "signals": payload["signals"],
    }
    bars = tuple(
        Bar(
            instrument=item["instrument"],
            timeframe=item["timeframe"],
            start_time=_dt(item["start_time"]),
            end_time=_dt(item["end_time"]),
            open=float(item["open"]),
            high=float(item["high"]),
            low=float(item["low"]),
            close=float(item["close"]),
            volume=float(item.get("volume", 0.0)),
            source=item.get("source", "I4_FIXTURE"),
        )
        for item in payload["bars"]
    )
    signals = tuple(
        BacktestSignal(
            signal_id=item["signal_id"],
            instrument=item["instrument"],
            side=item["side"],
            generated_at=_dt(item["generated_at"]),
            stop=float(item["stop"]),
            target=float(item["target"]),
            quantity=float(item["quantity"]),
            point_value=float(item.get("point_value", 1.0)),
            pattern=item.get("pattern", "UNSPECIFIED"),
            regime=item.get("regime", "UNKNOWN"),
            session=item.get("session", "UNSPECIFIED"),
            timeframe=item.get("timeframe", "M1"),
            risk_status=item.get("risk_status", "APPROVED"),
        )
        for item in payload["signals"]
    )
    config = BacktestConfig(**payload["config"])
    if not bars:
        raise ValueError("dataset must contain bars")
    if manifest.get("instrument") and any(
        bar.instrument != str(manifest["instrument"]).upper() for bar in bars
    ):
        raise ValueError("manifest instrument does not match bars")
    if manifest.get("timeframe") and any(
        bar.timeframe != str(manifest["timeframe"]).upper() for bar in bars
    ):
        raise ValueError("manifest timeframe does not match bars")
    return ExperimentData(
        dataset_id=dataset_id,
        dataset_sha256=canonical_sha256(dataset_payload),
        bars=bars,
        signals=signals,
        config=config,
        manifest=manifest,
    )
