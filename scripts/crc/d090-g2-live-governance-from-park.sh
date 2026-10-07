#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

NAMESPACE="${TRADEOPS_NAMESPACE:-tradeops}"
STATE_ROOT="${TRADEOPS_PARK_STATE_ROOT:-$ROOT/.runtime/tradeops-park}"
SNAPSHOT="${TRADEOPS_PARK_SNAPSHOT:-}"
API_BASE="${D090_LITELLM_API_BASE:-}"
API_REPO="${D090_API_MANAGEMENT_REPO:-$(cd "$ROOT/.." && pwd)/mayabank-api-management-architecture}"
PROFILE="${D090_LITELLM_PROFILE:-local-ollama}"
MODEL="${D090_LITELLM_MODEL:-ollama/qwen2.5:3b}"
REQUIRED_DEPLOYMENTS=(ai-access-policy genai-api litellm)
ACTIVATION_DEPLOYMENTS=(ai-access-policy genai-api)
WINDOW_FILE=""
ORIGINAL_POLICY_B64=""
RUNTIME_ISSUER=""
OUT=""

for cmd in oc python awk grep curl; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "D090_G2_FAIL: missing required command: $cmd" >&2
    exit 2
  }
done

: "${API_BASE:?export D090_LITELLM_API_BASE explicitly, e.g. http://192.168.56.1:11434}"

if [[ "$PROFILE" != "local-ollama" || "$MODEL" != ollama/* ]]; then
  echo "D090_G2_FAIL: bounded CRC G2 currently requires local-ollama / ollama/*" >&2
  exit 2
fi

if [[ -z "$SNAPSHOT" ]]; then
  [[ -f "$STATE_ROOT/LATEST" ]] || {
    echo "D090_G2_FAIL: no PARK snapshot found" >&2
    exit 2
  }
  SNAPSHOT="$(cat "$STATE_ROOT/LATEST")"
fi

if [[ ! -f "$SNAPSHOT/status" ]] || ! grep -qx "PARKED" "$SNAPSHOT/status"; then
  echo "D090_G2_FAIL: TradeOps must still be PARKED" >&2
  exit 2
fi

if [[ ! -f "$API_REPO/runtime/shared-platform/scripts/enable-d090-ai-access-crc.sh" ]]; then
  echo "D090_G2_FAIL: API Management owner checkout not found: $API_REPO" >&2
  exit 2
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$SNAPSHOT/g2-$STAMP"
mkdir -p "$OUT"
WINDOW_FILE="$OUT/g2-window.tsv"
: > "$WINDOW_FILE"

for name in "${REQUIRED_DEPLOYMENTS[@]}"; do
  line="$(awk -F '\t' -v n="$name" '$1==n {print $0}' "$SNAPSHOT/deployments.tsv")"
  [[ -n "$line" ]] || {
    echo "D090_G2_FAIL: deployment/$name absent from PARK snapshot" >&2
    exit 1
  }
  replicas="$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')"
  [[ "$replicas" =~ ^[0-9]+$ ]] && (( replicas >= 1 )) || {
    echo "D090_G2_FAIL: invalid snapshot replicas for deployment/$name: $replicas" >&2
    exit 1
  }
  printf '%s\t%s\n' "$name" "$replicas" >> "$WINDOW_FILE"
done

bash scripts/d090_bootstrap_oidc_crc.sh
echo "D090_G2_AUTH_MATERIAL_REFRESH=PASS"

ORIGINAL_POLICY_B64="$(oc -n "$NAMESPACE" get secret tradeops-runtime-secrets -o jsonpath='{.data.AI_ACCESS_CONSUMERS_JSON}')"
[[ -n "$ORIGINAL_POLICY_B64" ]] || {
  echo "D090_G2_FAIL: original AI_ACCESS_CONSUMERS_JSON missing" >&2
  exit 1
}

patch_policy_variant() {
  local variant="$1" policy_json patch
  policy_json="$(ORIGINAL_POLICY_B64="$ORIGINAL_POLICY_B64" VARIANT="$variant" python - <<'PY'
import base64, json, os

raw=base64.b64decode(os.environ["ORIGINAL_POLICY_B64"]).decode()
obj=json.loads(raw)
policy=obj["tradeops-ai"]
variant=os.environ["VARIANT"]
if variant == "quota":
    policy["rpm"]=1
    policy["budget_usd"]=5.0
    policy["input_cost_usd_per_1k"]=0.0
    policy["output_cost_usd_per_1k"]=0.0
elif variant == "budget":
    policy["rpm"]=60
    policy["budget_usd"]=0.000001
    policy["input_cost_usd_per_1k"]=100.0
    policy["output_cost_usd_per_1k"]=100.0
elif variant != "baseline":
    raise SystemExit("unknown policy variant")
print(json.dumps(obj,separators=(",",":")))
PY
)"
  patch="$(POLICY_JSON="$policy_json" python - <<'PY'
import base64, json, os
value=base64.b64encode(os.environ["POLICY_JSON"].encode()).decode()
print(json.dumps({"data":{"AI_ACCESS_CONSUMERS_JSON":value}},separators=(",",":")))
PY
)"
  oc -n "$NAMESPACE" patch secret tradeops-runtime-secrets --type=merge -p "$patch" >/dev/null
  oc -n "$NAMESPACE" rollout restart deploy/ai-access-policy >/dev/null
  oc -n "$NAMESPACE" rollout status deploy/ai-access-policy --timeout=300s >/dev/null
  echo "D090_G2_POLICY_VARIANT=PASS variant=$variant"
}

restore_policy() {
  local patch
  [[ -n "$ORIGINAL_POLICY_B64" ]] || return 0
  patch="$(ORIGINAL_POLICY_B64="$ORIGINAL_POLICY_B64" python - <<'PY'
import json, os
print(json.dumps({"data":{"AI_ACCESS_CONSUMERS_JSON":os.environ["ORIGINAL_POLICY_B64"]}},separators=(",",":")))
PY
)"
  if oc -n "$NAMESPACE" patch secret tradeops-runtime-secrets --type=merge -p "$patch" >/dev/null; then
    current="$(oc -n "$NAMESPACE" get secret tradeops-runtime-secrets -o jsonpath='{.data.AI_ACCESS_CONSUMERS_JSON}' 2>/dev/null || true)"
    if [[ "$current" == "$ORIGINAL_POLICY_B64" ]]; then
      echo "D090_G2_POLICY_RESTORE=PASS"
      return 0
    fi
  fi
  echo "D090_G2_POLICY_RESTORE=FAIL" >&2
  return 1
}

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  local cleanup_fail=0

  restore_policy || cleanup_fail=1

  if [[ -f "$WINDOW_FILE" ]]; then
    while IFS=$'\t' read -r name _replicas; do
      [[ -n "$name" ]] || continue
      oc -n "$NAMESPACE" scale "deployment/$name" --replicas=0 >/dev/null 2>&1 || cleanup_fail=1
    done < "$WINDOW_FILE"
  fi

  if [[ "$cleanup_fail" == "0" ]]; then
    echo "D090_G2_WINDOW_REPARK=PASS"
  fi

  if [[ "$rc" != "0" ]]; then
    exit "$rc"
  fi
  [[ "$cleanup_fail" == "0" ]] || exit 1
}
trap cleanup EXIT INT TERM

oc whoami >/dev/null
oc get namespace "$NAMESPACE" >/dev/null
oc -n mayabank-api wait --for=condition=Available deploy/api-gateway --timeout=120s >/dev/null
oc -n shared-observability wait --for=condition=Available deploy/otel-collector --timeout=120s >/dev/null

for name in "${ACTIVATION_DEPLOYMENTS[@]}"; do
  replicas="$(awk -F '\t' -v n="$name" '$1==n {print $2}' "$WINDOW_FILE")"
  echo "G2 WINDOW deployment/$name: 0 -> $replicas"
  oc -n "$NAMESPACE" scale "deployment/$name" --replicas="$replicas"
done
for name in "${ACTIVATION_DEPLOYMENTS[@]}"; do
  oc -n "$NAMESPACE" rollout status "deployment/$name" --timeout=300s >/dev/null
done
echo "D090_G2_WINDOW_BASE_ACTIVE=PASS"

export D090_LITELLM_PROFILE="$PROFILE"
export D090_LITELLM_MODEL="$MODEL"
export D090_LITELLM_API_BASE="$API_BASE"
bash scripts/d090_deploy_litellm_crc.sh
bash scripts/d090_enable_genai_crc.sh
echo "D090_G2_WINDOW_ACTIVE=PASS"

RUNTIME_ISSUER="$(
  MSYS_NO_PATHCONV=1 oc -n "$NAMESPACE" exec -i deploy/genai-api -- \
    python - < scripts/d090_runtime_issuer_probe.py
)"
[[ -n "$RUNTIME_ISSUER" ]] || {
  echo "D090_G2_FAIL: runtime issuer empty" >&2
  exit 1
}
echo "D090_G2_RUNTIME_TOKEN_ISSUER=$RUNTIME_ISSUER"

oc -n "$NAMESPACE" set env deploy/ai-access-policy OIDC_ISSUER="$RUNTIME_ISSUER" >/dev/null
oc -n "$NAMESPACE" rollout status deploy/ai-access-policy --timeout=300s >/dev/null
(
  cd "$API_REPO"
  KEYCLOAK_ISSUER_OVERRIDE="$RUNTIME_ISSUER" \
    bash runtime/shared-platform/scripts/enable-d090-ai-access-crc.sh
)
echo "D090_G2_AUTH_CHAIN=PASS"

# Apply AI Access plus the shared monitoring intent. G2 no longer mutates
# or restarts the existing product Prometheus pod.
oc apply -f infra/ai-access/ai-access-policy-crc.yaml >/dev/null
oc -n "$NAMESPACE" rollout status deploy/ai-access-policy --timeout=300s >/dev/null
oc -n "$NAMESPACE" set env deploy/ai-access-policy OIDC_ISSUER="$RUNTIME_ISSUER" >/dev/null
oc -n "$NAMESPACE" rollout status deploy/ai-access-policy --timeout=300s >/dev/null

if ! oc get namespace openshift-user-workload-monitoring >/dev/null 2>&1; then
  echo "D090_G2_SHARED_PROMETHEUS=BLOCKED namespace=openshift-user-workload-monitoring_missing" >&2
  exit 1
fi
THANOS_HOST="$(oc -n openshift-monitoring get route thanos-querier -o jsonpath='{.spec.host}' 2>/dev/null || true)"
[[ -n "$THANOS_HOST" ]] || {
  echo "D090_G2_SHARED_PROMETHEUS=BLOCKED route=thanos-querier_missing" >&2
  exit 1
}
oc -n "$NAMESPACE" get servicemonitor ai-access-policy >/dev/null
oc -n "$NAMESPACE" get networkpolicy allow-user-workload-monitoring-to-ai-access-policy >/dev/null
echo "D090_G2_SHARED_PROMETHEUS_INTENT=PASS"


capture_metrics() {
  local out="$1"
  MSYS_NO_PATHCONV=1 oc -n "$NAMESPACE" exec -i deploy/ai-access-policy -- python - <<'PY' > "$out"
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:8020/metrics", timeout=10) as response:
    print(response.read().decode(), end="")
PY
}

run_governance_probe() {
  local mode="$1"
  MSYS_NO_PATHCONV=1 oc -n "$NAMESPACE" exec -i deploy/genai-api -- \
    python - --mode "$mode" < scripts/d090_g2_governance_probe.py
}

# Baseline: live success + model allowlist denial.
patch_policy_variant baseline
run_governance_probe baseline | tee "$OUT/10-baseline-probe.txt"
capture_metrics "$OUT/11-baseline-metrics.txt"
grep -q 'mayabank_ai_access_requests_total{consumer="tradeops",status="ok"}' "$OUT/11-baseline-metrics.txt"
grep -q 'mayabank_ai_access_denials_total{code="MODEL_DENIED"}' "$OUT/11-baseline-metrics.txt"
grep -q 'mayabank_ai_access_tokens_total{consumer="tradeops",direction="input"}' "$OUT/11-baseline-metrics.txt"
echo "D090_G2_BASELINE_METRICS=PASS"

# Exercise the real genai-api path so ObservedLLM emits llm.complete to Shared OTel.
TRACE_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
MSYS_NO_PATHCONV=1 oc -n "$NAMESPACE" exec -i deploy/genai-api -- python - <<'PY' | tee "$OUT/12-genai-review.txt"
import json, urllib.request, uuid
payload={
  "workflow_id": str(uuid.uuid4()),
  "symbol": "D090G2",
  "side": "BUY",
  "qty": 1.0,
  "reason": "D-090 G2 live governance and telemetry evidence",
}
request=urllib.request.Request(
  "http://127.0.0.1:8013/review",
  data=json.dumps(payload).encode(),
  headers={"Content-Type":"application/json"},
  method="POST",
)
with urllib.request.urlopen(request, timeout=180) as response:
    body=json.loads(response.read().decode())
assert body.get("review"), body
print("D090_G2_GENAI_REVIEW=PASS")
PY

sleep 8
oc -n shared-observability logs deploy/otel-collector --since-time="$TRACE_START" \
  > "$OUT/13-shared-otel.log" 2>&1 || true
if grep -Eqi 'Traces|ResourceSpans|resource spans' "$OUT/13-shared-otel.log"; then
  echo "D090_G2_SHARED_OTEL_TRACE=PASS"
else
  echo "D090_G2_SHARED_OTEL_TRACE=FAIL" >&2
  exit 1
fi

# Shared OpenShift user-workload monitoring must scrape and query AI Access.
PROM_TIMEOUT="${D090_G2_SHARED_PROM_TIMEOUT_SECONDS:-180}"
[[ "$PROM_TIMEOUT" =~ ^[0-9]+$ ]] && (( PROM_TIMEOUT >= 30 )) || {
  echo "D090_G2_FAIL: D090_G2_SHARED_PROM_TIMEOUT_SECONDS must be an integer >= 30" >&2
  exit 2
}
THANOS_TOKEN="$(oc whoami -t)"
query_thanos() {
  local expr="$1"
  curl -ksS --fail \
    -H "Authorization: Bearer $THANOS_TOKEN" \
    -G "https://$THANOS_HOST/api/v1/query" \
    --data-urlencode "query=$expr"
}

UP_EXPR="up{namespace=\"$NAMESPACE\"}"
METRIC_EXPR='mayabank_ai_access_requests_total{consumer="tradeops",status="ok"}'
PROM_DEADLINE=$((SECONDS + PROM_TIMEOUT))
UP_BODY=""
METRIC_BODY=""

shared_prometheus_ok() {
  UP_BODY="$UP_BODY" METRIC_BODY="$METRIC_BODY" NAMESPACE="$NAMESPACE" python - <<'PY'
import json, os, sys

def rows(name):
    try:
        body=json.loads(os.environ.get(name,""))
    except Exception:
        return []
    if body.get("status") != "success":
        return []
    return body.get("data",{}).get("result",[])

up_ok=False
for row in rows("UP_BODY"):
    metric=row.get("metric",{})
    service=metric.get("service","")
    job=metric.get("job","")
    if metric.get("namespace")==os.environ["NAMESPACE"] and (
        service=="ai-access-policy" or "ai-access-policy" in job
    ):
        try:
            if float(row.get("value",["0","0"])[1]) == 1.0:
                up_ok=True
        except Exception:
            pass

metric_ok=False
for row in rows("METRIC_BODY"):
    metric=row.get("metric",{})
    if metric.get("consumer")!="tradeops" or metric.get("status")!="ok":
        continue
    namespace=metric.get("namespace")
    service=metric.get("service","")
    if namespace not in (None, "", os.environ["NAMESPACE"]):
        continue
    if namespace in (None, "") and service not in ("", "ai-access-policy"):
        continue
    try:
        if float(row.get("value",["0","0"])[1]) > 0:
            metric_ok=True
    except Exception:
        pass

sys.exit(0 if up_ok and metric_ok else 1)
PY
}

while (( SECONDS < PROM_DEADLINE )); do
  UP_BODY="$(query_thanos "$UP_EXPR" || true)"
  METRIC_BODY="$(query_thanos "$METRIC_EXPR" || true)"
  if shared_prometheus_ok; then
    break
  fi
  sleep 5
done

printf '%s\n' "$UP_BODY" > "$OUT/14-shared-prometheus-up.json"
printf '%s\n' "$METRIC_BODY" > "$OUT/15-shared-prometheus-metric.json"

if ! shared_prometheus_ok; then
  echo "D090_G2_SHARED_PROMETHEUS=FAIL" >&2
  unset THANOS_TOKEN
  exit 1
fi
unset THANOS_TOKEN
echo "D090_G2_PROMETHEUS_TARGET=PASS source=openshift-user-workload-monitoring"
echo "D090_G2_PROMETHEUS_QUERY=PASS source=thanos"
echo "D090_G2_SHARED_PROMETHEUS=PASS"

# Quota denial: first request allowed, second denied within the same 60-second window.
patch_policy_variant quota
run_governance_probe quota | tee "$OUT/20-quota-probe.txt"
capture_metrics "$OUT/21-quota-metrics.txt"
grep -q 'mayabank_ai_access_denials_total{code="QUOTA_EXCEEDED"}' "$OUT/21-quota-metrics.txt"
echo "D090_G2_QUOTA_METRICS=PASS"

# Budget denial: first real request records non-zero spend, second is denied.
patch_policy_variant budget
run_governance_probe budget | tee "$OUT/30-budget-probe.txt"
capture_metrics "$OUT/31-budget-metrics.txt"
grep -q 'mayabank_ai_access_denials_total{code="BUDGET_EXCEEDED"}' "$OUT/31-budget-metrics.txt"
python - "$OUT/31-budget-metrics.txt" <<'PY'
import re, sys
text=open(sys.argv[1],encoding="utf-8").read()
match=re.search(r'mayabank_ai_access_cost_usd_total\{consumer="tradeops"\}\s+([0-9.eE+-]+)', text)
if not match or float(match.group(1)) <= 0:
    raise SystemExit("D090_G2_COST_METRIC=FAIL")
print("D090_G2_COST_METRIC=PASS")
PY

restore_policy
ORIGINAL_POLICY_B64=""
echo "D090_G2_GOVERNANCE=PASS"
echo "D090_G2_EVIDENCE=$OUT"
