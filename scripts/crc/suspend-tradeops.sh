#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="${TRADEOPS_NAMESPACE:-tradeops}"
STATE_ROOT="${TRADEOPS_PARK_STATE_ROOT:-$ROOT/.runtime/tradeops-park}"
MODE="${TRADEOPS_PARK_MODE:-normal}"
DEEP_CONFIRM="${TRADEOPS_DEEP_PARK_CONFIRM_TSDB_LOSS:-no}"

case "$MODE" in
  normal|deep) ;;
  *)
    echo "TRADEOPS_PARK_FAIL: TRADEOPS_PARK_MODE must be normal or deep" >&2
    exit 2
    ;;
esac

if [[ "$MODE" == "deep" && "$DEEP_CONFIRM" != "yes" ]]; then
  echo "TRADEOPS_PARK_FAIL: deep mode deletes Prometheus emptyDir/TSDB when its pod is removed." >&2
  echo "Set TRADEOPS_DEEP_PARK_CONFIRM_TSDB_LOSS=yes only when that loss is accepted." >&2
  exit 2
fi

for cmd in oc python; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "TRADEOPS_PARK_FAIL: missing required command: $cmd" >&2
    exit 2
  fi
done

oc whoami >/dev/null
oc get namespace "$NAMESPACE" >/dev/null

mkdir -p "$STATE_ROOT"
LATEST_FILE="$STATE_ROOT/LATEST"

if [[ -f "$LATEST_FILE" ]]; then
  previous="$(cat "$LATEST_FILE")"
  if [[ -n "$previous" && -f "$previous/status" ]] && grep -qx "PARKED" "$previous/status"; then
    echo "TRADEOPS_PARK_ALREADY_ACTIVE=PASS"
    echo "TRADEOPS_PARK_SNAPSHOT=$previous"
    exit 0
  fi
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$STATE_ROOT/$STAMP"
mkdir -p "$OUT"

MUTATION_STARTED=0

rollback_on_error() {
  rc=$?
  trap - ERR INT TERM
  if [[ "$MUTATION_STARTED" == "1" && -f "$OUT/deployments.tsv" ]]; then
    echo "TRADEOPS_PARK_ROLLBACK: restoring deployment replicas from snapshot" >&2
    while IFS=$'\t' read -r name replicas; do
      [[ -n "$name" ]] || continue
      oc -n "$NAMESPACE" scale "deployment/$name" --replicas="$replicas" >/dev/null 2>&1 || true
    done < "$OUT/deployments.tsv"
  fi
  echo "TRADEOPS_PARK_FAIL: no stateful workload was intentionally scaled" >&2
  exit "$rc"
}
trap rollback_on_error ERR INT TERM

capture_best_effort() {
  local file="$1"
  shift
  {
    "$@"
  } >"$OUT/$file" 2>&1 || true
}

capture_best_effort 00-whoami.txt oc whoami
capture_best_effort 01-project.txt oc project
capture_best_effort 02-pods-before.txt oc -n "$NAMESPACE" get pods -o wide
capture_best_effort 03-workloads-before.txt oc -n "$NAMESPACE" get deployment,statefulset -o wide
capture_best_effort 04-top-before.txt oc adm top pods -n "$NAMESPACE"
capture_best_effort 05-quota-before.txt oc -n "$NAMESPACE" get resourcequota,limitrange
capture_best_effort 06-hpa-before.txt oc -n "$NAMESPACE" get hpa
capture_best_effort 07-cronjobs-before.txt oc -n "$NAMESPACE" get cronjobs.batch
capture_best_effort 08-cluster-pending-before.txt oc get pods -A --field-selector=status.phase=Pending -o wide
capture_best_effort 09-node-describe-before.txt oc describe node
capture_best_effort 10-cluster-pods-before.json oc get pods -A -o json
capture_best_effort 11-nodes-before.json oc get nodes -o json

oc -n "$NAMESPACE" get deployments.apps -o json > "$OUT/deployments.json"
oc -n "$NAMESPACE" get statefulsets.apps -o json > "$OUT/statefulsets.json"
oc -n "$NAMESPACE" get hpa.autoscaling -o json > "$OUT/hpa.json"
oc -n "$NAMESPACE" get cronjobs.batch -o json > "$OUT/cronjobs.json"

python - "$OUT/deployments.json" "$OUT/deployments.tsv" <<'PY'
import json
import sys

src, dst = sys.argv[1:3]
data = json.load(open(src, encoding="utf-8"))
items = sorted(data.get("items", []), key=lambda item: item["metadata"]["name"])
if not items:
    raise SystemExit("TRADEOPS_PARK_FAIL: no deployments found in namespace")
with open(dst, "w", encoding="utf-8", newline="") as handle:
    for item in items:
        name = item["metadata"]["name"]
        replicas = item.get("spec", {}).get("replicas", 1)
        handle.write(f"{name}\t{replicas}\n")
PY

python - "$OUT/statefulsets.json" "$OUT/statefulsets.tsv" <<'PY'
import json
import sys

src, dst = sys.argv[1:3]
data = json.load(open(src, encoding="utf-8"))
items = sorted(data.get("items", []), key=lambda item: item["metadata"]["name"])
with open(dst, "w", encoding="utf-8", newline="") as handle:
    for item in items:
        name = item["metadata"]["name"]
        replicas = item.get("spec", {}).get("replicas", 1)
        handle.write(f"{name}\t{replicas}\n")
PY

python - "$OUT/deployments.tsv" "$OUT/park-targets.tsv" "$MODE" <<'PY'
import sys

src, dst, mode = sys.argv[1:4]
protected = set() if mode == "deep" else {"prometheus"}
with open(dst, "w", encoding="utf-8", newline="") as out:
    for raw in open(src, encoding="utf-8"):
        name, replicas = raw.rstrip("\n").split("\t", 1)
        if name not in protected:
            out.write(f"{name}\t{replicas}\n")
PY

if oc api-resources --api-group=argoproj.io -o name 2>/dev/null | grep -qx 'applications.argoproj.io'; then
  oc get applications.argoproj.io -A -o json > "$OUT/argocd-applications.json"
  if ! python - "$OUT/argocd-applications.json" "$NAMESPACE" <<'PY'
import json
import sys

path, namespace = sys.argv[1:3]
data = json.load(open(path, encoding="utf-8"))
blockers = []
for item in data.get("items", []):
    spec = item.get("spec", {})
    destination = spec.get("destination", {})
    automated = (spec.get("syncPolicy") or {}).get("automated")
    if destination.get("namespace") == namespace and automated is not None:
        meta = item.get("metadata", {})
        blockers.append(f"{meta.get('namespace', '?')}/{meta.get('name', '?')}")
if blockers:
    print("TRADEOPS_PARK_FAIL: automated Argo CD application(s) target the namespace:", file=sys.stderr)
    for blocker in blockers:
        print(f"  - {blocker}", file=sys.stderr)
    print("Disable/suspend the owning GitOps reconciliation through its approved procedure before PARK.", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    exit 1
  fi
else
  printf '%s\n' "Argo CD Application CRD not present" > "$OUT/argocd-applications.txt"
fi

if ! python - "$OUT/hpa.json" "$OUT/park-targets.tsv" <<'PY'
import json
import sys

hpa_path, targets_path = sys.argv[1:3]
targets = {line.split("\t", 1)[0] for line in open(targets_path, encoding="utf-8") if line.strip()}
data = json.load(open(hpa_path, encoding="utf-8"))
blockers = []
for item in data.get("items", []):
    ref = item.get("spec", {}).get("scaleTargetRef", {})
    if ref.get("kind", "").lower() == "deployment" and ref.get("name") in targets:
        blockers.append(item.get("metadata", {}).get("name", "?"))
if blockers:
    print("TRADEOPS_PARK_FAIL: HPA targets deployments selected for PARK: " + ", ".join(sorted(blockers)), file=sys.stderr)
    raise SystemExit(1)
PY
then
  exit 1
fi

if ! python - "$OUT/cronjobs.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
active = []
for item in data.get("items", []):
    if item.get("spec", {}).get("suspend") is not True:
        active.append(item.get("metadata", {}).get("name", "?"))
if active:
    print("TRADEOPS_PARK_FAIL: active CronJob(s) could create new pods while parked: " + ", ".join(sorted(active)), file=sys.stderr)
    raise SystemExit(1)
PY
then
  exit 1
fi

{
  echo "namespace=$NAMESPACE"
  echo "mode=$MODE"
  echo "timestamp=$STAMP"
  if command -v git >/dev/null 2>&1; then
    echo "git_head=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
  fi
} > "$OUT/metadata.env"

positive_targets="$(
  awk -F '\t' '$2 ~ /^[0-9]+$/ && $2 > 0 {count++} END {print count+0}' "$OUT/park-targets.tsv"
)"
if [[ "$positive_targets" -eq 0 ]]; then
  echo "TRADEOPS_PARK_FAIL: no running deployment is eligible for PARK" >&2
  exit 1
fi

MUTATION_STARTED=1
while IFS=$'\t' read -r name replicas; do
  [[ -n "$name" ]] || continue
  if [[ "$replicas" =~ ^[0-9]+$ ]] && (( replicas > 0 )); then
    echo "PARK deployment/$name: $replicas -> 0"
    oc -n "$NAMESPACE" scale "deployment/$name" --replicas=0
  fi
done < "$OUT/park-targets.tsv"

while IFS=$'\t' read -r name replicas; do
  [[ -n "$name" ]] || continue
  current="$(oc -n "$NAMESPACE" get "deployment/$name" -o jsonpath='{.spec.replicas}')"
  if [[ "$current" != "0" ]]; then
    echo "TRADEOPS_PARK_FAIL: deployment/$name desired replicas is $current, expected 0" >&2
    false
  fi
done < "$OUT/park-targets.tsv"

while IFS=$'\t' read -r name replicas; do
  [[ -n "$name" ]] || continue
  current="$(oc -n "$NAMESPACE" get "statefulset/$name" -o jsonpath='{.spec.replicas}')"
  if [[ "$current" != "$replicas" ]]; then
    echo "TRADEOPS_PARK_FAIL: statefulset/$name changed from $replicas to $current" >&2
    false
  fi
done < "$OUT/statefulsets.tsv"

if [[ "$MODE" == "normal" ]] && grep -q '^prometheus[[:space:]]' "$OUT/deployments.tsv"; then
  before="$(awk -F '\t' '$1=="prometheus" {print $2}' "$OUT/deployments.tsv")"
  current="$(oc -n "$NAMESPACE" get deployment/prometheus -o jsonpath='{.spec.replicas}')"
  if [[ "$current" != "$before" ]]; then
    echo "TRADEOPS_PARK_FAIL: Prometheus changed in normal mode ($before -> $current)" >&2
    false
  fi
fi

capture_best_effort 20-pods-after.txt oc -n "$NAMESPACE" get pods -o wide
capture_best_effort 21-workloads-after.txt oc -n "$NAMESPACE" get deployment,statefulset -o wide
capture_best_effort 22-top-after.txt oc adm top pods -n "$NAMESPACE"
capture_best_effort 23-node-describe-after.txt oc describe node
capture_best_effort 24-cluster-pending-after.txt oc get pods -A --field-selector=status.phase=Pending -o wide
capture_best_effort 25-cluster-pods-after.json oc get pods -A -o json
capture_best_effort 26-nodes-after.json oc get nodes -o json

printf '%s\n' "PARKED" > "$OUT/status"
printf '%s\n' "$OUT" > "$LATEST_FILE"

trap - ERR INT TERM
MUTATION_STARTED=0

echo "TRADEOPS_PARK=PASS"
echo "TRADEOPS_PARK_MODE=$MODE"
echo "TRADEOPS_PARK_SNAPSHOT=$OUT"
echo "TRADEOPS_STATEFULSETS_PRESERVED=PASS"
if [[ "$MODE" == "normal" ]]; then
  echo "TRADEOPS_PROMETHEUS_PRESERVED=PASS"
fi
