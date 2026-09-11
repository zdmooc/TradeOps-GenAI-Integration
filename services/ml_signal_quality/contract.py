from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import SignalQualityRecord


DEFAULT_FEATURE_NAMES = (
    "rsi",
    "macd_histogram",
    "atr_pct",
    "adx",
    "ema_slope",
    "vwap_distance_pct",
    "volatility_pct",
    "volume_zscore",
    "structure_score",
    "pattern_score",
    "relative_strength",
    "session_code",
    "level_distance_atr",
    "regime_code",
    "spread_bps",
    "latency_ms",
    "data_quality_score",
)

FORBIDDEN_TOKENS = (
    "target",
    "future",
    "outcome",
    "label",
    "exit",
    "pnl",
    "profit",
    "mfe",
    "mae",
    "tp_before_sl",
)


@dataclass(frozen=True, slots=True)
class FeatureContract:
    version: str = "i5-v1"
    feature_names: tuple[str, ...] = DEFAULT_FEATURE_NAMES

    def validate_feature_names(self) -> None:
        if len(set(self.feature_names)) != len(self.feature_names):
            raise ValueError("feature names must be unique")
        for name in self.feature_names:
            lowered = name.lower()
            if any(token in lowered for token in FORBIDDEN_TOKENS):
                raise ValueError(f"leakage-prone feature name rejected: {name}")

    def validate_record(self, record: SignalQualityRecord) -> None:
        self.validate_feature_names()
        names = set(record.features)
        expected = set(self.feature_names)
        missing = expected - names
        extra = names - expected
        if missing or extra:
            raise ValueError(
                f"feature contract mismatch missing={sorted(missing)} extra={sorted(extra)}"
            )
        if record.label_time <= record.feature_time:
            raise ValueError("label must occur after the feature cutoff")

    def matrix(self, records: list[SignalQualityRecord]) -> np.ndarray:
        for record in records:
            self.validate_record(record)
        return np.asarray(
            [[record.features[name] for name in self.feature_names] for record in records],
            dtype=float,
        )

    @staticmethod
    def labels(records: list[SignalQualityRecord]) -> np.ndarray:
        return np.asarray([record.label for record in records], dtype=int)
