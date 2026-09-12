#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

for name in IG_API_KEY IG_IDENTIFIER IG_PASSWORD; do
  if [[ -z "${!name:-}" ]]; then
    echo "O3_CONFIG_FAIL: $name is not set" >&2
    exit 2
  fi
done

python scripts/o3_live_multi_source_replay.py
