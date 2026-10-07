#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SHARED_REPO="${SHARED_PLATFORM_REPO:-$(cd "$ROOT/.." && pwd)/shared-platform-services-openshift}"
ODM_NS="${ODM_NAMESPACE:-mayainsurance-decision-local}"
TRADEOPS_NS="${TRADEOPS_NAMESPACE:-tradeops}"
API_NS="${API_NAMESPACE:-mayabank-api}"
KEYCLOAK_NS="${KEYCLOAK_NAMESPACE:-keycloak-system}"
GW_LOCAL_PORT="${D090_GATEWAY_LOCAL_PORT:-18000}"
KC_LOCAL_PORT="${D090_KEYCLOAK_LOCAL_PORT:-18080}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${D090_SHARED_EVIDENCE_OUT:-evidence/out/d090-shared-${STAMP}.json}"
GW_LOG="$(mktemp)"
KC_LOG="$(mktemp)"
GW_PID=""
KC_PID=""

for cmd in oc python curl; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "D090_SHARED_PRECHECK=FAIL missing=$cmd" >&2; exit 2; }
done

if [[ ! -f "$SHARED_REPO/scripts/d090_bootstrap_ai_consumers_crc.py" ]]; then
  echo "D090_SHARED_PRECHECK=FAIL shared_platform_repo=$SHARED_REPO" >&2
  exit 2
fi

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  [[ -n "$GW_PID" ]] && kill "$GW_PID" >/dev/null 2>&1 || true
  [[ -n "$KC_PID" ]] && kill "$KC_PID" >/dev/null 2>&1 || true
  wait "$GW_PID" >/dev/null 2>&1 || true
  wait "$KC_PID" >/dev/null 2>&1 || true
  rm -f "$GW_LOG" "$KC_LOG"
  unset AI_OIDC_CLIENT_SECRET ODM_AI_CLIENT_SECRET
  exit "$rc"
}
trap cleanup EXIT INT TERM

echo "=== D-090 G3/G4 shared gateway isolation ==="

oc -n "$API_NS" wait --for=condition=Available deploy/api-gateway --timeout=120s >/dev/null
oc -n "$TRADEOPS_NS" wait --for=condition=Available deploy/ai-access-policy --timeout=120s >/dev/null
oc -n "$TRADEOPS_NS" wait --for=condition=Available deploy/litellm --timeout=120s >/dev/null
oc -n "$KEYCLOAK_NS" wait --for=condition=Ready keycloak/keycloak --timeout=120s >/dev/null

SYNC_TARGET_SECRETS=true TRADEOPS_NAMESPACE="$TRADEOPS_NS" ODM_NAMESPACE="$ODM_NS" python "$SHARED_REPO/scripts/d090_bootstrap_ai_consumers_crc.py"

TRADEOPS_NAMESPACE="$TRADEOPS_NS" ODM_NAMESPACE="$ODM_NS" python "$SHARED_REPO/scripts/d090_test_ai_identities_crc.py"

TRADEOPS_SECRET_B64="$(oc -n "$TRADEOPS_NS" get secret tradeops-ai-client-secret -o jsonpath='{.data.client-secret}')"
POLICIES_JSON="$(cat infra/ai-access/consumers.example.json)"
PATCH="$(TRADEOPS_SECRET_B64="$TRADEOPS_SECRET_B64" POLICIES_JSON="$POLICIES_JSON" python - <<'PY'
import base64, json, os
payload={
  "data":{
    "AI_OIDC_CLIENT_SECRET": os.environ["TRADEOPS_SECRET_B64"],
    "AI_ACCESS_CONSUMERS_JSON": base64.b64encode(os.environ["POLICIES_JSON"].encode()).decode(),
  }
}
print(json.dumps(payload,separators=(",",":")))
PY
)"
oc -n "$TRADEOPS_NS" patch secret tradeops-runtime-secrets --type=merge -p "$PATCH" >/dev/null
unset TRADEOPS_SECRET_B64 POLICIES_JSON PATCH

oc -n "$TRADEOPS_NS" rollout restart deploy/ai-access-policy >/dev/null
oc -n "$TRADEOPS_NS" rollout status deploy/ai-access-policy --timeout=300s >/dev/null
echo "D090_SHARED_POLICY_TWO_CONSUMERS=PASS"

oc -n "$API_NS" port-forward svc/api-gateway "${GW_LOCAL_PORT}:8000" >"$GW_LOG" 2>&1 &
GW_PID="$!"
oc -n "$KEYCLOAK_NS" port-forward svc/keycloak-service "${KC_LOCAL_PORT}:8080" >"$KC_LOG" 2>&1 &
KC_PID="$!"

ready=false
for _ in $(seq 1 40); do
  kc_ok=false
  gw_ok=false
  curl -fsS "http://127.0.0.1:${KC_LOCAL_PORT}/realms/mayabank/.well-known/openid-configuration" >/dev/null 2>&1 && kc_ok=true
  code="$(curl -sS -o /dev/null -w '%{http_code}'     -X POST "http://127.0.0.1:${GW_LOCAL_PORT}/ai/v1/chat/completions"     -H 'Content-Type: application/json'     --data '{"model":"tradeops-default","messages":[]}' 2>/dev/null || true)"
  [[ "$code" == "401" ]] && gw_ok=true
  if [[ "$kc_ok" == "true" && "$gw_ok" == "true" ]]; then
    ready=true
    break
  fi
  sleep 1
done

if [[ "$ready" != "true" ]]; then
  echo "D090_SHARED_PORT_FORWARD=FAIL" >&2
  cat "$GW_LOG" >&2 || true
  cat "$KC_LOG" >&2 || true
  exit 3
fi
echo "D090_SHARED_PORT_FORWARD=PASS"

export AI_GATEWAY_BASE_URL="http://127.0.0.1:${GW_LOCAL_PORT}/ai"
export AI_OIDC_TOKEN_URL="http://127.0.0.1:${KC_LOCAL_PORT}/realms/mayabank/protocol/openid-connect/token"
export AI_OIDC_CLIENT_ID="tradeops-ai"
export ODM_AI_CLIENT_ID="odm-ai"
export AI_OIDC_SCOPE="ai.inference"

export AI_OIDC_CLIENT_SECRET="$(oc -n "$TRADEOPS_NS" get secret tradeops-ai-client-secret -o jsonpath='{.data.client-secret}' | base64 -d)"
export ODM_AI_CLIENT_SECRET="$(oc -n "$ODM_NS" get secret odm-ai-client-secret -o jsonpath='{.data.client-secret}' | base64 -d)"

mkdir -p "$(dirname "$OUT")"
python scripts/d090_shared_isolation_probe.py   --timeout 120   --evidence-out "$OUT"

echo "D090_G3_SHARED_GATEWAY=PASS"
echo "D090_G4_CROSS_CONSUMER_ISOLATION=PASS"
echo "D090_SHARED_RUNTIME_RESULT=PASS"
echo "D090_SHARED_EVIDENCE=$OUT"
