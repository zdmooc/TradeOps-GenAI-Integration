#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

command -v oc >/dev/null 2>&1 || { echo "TRADEOPS_DEMO_PREFLIGHT=FAIL reason=oc_missing"; exit 2; }
server="$(oc whoami --show-server 2>/dev/null)" || { echo "TRADEOPS_DEMO_PREFLIGHT=FAIL reason=not_logged_in"; exit 2; }
if [[ "$server" != "https://api.crc.testing:6443" ]]; then
  echo "TRADEOPS_DEMO_PREFLIGHT=FAIL reason=not_crc server=$server"
  exit 2
fi
oc get namespace tradeops >/dev/null
echo "TRADEOPS_DEMO_CONTEXT=CRC"
echo "TRADEOPS_DEMO_GIT_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
oc get clusterversion version
oc get nodes -o wide
oc -n tradeops get deployments,statefulsets -o wide

status="NOT_CONFIRMED"
pointer="$ROOT/.runtime/tradeops-park/LATEST"
if [[ -f "$pointer" ]]; then
  snapshot="$(cat "$pointer")"
  if [[ -n "$snapshot" && -f "$snapshot/status" ]]; then
    status="$(head -n 1 "$snapshot/status")"
  fi
fi
echo "TRADEOPS_DEMO_PARK_SNAPSHOT_STATUS=$status"
agent_replicas="$(oc -n tradeops get deployment agent-controller -o jsonpath='{.spec.replicas}' 2>/dev/null || true)"
echo "TRADEOPS_DEMO_AGENT_CONTROLLER_DESIRED=${agent_replicas:-NOT_FOUND}"
if [[ "$status" == "PARKED" && "$agent_replicas" != "0" ]]; then
  echo "TRADEOPS_DEMO_PREFLIGHT=FAIL reason=park_snapshot_runtime_divergence"
  exit 3
fi
echo "TRADEOPS_DEMO_PREFLIGHT=PASS"
echo "TRADEOPS_DEMO_MODE=READ_ONLY"
echo "TRADEOPS_DEMO_CLAIM=CLUSTER_OBSERVED_NOT_FULL_APP_E2E"
