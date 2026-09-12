#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/evidence/graduation/live/resilience/$STAMP"
NAMESPACE="${NAMESPACE:-tradeops}"
WORKLOAD="${WORKLOAD:-agent-controller}"
LABEL="app.kubernetes.io/name=${WORKLOAD}"
RECOVERY_TIMEOUT_SECONDS="${RECOVERY_TIMEOUT_SECONDS:-180}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-1}"
LAB_RTO_TARGET_SECONDS="${LAB_RTO_TARGET_SECONDS:-}"

mkdir -p "$OUT"
cd "$ROOT"

if [[ "${ALLOW_CONTROLLED_POD_DELETE:-0}" != "1" ]]; then
  echo "Refusing controlled failure injection. Set ALLOW_CONTROLLED_POD_DELETE=1 for this local CRC drill." >&2
  exit 2
fi

for cmd in oc curl python git; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "Missing required command: $cmd" >&2
    exit 2
  }
done

if ! [[ "$RECOVERY_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( RECOVERY_TIMEOUT_SECONDS < 1 )); then
  echo "RECOVERY_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! [[ "$POLL_INTERVAL_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "POLL_INTERVAL_SECONDS must be numeric." >&2
  exit 2
fi
if [[ -n "$LAB_RTO_TARGET_SECONDS" ]] && ! [[ "$LAB_RTO_TARGET_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "LAB_RTO_TARGET_SECONDS must be numeric when set." >&2
  exit 2
fi

log() {
  local name="$1"
  shift
  echo "==> $name"
  "$@" 2>&1 | tee "$OUT/$name.txt"
}

now_ms() {
  python -c 'import time; print(int(time.time() * 1000))'
}

iso_utc() {
  python -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))'
}

log 01-preflight bash scripts/i9_crc_preflight.sh
log 02-oc-version oc version
log 03-node oc get node crc -o wide

oc -n "$NAMESPACE" get deployment "$WORKLOAD" -o yaml > "$OUT/04-deployment-before.yaml"
oc -n "$NAMESPACE" get pods -l "$LABEL" -o wide > "$OUT/05-pods-before.txt"
oc -n "$NAMESPACE" get route "$WORKLOAD" -o yaml > "$OUT/06-route.yaml"

DESIRED_REPLICAS="$(oc -n "$NAMESPACE" get deployment "$WORKLOAD" -o jsonpath='{.spec.replicas}')"
AVAILABLE_REPLICAS="$(oc -n "$NAMESPACE" get deployment "$WORKLOAD" -o jsonpath='{.status.availableReplicas}')"
if [[ "$DESIRED_REPLICAS" != "1" || "$AVAILABLE_REPLICAS" != "1" ]]; then
  echo "This drill requires exactly one desired and available ${WORKLOAD} replica so the controlled pod loss measures actual service recovery." >&2
  echo "desired=${DESIRED_REPLICAS} available=${AVAILABLE_REPLICAS}" >&2
  exit 2
fi

AGENT_HOST="$(oc -n "$NAMESPACE" get route "$WORKLOAD" -o jsonpath='{.spec.host}')"
OLD_POD="$(oc -n "$NAMESPACE" get pods -l "$LABEL" -o jsonpath='{.items[0].metadata.name}')"
OLD_UID="$(oc -n "$NAMESPACE" get pod "$OLD_POD" -o jsonpath='{.metadata.uid}')"
OLD_READY="$(oc -n "$NAMESPACE" get pod "$OLD_POD" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')"
if [[ "$OLD_READY" != "True" ]]; then
  echo "Refusing failure injection because the baseline pod is not Ready." >&2
  exit 2
fi

curl -fsSk "https://${AGENT_HOST}/health" | tee "$OUT/07-health-before.txt"

if oc adm top nodes >/dev/null 2>&1; then
  oc adm top nodes > "$OUT/08-node-metrics-before.txt"
else
  echo "metrics API unavailable" > "$OUT/08-node-metrics-before.txt"
fi
if oc -n "$NAMESPACE" adm top pods >/dev/null 2>&1; then
  oc -n "$NAMESPACE" adm top pods > "$OUT/09-pod-metrics-before.txt"
else
  echo "metrics API unavailable" > "$OUT/09-pod-metrics-before.txt"
fi

START_ISO="$(iso_utc)"
START_MS="$(now_ms)"
{
  echo "failure_injection_start_utc=${START_ISO}"
  echo "old_pod=${OLD_POD}"
  echo "old_uid=${OLD_UID}"
  echo "action=oc delete pod --wait=false"
} > "$OUT/10-failure-injection.txt"

oc -n "$NAMESPACE" delete pod "$OLD_POD" --wait=false \
  2>&1 | tee -a "$OUT/10-failure-injection.txt"

printf 'elapsed_ms\thttp_code\tnew_pod\tnew_uid\tready\n' > "$OUT/11-recovery-probes.tsv"

RECOVERED=0
NEW_POD=""
NEW_UID=""
while true; do
  NOW_MS="$(now_ms)"
  ELAPSED_MS="$((NOW_MS - START_MS))"

  HTTP_CODE="$(curl -sSk -o /dev/null -w '%{http_code}' "https://${AGENT_HOST}/health" || true)"
  POD_INFO="$(
    OLD_UID="$OLD_UID" oc -n "$NAMESPACE" get pods -l "$LABEL" -o json 2>/dev/null \
      | python -c '
import json, os, sys
data = json.load(sys.stdin)
old_uid = os.environ["OLD_UID"]
candidates = []
for item in data.get("items", []):
    uid = item.get("metadata", {}).get("uid", "")
    if not uid or uid == old_uid:
        continue
    ready = "False"
    for condition in item.get("status", {}).get("conditions", []):
        if condition.get("type") == "Ready":
            ready = condition.get("status", "False")
            break
    candidates.append((
        item.get("metadata", {}).get("creationTimestamp", ""),
        item.get("metadata", {}).get("name", ""),
        uid,
        ready,
    ))
if candidates:
    _, name, uid, ready = sorted(candidates)[-1]
    print(f"{name}\t{uid}\t{ready}")
' || true
  )"

  if [[ -n "$POD_INFO" ]]; then
    IFS=$'\t' read -r NEW_POD NEW_UID NEW_READY <<< "$POD_INFO"
  else
    NEW_POD=""
    NEW_UID=""
    NEW_READY="False"
  fi

  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$ELAPSED_MS" "${HTTP_CODE:-000}" "$NEW_POD" "$NEW_UID" "$NEW_READY" \
    >> "$OUT/11-recovery-probes.tsv"

  if [[ -n "$NEW_UID" && "$NEW_UID" != "$OLD_UID" && "$NEW_READY" == "True" && "$HTTP_CODE" == "200" ]]; then
    RECOVERED=1
    break
  fi

  if (( ELAPSED_MS >= RECOVERY_TIMEOUT_SECONDS * 1000 )); then
    break
  fi
  sleep "$POLL_INTERVAL_SECONDS"
done

END_ISO="$(iso_utc)"
END_MS="$(now_ms)"
RECOVERY_MS="$((END_MS - START_MS))"
RECOVERY_SECONDS="$(python - "$RECOVERY_MS" <<'PY'
import sys
print(f"{int(sys.argv[1]) / 1000:.3f}")
PY
)"

oc -n "$NAMESPACE" get deployment "$WORKLOAD" -o yaml > "$OUT/12-deployment-after.yaml"
oc -n "$NAMESPACE" get pods -l "$LABEL" -o wide > "$OUT/13-pods-after.txt"
oc -n "$NAMESPACE" get events --sort-by=.lastTimestamp > "$OUT/14-events-after.txt" || true
curl -sSk -D "$OUT/15-health-after-headers.txt" \
  "https://${AGENT_HOST}/health" -o "$OUT/15-health-after.txt" || true

if oc adm top nodes >/dev/null 2>&1; then
  oc adm top nodes > "$OUT/16-node-metrics-after.txt"
else
  echo "metrics API unavailable" > "$OUT/16-node-metrics-after.txt"
fi
if oc -n "$NAMESPACE" adm top pods >/dev/null 2>&1; then
  oc -n "$NAMESPACE" adm top pods > "$OUT/17-pod-metrics-after.txt"
else
  echo "metrics API unavailable" > "$OUT/17-pod-metrics-after.txt"
fi

TARGET_RESULT="NOT_EVALUATED"
if [[ -n "$LAB_RTO_TARGET_SECONDS" ]]; then
  TARGET_RESULT="$(
    python - "$RECOVERY_SECONDS" "$LAB_RTO_TARGET_SECONDS" <<'PY'
import sys
observed = float(sys.argv[1])
target = float(sys.argv[2])
print("PASS" if observed <= target else "FAIL")
PY
  )"
fi

{
  echo "timestamp_utc=${STAMP}"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "evidence_class=LIVE_OPERATIONAL"
  echo "scope=LOCAL_CRC_CONTROLLED_FAILURE"
  echo "namespace=${NAMESPACE}"
  echo "workload=${WORKLOAD}"
  echo "failure_action=DELETE_SINGLE_POD"
  echo "old_pod=${OLD_POD}"
  echo "old_uid=${OLD_UID}"
  echo "new_pod=${NEW_POD}"
  echo "new_uid=${NEW_UID}"
  echo "failure_start_utc=${START_ISO}"
  echo "recovery_end_utc=${END_ISO}"
  echo "observed_recovery_seconds=${RECOVERY_SECONDS}"
  echo "lab_rto_target_seconds=${LAB_RTO_TARGET_SECONDS:-NOT_SET}"
  echo "lab_rto_target_result=${TARGET_RESULT}"
  echo "rpo_applicable=false"
  echo "rpo_reason=stateless-pod-recreation-no-persistent-store-failure-injected"
  echo "data_loss_claim=NOT_MEASURED_NOT_APPLICABLE_TO_THIS_DRILL"
  echo "provider_cost_claim=NOT_MEASURED_ON_LOCAL_CRC"
  echo "carbon_claim=NOT_MEASURED"
  echo "full_resilience_finops_greenops_gate_claim=false"
  echo "verification=$([[ "$RECOVERED" == "1" ]] && echo CRC_RESILIENCE_DRILL_PASS || echo CRC_RESILIENCE_DRILL_FAIL)"
} > "$OUT/00-summary.txt"

if grep -R -Eqi '(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|password[[:space:]]*[:=][[:space:]]*[^[:space:]]+|bearer[[:space:]]+[A-Za-z0-9._~-]{16,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+)' "$OUT"; then
  echo "O5_SECRET_SCAN_FAIL" > "$OUT/18-secret-scan.txt"
  exit 1
fi
echo "O5_SECRET_SCAN_PASS" > "$OUT/18-secret-scan.txt"

if [[ "$RECOVERED" != "1" ]]; then
  echo "CRC_RESILIENCE_DRILL_FAIL recovery_timeout_seconds=${RECOVERY_TIMEOUT_SECONDS}" >&2
  echo "Evidence directory: $OUT" >&2
  exit 1
fi

if [[ "$TARGET_RESULT" == "FAIL" ]]; then
  echo "CRC_RESILIENCE_DRILL_PASS but LAB_RTO_TARGET_MISSED observed=${RECOVERY_SECONDS}s target=${LAB_RTO_TARGET_SECONDS}s" >&2
  echo "Evidence directory: $OUT" >&2
  exit 3
fi

echo "CRC_RESILIENCE_DRILL_PASS observed_recovery_seconds=${RECOVERY_SECONDS}"
echo "Evidence directory: $OUT"
