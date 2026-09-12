from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from services.graduation.paper_shadow import build_closed_outcomes
from services.market_data.kraken_rest import KrakenOHLCClient
from services.market_data.replay import ReplayEngine

ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    pair = os.getenv("O4_KRAKEN_PAIR", "XBTUSD").strip()
    points = int(os.getenv("O4_POINTS", "240"))
    outcomes_required = int(os.getenv("O4_OUTCOMES", "100"))
    horizon_bars = int(os.getenv("O4_HORIZON_BARS", "3"))
    warmup = int(os.getenv("O4_WARMUP", "10"))
    max_age_seconds = float(os.getenv("O4_MAX_SOURCE_AGE_SECONDS", "1800"))

    minimum_points = warmup + horizon_bars + outcomes_required
    if points < minimum_points:
        raise SystemExit(
            "O4_CONFIG_FAIL: O4_POINTS must be >= "
            f"{minimum_points} for the requested outcomes"
        )
    if outcomes_required < 100:
        raise SystemExit("O4_CONFIG_FAIL: O4_OUTCOMES must be >= 100")

    captured_at = datetime.now(timezone.utc)
    stamp = captured_at.strftime("%Y%m%dT%H%M%SZ")
    evidence_rel = Path("evidence/graduation/live/paper-shadow") / stamp
    evidence_dir = ROOT / evidence_rel
    evidence_dir.mkdir(parents=True, exist_ok=False)

    print("==> 01-real-market-capture")
    kraken = KrakenOHLCClient()
    events = kraken.ohlc(pair, interval=1, limit=points, committed_only=True)
    if len(events) < minimum_points:
        raise RuntimeError(
            f"Kraken returned {len(events)} committed bars; need at least {minimum_points}"
        )

    latest_event = max(event.event_time for event in events)
    latest_age_seconds = max(0.0, (captured_at - latest_event).total_seconds())
    if latest_age_seconds > max_age_seconds:
        raise RuntimeError(
            "Kraken source is not recent enough for operational evidence: "
            f"age={latest_age_seconds:.1f}s limit={max_age_seconds:.1f}s"
        )

    raw_capture = evidence_dir / "01-kraken-real-market-capture.jsonl"
    ReplayEngine.write_jsonl(raw_capture, events)
    print(f"O4_REAL_MARKET_CAPTURE_PASS bars={len(events)} pair={pair}")

    print("==> 02-paper-shadow-outcomes")
    evidence_ref_prefix = (
        f"repo:{evidence_rel.as_posix()}/01-kraken-real-market-capture.jsonl"
    )
    outcomes = build_closed_outcomes(
        events,
        count=outcomes_required,
        warmup=warmup,
        horizon_bars=horizon_bars,
        mode="SHADOW",
        source="RECORDED_REAL_MARKET",
        evidence_ref_prefix=evidence_ref_prefix,
    )
    records = [outcome.to_dict() for outcome in outcomes]

    evidence_records = evidence_dir / "02-paper-shadow-records.jsonl"
    canonical_records = ROOT / "evidence/graduation/paper-shadow-records.jsonl"
    _write_jsonl(evidence_records, records)
    _write_jsonl(canonical_records, records)

    realized = [float(record["realized_r"]) for record in records]
    wins = sum(1 for value in realized if value > 0)
    losses = sum(1 for value in realized if value < 0)
    flat = len(realized) - wins - losses
    summary = {
        "captured_at": captured_at.isoformat().replace("+00:00", "Z"),
        "evidence_class": "OPERATIONAL",
        "execution_mode": "SHADOW_ONLY_NO_BROKER_ORDERS",
        "market_source": "KRAKEN_REST",
        "graduation_source": "RECORDED_REAL_MARKET",
        "pair": pair,
        "captured_bars": len(events),
        "latest_event_time": latest_event.isoformat().replace("+00:00", "Z"),
        "latest_age_seconds": round(latest_age_seconds, 3),
        "strategy": records[0]["strategy"],
        "horizon_bars": horizon_bars,
        "closed_outcomes": len(records),
        "unique_signal_ids": len({str(record["signal_id"]) for record in records}),
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "mean_realized_r": round(mean(realized), 8),
        "min_realized_r": round(min(realized), 8),
        "max_realized_r": round(max(realized), 8),
        "canonical_records_path": "evidence/graduation/paper-shadow-records.jsonl",
        "verification": "PAPER_SHADOW_100_OUTCOMES_PASS",
    }
    _write_json(evidence_dir / "03-summary.json", summary)

    git_commit = os.popen(f'git -C "{ROOT}" rev-parse HEAD').read().strip()
    (evidence_dir / "00-summary.txt").write_text(
        "\n".join(
            [
                f"timestamp_utc={stamp}",
                f"git_commit={git_commit}",
                "evidence_class=OPERATIONAL",
                "execution_mode=SHADOW_ONLY_NO_BROKER_ORDERS",
                "source=RECORDED_REAL_MARKET",
                "market_source=KRAKEN_REST",
                f"pair={pair}",
                f"captured_bars={len(events)}",
                f"closed_outcomes={len(records)}",
                f"unique_signal_ids={summary['unique_signal_ids']}",
                "verification=PAPER_SHADOW_100_OUTCOMES_PASS",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "O4_PAPER_SHADOW_100_PASS "
        f"closed={len(records)} unique={summary['unique_signal_ids']} "
        f"wins={wins} losses={losses} flat={flat}"
    )
    print("PAPER_SHADOW_100_OUTCOMES_PASS")
    print(f"Canonical records: {canonical_records}")
    print(f"Evidence directory: {evidence_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
