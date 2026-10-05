#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODEL="${D090_LITELLM_MODEL:-openai/gpt-5.6-terra}"
PROVIDER_KEY="${D090_PROVIDER_API_KEY:-${OPENAI_API_KEY:-}}"

: "${PROVIDER_KEY:?export OPENAI_API_KEY or D090_PROVIDER_API_KEY in the current shell; it is never written to Git}"

case "${PROVIDER_KEY}" in
  *TA_CLE*|*PLACEHOLDER*|*CHANGEME*|*YOUR_KEY*|*your-key*|*"<"*|*">"*)
    echo "D090_PROVIDER_KEY_PRECHECK=FAIL placeholder_detected" >&2
    exit 2
    ;;
esac
echo "D090_PROVIDER_KEY_PRECHECK=PASS"

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

if ! oc -n tradeops rollout status deploy/litellm --timeout=1200s; then
  echo "D090_LITELLM_ROLLOUT=FAIL" >&2
  echo "===== LITELLM SNAPSHOT =====" >&2
  oc -n tradeops get deploy,rs,pods -l app.kubernetes.io/name=litellm -o wide >&2 || true
  oc -n tradeops describe deploy/litellm >&2 || true
  oc -n tradeops describe pods -l app.kubernetes.io/name=litellm >&2 || true
  oc -n tradeops logs -l app.kubernetes.io/name=litellm --tail=250 --prefix >&2 || true
  oc -n tradeops logs -l app.kubernetes.io/name=litellm --previous --tail=250 --prefix >&2 || true
  oc -n tradeops get events --sort-by=.lastTimestamp | tail -n 120 >&2 || true
  exit 1
fi
echo "D090_LITELLM_ROLLOUT=PASS"

oc -n tradeops exec deploy/ai-access-policy -- python - <<'PY'
import urllib.request
with urllib.request.urlopen("http://litellm:4000/health/readiness", timeout=10) as r:
    assert r.status == 200
print("D090_LITELLM_READINESS=PASS")
PY

echo "D090_LITELLM_DEPLOY=PASS model=${MODEL}"
