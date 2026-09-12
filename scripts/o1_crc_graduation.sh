#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/evidence/graduation/live/crc/$STAMP"
mkdir -p "$OUT"

: "${POSTGRES_PASSWORD:?export POSTGRES_PASSWORD before running O1}"
: "${GRAFANA_ADMIN_PASSWORD:?export GRAFANA_ADMIN_PASSWORD before running O1}"

cd "$ROOT"

log() {
  local name="$1"
  shift
  echo "==> $name"
  "$@" 2>&1 | tee "$OUT/$name.txt"
}

# Never print or persist secret values.
log 01-preflight bash scripts/i9_crc_preflight.sh
log 02-crc-status crc status
log 03-oc-version oc version
log 04-nodes oc get nodes -o wide

# Deploy the I9 target slice on CRC using the existing reviewed deployment path.
DEPLOY_MODE="${DEPLOY_MODE:-direct}" bash scripts/i9_crc_deploy.sh 2>&1 | tee "$OUT/05-deploy.txt"

# Verify rollout and target invariants.
bash scripts/i9_crc_verify.sh 2>&1 | tee "$OUT/06-verify.txt"

log 07-pods oc -n tradeops get pods -o wide
log 08-workloads oc -n tradeops get deployment,statefulset
log 09-routes oc -n tradeops get routes
log 10-quotas-policies oc -n tradeops get resourcequota,limitrange,networkpolicy
log 11-services oc -n tradeops get services
log 12-helm helm -n tradeops list

# Resource metrics are useful graduation evidence when the metrics API is available,
# but their absence must not invalidate an otherwise successful CRC deployment.
if oc -n tradeops adm top pods >/dev/null 2>&1; then
  oc -n tradeops adm top pods 2>&1 | tee "$OUT/13-pod-metrics.txt"
else
  echo "metrics API unavailable on this CRC run" | tee "$OUT/13-pod-metrics.txt"
fi

if oc adm top nodes >/dev/null 2>&1; then
  oc adm top nodes 2>&1 | tee "$OUT/14-node-metrics.txt"
else
  echo "metrics API unavailable on this CRC run" | tee "$OUT/14-node-metrics.txt"
fi

AGENT_HOST="$(oc -n tradeops get route agent-controller -o jsonpath='{.spec.host}')"
{
  echo "timestamp_utc=$STAMP"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "crc_version=$(crc version 2>/dev/null | head -n 1 || true)"
  echo "openshift_server=$(oc version -o json 2>/dev/null | python -c 'import json,sys; d=json.load(sys.stdin); print(d.get("openshiftVersion", "unknown"))' || true)"
  echo "namespace=tradeops"
  echo "deployment_mode=${DEPLOY_MODE:-direct}"
  echo "agent_controller_route=https://${AGENT_HOST}"
  echo "verification=I9_CRC_VERIFY_PASS"
  echo "evidence_class=LIVE_OPERATIONAL"
} > "$OUT/00-summary.txt"

curl -fsSk "https://${AGENT_HOST}/health" 2>&1 | tee "$OUT/15-agent-health.txt"

echo "O1_CRC_LIVE_EVIDENCE_PASS"
echo "Evidence directory: $OUT"
