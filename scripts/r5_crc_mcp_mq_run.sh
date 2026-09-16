#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash scripts/r5_crc_mcp_mq_deploy.sh
exec bash scripts/r5_crc_mcp_mq_verify.sh
