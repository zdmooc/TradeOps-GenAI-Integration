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

# O1_EVIDENCE_ONLY=1 captures evidence from an already validated live CRC
# deployment without rebuilding/redeploying the large runtime image. This avoids
# perturbing the target while preserving the normal deploy path for fresh runs.
if [[ "${O1_EVIDENCE_ONLY:-0}" == "1" ]]; then
  {
    echo "deployment_skipped=true"
    echo "reason=already-validated-live-target"
  } | tee "$OUT/05-deploy.txt"
else
  DEPLOY_MODE="${DEPLOY_MODE:-direct}" bash scripts/i9_crc_deploy.sh 2>&1 | tee "$OUT/05-deploy.txt"
fi

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

oc describe node crc 2>&1 | sed -n '/Conditions:/,/Addresses:/p' | tee "$OUT/15-node-conditions.txt"

AGENT_HOST="$(oc -n tradeops get route agent-controller -o jsonpath='{.spec.host}')"
RAG="$(oc -n tradeops get pods -l app.kubernetes.io/name=rag-api --sort-by=.metadata.creationTimestamp -o name | tail -1)"
RAG_IMAGE_ID="$(oc -n tradeops get "$RAG" -o jsonpath='{.status.containerStatuses[0].imageID}')"

{
  echo "timestamp_utc=$STAMP"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "crc_version=$(crc version 2>/dev/null | head -n 1 || true)"
  echo "openshift_server=$(oc version -o json 2>/dev/null | python -c 'import json,sys; d=json.load(sys.stdin); print(d.get("openshiftVersion", "unknown"))' || true)"
  echo "namespace=tradeops"
  echo "deployment_mode=${DEPLOY_MODE:-direct}"
  echo "evidence_only=${O1_EVIDENCE_ONLY:-0}"
  echo "agent_controller_route=https://${AGENT_HOST}"
  echo "rag_image_id=${RAG_IMAGE_ID}"
  echo "verification=I9_CRC_VERIFY_PASS"
  echo "evidence_class=LIVE_OPERATIONAL"
} > "$OUT/00-summary.txt"

curl -fsSk "https://${AGENT_HOST}/health" 2>&1 | tee "$OUT/16-agent-health.txt"
printf '%s\n' "$RAG_IMAGE_ID" | tee "$OUT/17-rag-image-digest.txt"

# Prove the RAG path end to end: corpus ingestion -> Qdrant -> semantic query.
oc -n tradeops exec "$RAG" -- python -c '
import json, urllib.request

def post(path, payload):
    req = urllib.request.Request(
        "http://127.0.0.1:8014" + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read())

ingest = post("/ingest", {"directory": "/app/rag_corpus"})
query = post("/query", {"question": "risk architecture trading", "top_k": 3})
print("INGEST =", json.dumps(ingest, indent=2))
print("QUERY =", json.dumps(query, indent=2))
assert ingest["ingested"] > 0
assert len(query["hits"]) > 0
print("RAG_END_TO_END_PASS")
' 2>&1 | tee "$OUT/18-rag-e2e.txt"

# Fail closed if either current runtime secret was accidentally written to evidence.
# grep is intentionally quiet so a matching secret is never echoed.
if grep -R -F -q -- "$POSTGRES_PASSWORD" "$OUT" || grep -R -F -q -- "$GRAFANA_ADMIN_PASSWORD" "$OUT"; then
  echo "O1_SECRET_SCAN_FAIL" | tee "$OUT/19-secret-scan.txt"
  exit 1
fi
echo "O1_SECRET_SCAN_PASS" | tee "$OUT/19-secret-scan.txt"

echo "O1_CRC_LIVE_EVIDENCE_PASS"
echo "Evidence directory: $OUT"
