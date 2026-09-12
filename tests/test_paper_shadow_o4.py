from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from services.graduation.gate import count_valid_paper_shadow_records
from services.graduation.paper_shadow import build_closed_outcomes
from services.market_data.model import MarketEvent

UTC = timezone.utc
BASE = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


def _real_bars(count: int) -> list[MarketEvent]:
    events: list[MarketEvent] = []
    for index in range(count):
        price = 100.0 + (index % 20) * 0.15 + index * 0.01
        events.append(
            MarketEvent(
                instrument="XXBTZUSD",
                event_time=BASE + timedelta(minutes=index),
                ingest_time=BASE + timedelta(minutes=count),
                source="KRAKEN_REST",
                last=price,
                market_status="HISTORICAL_COMMITTED",
                event_type="BAR",
                resolution="MINUTE",
                event_id=f"real-{index:03d}",
                metadata={
                    "open": price - 0.05,
                    "high": price + 0.20,
                    "low": price - 0.20,
                    "close": price,
                    "committed": True,
                },
            )
        )
    return events


def test_builds_exactly_one_hundred_unique_closed_real_market_outcomes(tmp_path):
    outcomes = build_closed_outcomes(
        _real_bars(140),
        count=100,
        warmup=10,
        horizon_bars=3,
        evidence_ref_prefix="repo:evidence/real-capture.jsonl",
    )

    assert len(outcomes) == 100
    assert len({outcome.signal_id for outcome in outcomes}) == 100
    assert all(outcome.mode == "SHADOW" for outcome in outcomes)
    assert all(outcome.source == "RECORDED_REAL_MARKET" for outcome in outcomes)
    assert all(outcome.state == "CLOSED" for outcome in outcomes)
    assert all(outcome.evidence_ref.startswith("repo:evidence/real-capture.jsonl") for outcome in outcomes)
    assert all(outcome.closed_at > outcome.observed_at for outcome in outcomes)

    records_path = tmp_path / "paper-shadow-records.jsonl"
    with records_path.open("w", encoding="utf-8") as handle:
        for outcome in outcomes:
            handle.write(json.dumps(outcome.to_dict(), sort_keys=True) + "\n")

    assert count_valid_paper_shadow_records(records_path) == 100


def test_outcome_generation_fails_when_real_market_history_is_too_short():
    with pytest.raises(ValueError, match="not enough real-market bars"):
        build_closed_outcomes(
            _real_bars(50),
            count=100,
            warmup=10,
            horizon_bars=3,
            evidence_ref_prefix="repo:evidence/real-capture.jsonl",
        )


def test_same_real_market_input_produces_same_signal_ids_and_realized_r():
    events = _real_bars(140)
    first = build_closed_outcomes(
        events,
        count=100,
        warmup=10,
        horizon_bars=3,
        evidence_ref_prefix="repo:evidence/real-capture.jsonl",
    )
    second = build_closed_outcomes(
        list(reversed(events)),
        count=100,
        warmup=10,
        horizon_bars=3,
        evidence_ref_prefix="repo:evidence/real-capture.jsonl",
    )

    assert [item.signal_id for item in first] == [item.signal_id for item in second]
    assert [item.realized_r for item in first] == [item.realized_r for item in second]
