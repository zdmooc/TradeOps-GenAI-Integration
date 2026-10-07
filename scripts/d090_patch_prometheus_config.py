#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys


JOB_LINES = [
    "  - job_name: ai-access-policy",
    "    metrics_path: /metrics",
    "    static_configs:",
    '      - targets: ["ai-access-policy:8020"]',
]


def ensure_ai_access_scrape(config: str) -> tuple[str, bool]:
    if "ai-access-policy:8020" in config:
        return config, False

    lines = config.splitlines()
    scrape_index = None
    for index, line in enumerate(lines):
        if line == "scrape_configs:":
            scrape_index = index
            break

    if scrape_index is None:
        raise ValueError("top-level scrape_configs section missing")

    insert_index = len(lines)
    for index in range(scrape_index + 1, len(lines)):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            insert_index = index
            break

    lines[insert_index:insert_index] = JOB_LINES
    rendered = "\n".join(lines)
    if config.endswith("\n"):
        rendered += "\n"
    return rendered, True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Read Prometheus YAML from this file instead of stdin")
    args = parser.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as handle:
            config = handle.read()
    else:
        config = sys.stdin.read()

    try:
        rendered, changed = ensure_ai_access_scrape(config)
    except ValueError as exc:
        print(f"D090_G2_PROMETHEUS_PATCH_FAIL: {exc}", file=sys.stderr)
        return 2

    sys.stdout.write(rendered)
    print(
        f"D090_G2_PROMETHEUS_PATCH={'CHANGED' if changed else 'ALREADY_PRESENT'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
