from pathlib import Path

from services.market_data.replay import ReplayEngine


def main() -> None:
    path = Path("data/replay/sample_market_events.jsonl")
    events = ReplayEngine.load_jsonl(path)
    result = ReplayEngine().replay(events)
    print(f"replay_file={path}")
    print(f"accepted={len(result.accepted)} rejected={len(result.rejected)}")
    for event in result.accepted:
        print(
            f"{event.event_time.isoformat()} {event.instrument} "
            f"bid={event.bid} ask={event.ask} spread={event.spread}"
        )


if __name__ == "__main__":
    main()
