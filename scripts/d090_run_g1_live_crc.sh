#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="evidence/out/d090-${STAMP}"
mkdir -p "${OUT}"

TRACE_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

PROFILE="$(oc -n tradeops get configmap d090-ai-model -o jsonpath='{.data.profile}' 2>/dev/null || true)"
MODEL_CFG="$(oc -n tradeops get configmap d090-ai-model -o jsonpath='{.data.model}' 2>/dev/null || true)"
API_BASE_CFG="$(oc -n tradeops get configmap d090-ai-model -o jsonpath='{.data.api_base}' 2>/dev/null || true)"

if [[ "${PROFILE}" == "local-ollama" ]]; then
  [[ "${MODEL_CFG}" == ollama/* ]]
  [[ "${API_BASE_CFG}" == http://*:11434 ]]
  echo "D090_LOCAL_REAL_MODEL_PROFILE=PASS model=${MODEL_CFG} api_base=${API_BASE_CFG}" | tee -a "${OUT}/05-summary.txt"
fi

oc -n tradeops wait --for=condition=Available deploy/genai-api --timeout=120s >/dev/null
oc -n tradeops wait --for=condition=Available deploy/ai-access-policy --timeout=120s >/dev/null
oc -n tradeops wait --for=condition=Available deploy/litellm --timeout=120s >/dev/null
oc -n mayabank-api wait --for=condition=Available deploy/api-gateway --timeout=120s >/dev/null

MSYS_NO_PATHCONV=1 oc -n tradeops exec -i deploy/genai-api -- \
  python - \
  --timeout "${D090_G1_PROBE_TIMEOUT:-120}" \
  --evidence-out /tmp/d090-real-model.json \
  < scripts/d090_real_model_probe.py | tee "${OUT}/01-real-model-probe.txt"

MSYS_NO_PATHCONV=1 oc -n tradeops exec deploy/genai-api -- \
  cat /tmp/d090-real-model.json > "${OUT}/02-real-model.json"

oc -n tradeops exec -i deploy/ai-access-policy -- python - <<'PY'   > "${OUT}/03-ai-access-metrics.txt"
import urllib.request
print(urllib.request.urlopen("http://127.0.0.1:8020/metrics", timeout=10).read().decode())
PY

sleep 5
oc -n shared-observability logs deploy/otel-collector --since-time="${TRACE_START}"   > "${OUT}/04-shared-otel.log" 2>&1 || true

if grep -Eq 'llm.complete|genai-api' "${OUT}/04-shared-otel.log"; then
  echo "D090_SHARED_OTEL_TRACE=PASS" | tee -a "${OUT}/05-summary.txt"
else
  echo "D090_SHARED_OTEL_TRACE=PENDING_NOT_OBSERVED" | tee -a "${OUT}/05-summary.txt"
fi

grep -q 'D090_REAL_MODEL_PATH=PASS' "${OUT}/01-real-model-probe.txt"
grep -q 'mayabank_ai_access_requests_total' "${OUT}/03-ai-access-metrics.txt"

if [[ "${PROFILE}" == "local-ollama" ]]; then
  echo "D090_G1_CLAIM=LOCAL_REAL_MODEL_PROVEN" | tee -a "${OUT}/05-summary.txt"
fi
echo "D090_G1_LIVE=PASS" | tee -a "${OUT}/05-summary.txt"
echo "D090_EVIDENCE_DIR=${OUT}"
