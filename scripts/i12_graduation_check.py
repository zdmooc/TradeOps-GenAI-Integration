#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.graduation.gate import evaluate_manifest, load_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate I12 Excellence graduation evidence")
    parser.add_argument(
        "--manifest",
        default=str(ROOT / "data" / "graduation" / "i12_graduation_manifest.json"),
    )
    parser.add_argument("--expect-status", choices=("GRADUATED", "NOT_GRADUATED"))
    parser.add_argument("--require-graduated", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    report = evaluate_manifest(manifest, repo_root=ROOT)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))

    if report.errors:
        return 2
    if args.expect_status and report.status != args.expect_status:
        return 3
    if args.require_graduated and report.status != "GRADUATED":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
