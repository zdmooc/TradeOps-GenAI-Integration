from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .contract import FeatureContract
from .models import SignalQualityRecord


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_dataset_hash(records: list[SignalQualityRecord]) -> str:
    payload = "\n".join(
        json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        for record in records
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_dataset(
    records: list[SignalQualityRecord], contract: FeatureContract
) -> None:
    if len(records) < 40:
        raise ValueError("at least 40 records are required for I5 experiments")
    record_ids = [record.record_id for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("record_id values must be unique")
    for record in records:
        contract.validate_record(record)
    feature_times = [record.feature_time for record in records]
    if feature_times != sorted(feature_times):
        raise ValueError("records must be ordered chronologically")


def _bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def generate_synthetic_records(spec: dict[str, Any]) -> list[SignalQualityRecord]:
    if spec.get("generator_version") != "stable-logit-v1":
        raise ValueError("unsupported synthetic generator version")
    rng = random.Random(int(spec["seed"]))
    start = _parse_timestamp(spec["start_time"])
    frequency = timedelta(minutes=int(spec["frequency_minutes"]))
    horizon = timedelta(minutes=int(spec["label_horizon_minutes"]))
    records: list[SignalQualityRecord] = []
    for index in range(int(spec["records"])):
        feature_time = start + frequency * index
        regime = rng.choice([-1.0, -1.0, 0.0, 0.0, 1.0, 1.0])
        session = float((index // 20) % 3)
        rsi = _bounded(50 + rng.gauss(0, 12), 15, 85)
        macd = _bounded(0.25 * regime + rng.gauss(0, 0.75), -2.5, 2.5)
        atr = _bounded(1.25 + rng.gauss(0, 0.4), 0.3, 3.5)
        adx = _bounded(26 + 6 * abs(regime) + rng.gauss(0, 7), 8, 55)
        ema_slope = _bounded(0.35 * regime + rng.gauss(0, 0.45), -1.5, 1.5)
        vwap = _bounded(rng.gauss(0, 0.65), -2, 2)
        volatility = _bounded(1.2 + rng.gauss(0, 0.4), 0.3, 3.5)
        volume_zscore = _bounded(rng.gauss(0, 1), -2.5, 2.5)
        structure = _bounded(0.5 * regime + rng.gauss(0, 0.45), -1, 1)
        pattern = _bounded(rng.betavariate(2.4, 2.0), 0, 1)
        relative_strength = _bounded(0.4 * regime + rng.gauss(0, 0.55), -1.5, 1.5)
        level_distance = _bounded(1.4 + abs(rng.gauss(0, 0.65)), 0.05, 3.5)
        spread = _bounded(6.0 + 1.4 * volatility + rng.gauss(0, 1.6), 1, 18)
        latency = _bounded(85 + 20 * volatility + abs(rng.gauss(0, 45)), 5, 400)
        data_quality = _bounded(
            0.96 - 0.004 * spread - 0.00025 * latency + rng.gauss(0, 0.02),
            0.65,
            1.0,
        )
        features = {
            "rsi": round(rsi, 6),
            "macd_histogram": round(macd, 6),
            "atr_pct": round(atr, 6),
            "adx": round(adx, 6),
            "ema_slope": round(ema_slope, 6),
            "vwap_distance_pct": round(vwap, 6),
            "volatility_pct": round(volatility, 6),
            "volume_zscore": round(volume_zscore, 6),
            "structure_score": round(structure, 6),
            "pattern_score": round(pattern, 6),
            "relative_strength": round(relative_strength, 6),
            "session_code": session,
            "level_distance_atr": round(level_distance, 6),
            "regime_code": regime,
            "spread_bps": round(spread, 6),
            "latency_ms": round(latency, 6),
            "data_quality_score": round(data_quality, 6),
        }
        latent = (
            -0.35
            + 0.035 * (rsi - 50)
            + 0.55 * macd
            + 0.02 * (adx - 25)
            + 0.85 * ema_slope
            - 0.14 * abs(vwap)
            - 0.18 * (atr - 1.3)
            - 0.15 * (volatility - 1.2)
            + 0.10 * volume_zscore
            + 0.72 * structure
            + 1.2 * (pattern - 0.5)
            + 0.65 * relative_strength
            - 0.08 * (level_distance - 1.5)
            + 0.18 * regime
            - 0.05 * (spread - 7)
            - 0.0012 * (latency - 110)
            + 0.8 * (data_quality - 0.85)
        )
        probability = 1.0 / (1.0 + math.exp(-latent))
        label = 1 if rng.random() < probability else 0
        records.append(
            SignalQualityRecord(
                record_id=f"I5-{index + 1:04d}",
                feature_time=feature_time,
                label_time=feature_time + horizon,
                features=features,
                label=label,
                source="SYNTHETIC_I5_V1",
            )
        )
    return records


def load_synthetic_dataset(
    path: str | Path, contract: FeatureContract | None = None
) -> tuple[list[SignalQualityRecord], str, dict[str, Any]]:
    feature_contract = contract or FeatureContract()
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    records = generate_synthetic_records(spec)
    validate_dataset(records, feature_contract)
    return records, canonical_dataset_hash(records), spec
