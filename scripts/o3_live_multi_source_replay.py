from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from services.market_data.ig_rest import IGRestClient
from services.market_data.kraken_rest import KrakenOHLCClient
from services.market_data.replay import ReplayEngine

ROOT = Path(__file__).resolve().parents[1]


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"O3_CONFIG_FAIL: required environment variable {name} is not set")
    return value


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _json_dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_age_seconds(events, now: datetime) -> float:
    latest = max(event.event_time for event in events)
    return max(0.0, (now - latest).total_seconds())


def _scan_secret_values(directory: Path, secret_values: list[str]) -> None:
    files = [path for path in directory.rglob("*") if path.is_file()]
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for value in secret_values:
            if value and value in text:
                raise RuntimeError(f"secret value detected in evidence file {path.name}")


def main() -> int:
    api_key = _required_env("IG_API_KEY")
    identifier = _required_env("IG_IDENTIFIER")
    password = _required_env("IG_PASSWORD")

    ig_env = os.getenv("IG_ENV", "demo").strip().lower()
    if ig_env == "demo":
        ig_base_url = IGRestClient.DEMO_BASE_URL
    elif ig_env == "live":
        ig_base_url = IGRestClient.LIVE_BASE_URL
    else:
        raise SystemExit("O3_CONFIG_FAIL: IG_ENV must be 'demo' or 'live'")

    ig_epic = os.getenv("IG_EPIC", "CS.D.BITCOIN.CFD.IP").strip()
    kraken_pair = os.getenv("KRAKEN_PAIR", "XBTUSD").strip()
    points = int(os.getenv("O3_POINTS", "20"))
    max_age_seconds = float(os.getenv("O3_MAX_SOURCE_AGE_SECONDS", "1800"))
    if points < 2:
        raise SystemExit("O3_CONFIG_FAIL: O3_POINTS must be >= 2")

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = ROOT / "evidence" / "graduation" / "live" / "market-data" / stamp
    evidence_dir.mkdir(parents=True, exist_ok=False)

    print("==> 01-live-acquisition")
    ig = IGRestClient(
        api_key=api_key,
        identifier=identifier,
        password=password,
        base_url=ig_base_url,
    )
    session = ig.authenticate_v2()
    ig_events = ig.historical_prices(
        ig_epic,
        resolution="MINUTE",
        max_points=points,
        page_size=min(points, 100),
    )
    if not ig_events:
        raise RuntimeError("IG live acquisition returned zero market events")

    kraken = KrakenOHLCClient()
    kraken_events = kraken.ohlc(
        kraken_pair,
        interval=1,
        limit=points,
        committed_only=True,
    )
    if not kraken_events:
        raise RuntimeError("Kraken live acquisition returned zero committed market events")

    source_set = {event.source for event in ig_events + kraken_events}
    if source_set != {"IG_REST", "KRAKEN_REST"}:
        raise RuntimeError(f"expected two independent sources, got {sorted(source_set)!r}")

    ig_age = _source_age_seconds(ig_events, now)
    kraken_age = _source_age_seconds(kraken_events, now)
    if ig_age > max_age_seconds:
        raise RuntimeError(
            f"IG source is not recent enough for live evidence: age={ig_age:.1f}s "
            f"limit={max_age_seconds:.1f}s"
        )
    if kraken_age > max_age_seconds:
        raise RuntimeError(
            f"Kraken source is not recent enough for live evidence: age={kraken_age:.1f}s "
            f"limit={max_age_seconds:.1f}s"
        )

    ReplayEngine.write_jsonl(evidence_dir / "01-ig-capture.jsonl", ig_events)
    ReplayEngine.write_jsonl(evidence_dir / "02-kraken-capture.jsonl", kraken_events)
    combined = sorted(ig_events + kraken_events, key=lambda event: (event.event_time, event.event_id))
    ReplayEngine.write_jsonl(evidence_dir / "03-combined-capture.jsonl", combined)

    acquisition = {
        "captured_at": now.isoformat().replace("+00:00", "Z"),
        "ig": {
            "environment": ig_env,
            "epic": ig_epic,
            "events": len(ig_events),
            "latest_event_time": max(event.event_time for event in ig_events)
            .isoformat()
            .replace("+00:00", "Z"),
            "latest_age_seconds": round(ig_age, 3),
            "authenticated_account_present": bool(session.account_id),
        },
        "kraken": {
            "pair": kraken_pair,
            "events": len(kraken_events),
            "latest_event_time": max(event.event_time for event in kraken_events)
            .isoformat()
            .replace("+00:00", "Z"),
            "latest_age_seconds": round(kraken_age, 3),
            "committed_only": True,
        },
        "source_count": len(source_set),
        "sources": sorted(source_set),
        "max_source_age_seconds": max_age_seconds,
    }
    _json_dump(evidence_dir / "04-acquisition-summary.json", acquisition)
    print(
        f"O3_LIVE_ACQUISITION_PASS sources={len(source_set)} "
        f"ig_events={len(ig_events)} kraken_events={len(kraken_events)}"
    )

    print("==> 02-deterministic-replay")
    captured = ReplayEngine.load_jsonl(evidence_dir / "03-combined-capture.jsonl")
    first = ReplayEngine().replay(captured)
    second = ReplayEngine().replay(captured)

    first_payload = [event.to_dict() for event in first.accepted]
    second_payload = [event.to_dict() for event in second.accepted]
    if first_payload != second_payload:
        raise RuntimeError("deterministic replay mismatch")
    if len(first.accepted) != len(captured):
        rejected = [
            {
                "event_id": record.event.event_id,
                "source": record.event.source,
                "reasons": [reason.value for reason in record.quality.reasons],
            }
            for record in first.rejected
        ]
        _json_dump(evidence_dir / "05-rejected-events.json", rejected)
        raise RuntimeError(
            f"replay quality gate rejected {len(first.rejected)} of {len(captured)} captured events"
        )

    replay_summary = {
        "captured": len(captured),
        "accepted": len(first.accepted),
        "rejected": len(first.rejected),
        "sources": sorted({event.source for event in first.accepted}),
        "deterministic_second_run_equal": first_payload == second_payload,
        "first_event_time": first.accepted[0].event_time.isoformat().replace("+00:00", "Z"),
        "last_event_time": first.accepted[-1].event_time.isoformat().replace("+00:00", "Z"),
    }
    _json_dump(evidence_dir / "06-replay-summary.json", replay_summary)
    print(f"O3_DETERMINISTIC_REPLAY_PASS accepted={len(first.accepted)} rejected=0")

    print("==> 03-secret-scan")
    _scan_secret_values(evidence_dir, [api_key, identifier, password])
    _write_text(evidence_dir / "07-secret-scan.txt", "O3_SECRET_SCAN_PASS")
    print("O3_SECRET_SCAN_PASS")

    git_commit = os.popen(f'git -C "{ROOT}" rev-parse HEAD').read().strip()
    summary = "\n".join(
        [
            f"timestamp_utc={stamp}",
            f"git_commit={git_commit}",
            "evidence_class=LIVE_OPERATIONAL",
            f"ig_environment={ig_env}",
            f"ig_epic={ig_epic}",
            f"kraken_pair={kraken_pair}",
            "sources=IG_REST,KRAKEN_REST",
            f"captured_events={len(captured)}",
            f"accepted_events={len(first.accepted)}",
            "deterministic_replay=true",
            "secret_scan=PASS",
            "verification=LIVE_MULTI_SOURCE_REPLAY_PASS",
        ]
    )
    _write_text(evidence_dir / "00-summary.txt", summary)

    print("LIVE_MULTI_SOURCE_REPLAY_PASS")
    print(f"Evidence directory: {evidence_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
