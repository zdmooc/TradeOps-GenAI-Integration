#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="${TRADEOPS_NAMESPACE:-tradeops}"
STATE_ROOT="${TRADEOPS_PARK_STATE_ROOT:-$ROOT/.runtime/tradeops-park}"
SNAPSHOT="${TRADEOPS_PARK_SNAPSHOT:-}"
GITOPS_NAMESPACE="${TRADEOPS_GITOPS_NAMESPACE:-openshift-gitops}"

for cmd in oc python; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "T2_CAPACITY_GITOPS_FAIL: missing required command: $cmd" >&2
    exit 2
  fi
done

if [[ -z "$SNAPSHOT" ]]; then
  if [[ ! -f "$STATE_ROOT/LATEST" ]]; then
    echo "T2_CAPACITY_GITOPS_FAIL: no PARK snapshot found" >&2
    exit 2
  fi
  SNAPSHOT="$(cat "$STATE_ROOT/LATEST")"
fi

if [[ ! -f "$SNAPSHOT/status" ]] || ! grep -qx "PARKED" "$SNAPSHOT/status"; then
  echo "T2_CAPACITY_GITOPS_FAIL: TradeOps must be PARKED before T2 capacity evidence" >&2
  exit 2
fi

for required in   "$SNAPSHOT/10-cluster-pods-before.json"   "$SNAPSHOT/11-nodes-before.json"   "$SNAPSHOT/25-cluster-pods-after.json"   "$SNAPSHOT/26-nodes-after.json"; do
  if [[ ! -s "$required" ]]; then
    echo "T2_CAPACITY_GITOPS_FAIL: required structured PARK evidence missing: $required" >&2
    exit 2
  fi
done

oc whoami >/dev/null
oc get namespace "$NAMESPACE" >/dev/null
oc get namespace "$GITOPS_NAMESPACE" >/dev/null

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$SNAPSHOT/t2-$STAMP"
mkdir -p "$OUT"

oc get pods -A -o json > "$OUT/current-pods.json"
oc get nodes -o json > "$OUT/current-nodes.json"
oc get clusteroperators.config.openshift.io -o json > "$OUT/clusteroperators.json"
oc -n "$GITOPS_NAMESPACE" get pods -o json > "$OUT/gitops-pods.json"

if oc api-resources --api-group=argoproj.io -o name 2>/dev/null | grep -qx 'applications.argoproj.io'; then
  oc get applications.argoproj.io -A -o json > "$OUT/argocd-applications.json"
else
  echo "T2_CAPACITY_GITOPS_FAIL: Argo CD Application CRD is not available" >&2
  exit 1
fi

oc get pods -A --field-selector=status.phase=Pending -o wide > "$OUT/pending-pods.txt" 2>&1 || true
oc adm top nodes > "$OUT/top-nodes.txt" 2>&1 || true
oc adm top pods -n "$NAMESPACE" > "$OUT/top-tradeops.txt" 2>&1 || true
oc -n "$GITOPS_NAMESPACE" get deployment,statefulset,pods -o wide > "$OUT/gitops-workloads.txt" 2>&1 || true
oc get events -A --field-selector=reason=FailedScheduling --sort-by=.lastTimestamp > "$OUT/failed-scheduling-events.txt" 2>&1 || true

python "$ROOT/scripts/crc/k8s_capacity_summary.py"   --pods "$SNAPSHOT/10-cluster-pods-before.json"   --nodes "$SNAPSHOT/11-nodes-before.json"   --output "$OUT/capacity-before.json" >/dev/null

python "$ROOT/scripts/crc/k8s_capacity_summary.py"   --pods "$SNAPSHOT/25-cluster-pods-after.json"   --nodes "$SNAPSHOT/26-nodes-after.json"   --output "$OUT/capacity-immediate-after-park.json" >/dev/null

python "$ROOT/scripts/crc/k8s_capacity_summary.py"   --pods "$OUT/current-pods.json"   --nodes "$OUT/current-nodes.json"   --output "$OUT/capacity-current.json" >/dev/null

python -   "$OUT/capacity-before.json"   "$OUT/capacity-immediate-after-park.json"   "$OUT/capacity-current.json"   "$OUT/capacity-delta.txt" <<'PY'
import json
import sys

before_path, after_path, current_path, output_path = sys.argv[1:5]
before = json.load(open(before_path, encoding="utf-8"))
after = json.load(open(after_path, encoding="utf-8"))
current = json.load(open(current_path, encoding="utf-8"))


def value(payload, section, key):
    return payload.get(section, {}).get(key, 0)


markers = {
    "T2_BEFORE_ACTIVE_PODS": value(before, "pods", "active"),
    "T2_AFTER_PARK_ACTIVE_PODS": value(after, "pods", "active"),
    "T2_CURRENT_ACTIVE_PODS": value(current, "pods", "active"),
    "T2_BEFORE_PENDING_PODS": value(before, "pods", "pending"),
    "T2_AFTER_PARK_PENDING_PODS": value(after, "pods", "pending"),
    "T2_CURRENT_PENDING_PODS": value(current, "pods", "pending"),
    "T2_BEFORE_UNSCHEDULED_MEMORY_MIB": value(before, "requests", "unscheduled_memory_mib"),
    "T2_AFTER_PARK_UNSCHEDULED_MEMORY_MIB": value(after, "requests", "unscheduled_memory_mib"),
    "T2_CURRENT_UNSCHEDULED_MEMORY_MIB": value(current, "requests", "unscheduled_memory_mib"),
    "T2_BEFORE_SCHEDULED_MEMORY_MIB": value(before, "requests", "scheduled_memory_mib"),
    "T2_AFTER_PARK_SCHEDULED_MEMORY_MIB": value(after, "requests", "scheduled_memory_mib"),
    "T2_CURRENT_SCHEDULED_MEMORY_MIB": value(current, "requests", "scheduled_memory_mib"),
    "T2_CURRENT_MEMORY_PRESSURE_PODS": value(
        current, "pods", "unscheduled_insufficient_memory"
    ),
    "T2_CURRENT_CPU_PRESSURE_PODS": value(current, "pods", "unscheduled_insufficient_cpu"),
}
markers["T2_IMMEDIATE_SCHEDULED_MEMORY_DELTA_MIB"] = (
    markers["T2_AFTER_PARK_SCHEDULED_MEMORY_MIB"] - markers["T2_BEFORE_SCHEDULED_MEMORY_MIB"]
)
markers["T2_CURRENT_SCHEDULED_MEMORY_DELTA_MIB"] = (
    markers["T2_CURRENT_SCHEDULED_MEMORY_MIB"] - markers["T2_BEFORE_SCHEDULED_MEMORY_MIB"]
)

with open(output_path, "w", encoding="utf-8") as handle:
    for key, val in markers.items():
        line = f"{key}={val}"
        print(line)
        handle.write(line + "\n")
PY

if ! python - "$OUT/gitops-pods.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
active = []
problems = []
for pod in data.get("items", []):
    name = pod.get("metadata", {}).get("name", "?")
    phase = pod.get("status", {}).get("phase", "Unknown")
    if phase in {"Succeeded"}:
        continue
    active.append(name)
    statuses = pod.get("status", {}).get("containerStatuses") or []
    ready = phase == "Running" and statuses and all(item.get("ready") for item in statuses)
    if not ready:
        problems.append(f"{name}:{phase}")

if not active:
    print("T2_GITOPS_CORE_FAIL: no active pod in GitOps namespace", file=sys.stderr)
    raise SystemExit(1)
if problems:
    print("T2_GITOPS_CORE_FAIL: " + ", ".join(problems), file=sys.stderr)
    raise SystemExit(1)
print(f"T2_GITOPS_READY_PODS={len(active)}")
PY
then
  exit 1
fi

if ! python - "$OUT/clusteroperators.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
bad = []
for operator in data.get("items", []):
    name = operator.get("metadata", {}).get("name", "?")
    conditions = {
        item.get("type"): item.get("status")
        for item in operator.get("status", {}).get("conditions") or []
    }
    if (
        conditions.get("Available") != "True"
        or conditions.get("Degraded") == "True"
        or conditions.get("Progressing") == "True"
    ):
        bad.append(
            f"{name}:Available={conditions.get('Available')},"
            f"Progressing={conditions.get('Progressing')},"
            f"Degraded={conditions.get('Degraded')}"
        )

if bad:
    print("T2_CLUSTEROPERATORS_FAIL:", file=sys.stderr)
    for item in bad:
        print(f"  - {item}", file=sys.stderr)
    raise SystemExit(1)
print("T2_CLUSTEROPERATORS_HEALTH=PASS")
PY
then
  exit 1
fi

memory_pressure="$(awk -F= '$1=="T2_CURRENT_MEMORY_PRESSURE_PODS" {print $2}' "$OUT/capacity-delta.txt")"
cpu_pressure="$(awk -F= '$1=="T2_CURRENT_CPU_PRESSURE_PODS" {print $2}' "$OUT/capacity-delta.txt")"

if [[ "$memory_pressure" != "0" || "$cpu_pressure" != "0" ]]; then
  echo "T2_SCHEDULER_PRESSURE_FAIL: memory=$memory_pressure cpu=$cpu_pressure" >&2
  exit 1
fi

echo "T2_CAPACITY_EVIDENCE_CAPTURED=PASS"
echo "T2_SCHEDULER_CAPACITY_GATE=PASS"
echo "T2_GITOPS_CORE=PASS"
echo "T2_CAPACITY_GITOPS_GATE=PASS"
echo "T2_EVIDENCE=$OUT"
