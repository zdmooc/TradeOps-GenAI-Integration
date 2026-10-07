#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STATE_ROOT="${TRADEOPS_PARK_STATE_ROOT:-$ROOT/.runtime/tradeops-park}"
if [[ -f "$STATE_ROOT/LATEST" ]]; then
  SNAPSHOT="$(cat "$STATE_ROOT/LATEST")"
  if [[ -n "$SNAPSHOT" && -f "$SNAPSHOT/status" ]] && grep -qx PARKED "$SNAPSHOT/status"; then
    echo "R5_CRC_RUN_MODE=BOUNDED_FROM_PARK"
    exec bash scripts/crc/r5_crc_mcp_mq_from_park.sh
  fi
fi

echo "R5_CRC_RUN_MODE=FULL_STACK"
bash scripts/r5_crc_mcp_mq_deploy.sh
exec bash scripts/r5_crc_mcp_mq_verify.sh
