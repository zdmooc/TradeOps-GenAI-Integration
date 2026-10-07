#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="${TRADEOPS_NAMESPACE:-tradeops}"
STATE_ROOT="${TRADEOPS_PARK_STATE_ROOT:-$ROOT/.runtime/tradeops-park}"
LATEST_FILE="$STATE_ROOT/LATEST"
SNAPSHOT="${TRADEOPS_PARK_SNAPSHOT:-}"

for cmd in oc python; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "TRADEOPS_RESUME_FAIL: missing required command: $cmd" >&2
    exit 2
  fi
done

oc whoami >/dev/null
oc get namespace "$NAMESPACE" >/dev/null

if [[ -z "$SNAPSHOT" ]]; then
  if [[ ! -f "$LATEST_FILE" ]]; then
    echo "TRADEOPS_RESUME_FAIL: no PARK snapshot pointer found at $LATEST_FILE" >&2
    exit 2
  fi
  SNAPSHOT="$(cat "$LATEST_FILE")"
fi

if [[ ! -d "$SNAPSHOT" || ! -f "$SNAPSHOT/deployments.tsv" || ! -f "$SNAPSHOT/statefulsets.tsv" ]]; then
  echo "TRADEOPS_RESUME_FAIL: invalid PARK snapshot: $SNAPSHOT" >&2
  exit 2
fi

if [[ -f "$SNAPSHOT/status" ]] && grep -qx "RESUMED" "$SNAPSHOT/status"; then
  echo "TRADEOPS_RESUME_ALREADY_COMPLETE=PASS"
  echo "TRADEOPS_PARK_SNAPSHOT=$SNAPSHOT"
  exit 0
fi

snapshot_namespace="$(awk -F= '$1=="namespace" {print substr($0,index($0,"=")+1)}' "$SNAPSHOT/metadata.env" 2>/dev/null || true)"
if [[ -n "$snapshot_namespace" && "$snapshot_namespace" != "$NAMESPACE" ]]; then
  echo "TRADEOPS_RESUME_FAIL: snapshot namespace is $snapshot_namespace, requested namespace is $NAMESPACE" >&2
  exit 2
fi

CURRENT_DEPLOYMENTS="$SNAPSHOT/resume-current-deployments.json"
CURRENT_HPA="$SNAPSHOT/resume-current-hpa.json"
oc -n "$NAMESPACE" get deployments.apps -o json > "$CURRENT_DEPLOYMENTS"
oc -n "$NAMESPACE" get hpa.autoscaling -o json > "$CURRENT_HPA"

if ! python - "$CURRENT_DEPLOYMENTS" "$SNAPSHOT/deployments.tsv" <<'PY'
import json
import sys

current_path, snapshot_path = sys.argv[1:3]
current = {
    item["metadata"]["name"]
    for item in json.load(open(current_path, encoding="utf-8")).get("items", [])
}
expected = {
    line.split("\t", 1)[0]
    for line in open(snapshot_path, encoding="utf-8")
    if line.strip()
}
if current != expected:
    missing = sorted(expected - current)
    extra = sorted(current - expected)
    if missing:
        print("TRADEOPS_RESUME_FAIL: deployment(s) missing since PARK: " + ", ".join(missing), file=sys.stderr)
    if extra:
        print("TRADEOPS_RESUME_FAIL: new deployment(s) appeared since PARK: " + ", ".join(extra), file=sys.stderr)
    raise SystemExit(1)
PY
then
  exit 1
fi

if ! python - "$CURRENT_HPA" "$SNAPSHOT/deployments.tsv" <<'PY'
import json
import sys

hpa_path, snapshot_path = sys.argv[1:3]
targets = {
    line.split("\t", 1)[0]
    for line in open(snapshot_path, encoding="utf-8")
    if line.strip()
}
data = json.load(open(hpa_path, encoding="utf-8"))
blockers = []
for item in data.get("items", []):
    ref = item.get("spec", {}).get("scaleTargetRef", {})
    if ref.get("kind", "").lower() == "deployment" and ref.get("name") in targets:
        blockers.append(item.get("metadata", {}).get("name", "?"))
if blockers:
    print("TRADEOPS_RESUME_FAIL: HPA now controls deployment(s) from the PARK snapshot: " + ", ".join(sorted(blockers)), file=sys.stderr)
    raise SystemExit(1)
PY
then
  exit 1
fi

while IFS=$'\t' read -r name replicas; do
  [[ -n "$name" ]] || continue
  current="$(oc -n "$NAMESPACE" get "statefulset/$name" -o jsonpath='{.spec.replicas}' 2>/dev/null || true)"
  if [[ -z "$current" ]]; then
    echo "TRADEOPS_RESUME_FAIL: statefulset/$name disappeared since PARK" >&2
    exit 1
  fi
  if [[ "$current" != "$replicas" ]]; then
    echo "TRADEOPS_RESUME_FAIL: statefulset/$name drifted from $replicas to $current; refusing to mutate deployments" >&2
    exit 1
  fi
done < "$SNAPSHOT/statefulsets.tsv"

python - "$CURRENT_DEPLOYMENTS" "$SNAPSHOT/resume-before.tsv" <<'PY'
import json
import sys

src, dst = sys.argv[1:3]
items = sorted(json.load(open(src, encoding="utf-8")).get("items", []), key=lambda item: item["metadata"]["name"])
with open(dst, "w", encoding="utf-8", newline="") as handle:
    for item in items:
        handle.write(f"{item['metadata']['name']}\t{item.get('spec', {}).get('replicas', 1)}\n")
PY

MUTATION_STARTED=0

rollback_on_error() {
  rc=$?
  trap - ERR INT TERM
  if [[ "$MUTATION_STARTED" == "1" && -f "$SNAPSHOT/resume-before.tsv" ]]; then
    echo "TRADEOPS_RESUME_ROLLBACK: restoring pre-resume deployment replicas" >&2
    while IFS=$'\t' read -r name replicas; do
      [[ -n "$name" ]] || continue
      oc -n "$NAMESPACE" scale "deployment/$name" --replicas="$replicas" >/dev/null 2>&1 || true
    done < "$SNAPSHOT/resume-before.tsv"
  fi
  echo "TRADEOPS_RESUME_FAIL: stateful workloads were not intentionally scaled" >&2
  exit "$rc"
}
trap rollback_on_error ERR INT TERM

{
  oc -n "$NAMESPACE" get pods -o wide
  oc -n "$NAMESPACE" get deployment,statefulset -o wide
} > "$SNAPSHOT/30-before-resume.txt" 2>&1 || true

MUTATION_STARTED=1
while IFS=$'\t' read -r name replicas; do
  [[ -n "$name" ]] || continue
  echo "RESUME deployment/$name -> $replicas"
  oc -n "$NAMESPACE" scale "deployment/$name" --replicas="$replicas"
done < "$SNAPSHOT/deployments.tsv"

while IFS=$'\t' read -r name replicas; do
  [[ -n "$name" ]] || continue
  current="$(oc -n "$NAMESPACE" get "deployment/$name" -o jsonpath='{.spec.replicas}')"
  if [[ "$current" != "$replicas" ]]; then
    echo "TRADEOPS_RESUME_FAIL: deployment/$name desired replicas is $current, expected $replicas" >&2
    false
  fi
  if [[ "$replicas" =~ ^[0-9]+$ ]] && (( replicas > 0 )); then
    oc -n "$NAMESPACE" rollout status "deployment/$name" --timeout="${TRADEOPS_RESUME_TIMEOUT:-300s}"
  fi
done < "$SNAPSHOT/deployments.tsv"

while IFS=$'\t' read -r name replicas; do
  [[ -n "$name" ]] || continue
  current="$(oc -n "$NAMESPACE" get "statefulset/$name" -o jsonpath='{.spec.replicas}')"
  if [[ "$current" != "$replicas" ]]; then
    echo "TRADEOPS_RESUME_FAIL: statefulset/$name changed from $replicas to $current" >&2
    false
  fi
done < "$SNAPSHOT/statefulsets.tsv"

{
  oc -n "$NAMESPACE" get pods -o wide
  oc -n "$NAMESPACE" get deployment,statefulset -o wide
} > "$SNAPSHOT/31-after-resume.txt" 2>&1 || true
oc adm top pods -n "$NAMESPACE" > "$SNAPSHOT/32-top-after-resume.txt" 2>&1 || true

if [[ "${TRADEOPS_RESUME_FULL_VERIFY:-no}" == "yes" ]]; then
  bash "$ROOT/scripts/i9_crc_verify.sh" | tee "$SNAPSHOT/33-full-verify.txt"
fi

printf '%s\n' "RESUMED" > "$SNAPSHOT/status"

trap - ERR INT TERM
MUTATION_STARTED=0

echo "TRADEOPS_RESUME=PASS"
echo "TRADEOPS_RESUME_SNAPSHOT=$SNAPSHOT"
echo "TRADEOPS_REPLICA_RESTORE=EXACT"
echo "TRADEOPS_STATEFULSETS_PRESERVED=PASS"
