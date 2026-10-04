#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODEL="${D090_LITELLM_MODEL:-}"
PROVIDER_KEY="${D090_PROVIDER_API_KEY:-}"

: "${MODEL:?export D090_LITELLM_MODEL, for example an exact LiteLLM provider/model identifier}"
: "${PROVIDER_KEY:?export D090_PROVIDER_API_KEY in the current shell; it is never written to Git}"

oc -n tradeops get secret tradeops-runtime-secrets >/dev/null
oc -n tradeops create configmap d090-ai-model   --from-literal=model="${MODEL}"   --dry-run=client -o yaml | oc apply -f - >/dev/null

PROVIDER_KEY="${PROVIDER_KEY}" PATCH="$(PROVIDER_KEY="${PROVIDER_KEY}" python - <<'PY'
import base64, json, os
value=base64.b64encode(os.environ["PROVIDER_KEY"].encode()).decode()
print(json.dumps({"data":{"LITELLM_PROVIDER_API_KEY":value}},separators=(",",":")))
PY
)"
oc -n tradeops patch secret tradeops-runtime-secrets --type=merge -p "${PATCH}" >/dev/null

unset PROVIDER_KEY PATCH

oc apply -f infra/ai-access/litellm-deployment-crc.yaml >/dev/null
oc -n tradeops rollout status deploy/litellm --timeout=300s

oc -n tradeops exec deploy/ai-access-policy -- python - <<'PY'
import urllib.request
with urllib.request.urlopen("http://litellm:4000/health/readiness", timeout=10) as r:
    assert r.status == 200
print("D090_LITELLM_READINESS=PASS")
PY

echo "D090_LITELLM_DEPLOY=PASS model=${MODEL}"
