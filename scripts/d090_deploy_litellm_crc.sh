#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PROFILE="${D090_LITELLM_PROFILE:-}"
MODEL="${D090_LITELLM_MODEL:-}"
API_BASE="${D090_LITELLM_API_BASE:-}"
PROVIDER_KEY="${D090_PROVIDER_API_KEY:-${OPENAI_API_KEY:-}}"

if [[ -z "${PROFILE}" ]]; then
  if [[ "${MODEL}" == ollama/* || "${API_BASE}" == *":11434"* ]]; then
    PROFILE="local-ollama"
  else
    PROFILE="hosted"
  fi
fi

case "${PROFILE}" in
  local-ollama)
    MODEL="${MODEL:-ollama/qwen2.5:3b}"
    : "${API_BASE:?export D090_LITELLM_API_BASE explicitly for local-ollama; do not rely on host.crc.testing on CRC Windows}"
    if [[ "${MODEL}" != ollama/* ]]; then
      echo "D090_LOCAL_OLLAMA_PRECHECK=FAIL model_must_start_with_ollama/" >&2
      exit 2
    fi
    ;;
  hosted)
    MODEL="${MODEL:-openai/gpt-6-luna}"
    : "${PROVIDER_KEY:?export OPENAI_API_KEY or D090_PROVIDER_API_KEY in the current shell; it is never written to Git}"
    case "${PROVIDER_KEY}" in
      *TA_CLE*|*PLACEHOLDER*|*CHANGEME*|*YOUR_KEY*|*your-key*|*"<"*|*">"*)
        echo "D090_PROVIDER_KEY_PRECHECK=FAIL placeholder_detected" >&2
        exit 2
        ;;
    esac
    echo "D090_PROVIDER_KEY_PRECHECK=PASS"
    oc -n tradeops delete networkpolicy allow-litellm-to-local-ollama --ignore-not-found >/dev/null
    echo "D090_LOCAL_OLLAMA_POLICY_CLEANUP=PASS"
    ;;
  *)
    echo "D090_LITELLM_PROFILE=FAIL supported=hosted,local-ollama observed=${PROFILE}" >&2
    exit 2
    ;;
esac

oc -n tradeops get secret tradeops-runtime-secrets >/dev/null
oc -n tradeops wait --for=condition=Available deploy/ai-access-policy --timeout=120s >/dev/null

CONFIG_FILE="$(mktemp)"
MODEL_CM_ARGS=(--from-literal="model=${MODEL}" --from-literal="profile=${PROFILE}")
if [[ -n "${API_BASE}" ]]; then
  MODEL_CM_ARGS+=(--from-literal="api_base=${API_BASE}")
fi
oc -n tradeops create configmap d090-ai-model "${MODEL_CM_ARGS[@]}"   --dry-run=client -o yaml | oc apply -f - >/dev/null

if [[ "${PROFILE}" == "hosted" ]]; then
  PROVIDER_KEY="${PROVIDER_KEY}" PATCH="$(PROVIDER_KEY="${PROVIDER_KEY}" python - <<'PY'
import base64, json, os
value=base64.b64encode(os.environ["PROVIDER_KEY"].encode()).decode()
print(json.dumps({"data":{"LITELLM_PROVIDER_API_KEY":value}},separators=(",",":")))
PY
)"
  oc -n tradeops patch secret tradeops-runtime-secrets --type=merge -p "${PATCH}" >/dev/null
  unset PROVIDER_KEY PATCH
else
  if [[ -n "$(oc -n tradeops get secret tradeops-runtime-secrets -o jsonpath='{.data.LITELLM_PROVIDER_API_KEY}' 2>/dev/null || true)" ]]; then
    oc -n tradeops patch secret tradeops-runtime-secrets --type=json       -p='[{"op":"remove","path":"/data/LITELLM_PROVIDER_API_KEY"}]' >/dev/null
  fi

  OLLAMA_HOSTNAME="$(python - "${API_BASE}" <<'PY'
import sys, urllib.parse
url=urllib.parse.urlparse(sys.argv[1])
if url.scheme != "http" or url.port != 11434 or not url.hostname:
    raise SystemExit("D090_LOCAL_OLLAMA_PRECHECK=FAIL api_base_must_be_http_port_11434")
print(url.hostname)
PY
)"
  OLLAMA_HOST_IP="$(oc -n tradeops exec deploy/ai-access-policy --     python -c 'import socket,sys; print(socket.gethostbyname(sys.argv[1]))' "${OLLAMA_HOSTNAME}")"
  OLLAMA_HOST_CIDR="$(python - "${OLLAMA_HOST_IP}" <<'PY'
import ipaddress, sys
ip=ipaddress.ip_address(sys.argv[1].strip())
if ip.version != 4:
    raise SystemExit("D090_OLLAMA_HOST_RESOLUTION=FAIL ipv4_required")
print(f"{ip}/32")
PY
)"
  echo "D090_OLLAMA_HOST_RESOLUTION=PASS host=${OLLAMA_HOSTNAME} cidr=${OLLAMA_HOST_CIDR}"

  python - "${OLLAMA_HOST_CIDR}" <<'PY' | oc apply -f - >/dev/null
from pathlib import Path
import sys
template=Path("infra/ai-access/networkpolicy-local-ollama-crc.template.yaml").read_text(encoding="utf-8")
print(template.replace("__OLLAMA_HOST_CIDR__", sys.argv[1]), end="")
PY
  echo "D090_OLLAMA_NETWORKPOLICY=PASS cidr=${OLLAMA_HOST_CIDR} port=11434"
fi

{
  cat <<'EOF'
model_list:
  - model_name: tradeops-default
    litellm_params:
      model: os.environ/TRADEOPS_LITELLM_MODEL
EOF
  if [[ -n "${API_BASE}" ]]; then
    echo '      api_base: os.environ/TRADEOPS_LITELLM_API_BASE'
  fi
  if [[ "${PROFILE}" == "hosted" ]]; then
    echo '      api_key: os.environ/LITELLM_PROVIDER_API_KEY'
  fi
  cat <<'EOF'
  - model_name: odm-extraction
    litellm_params:
      model: os.environ/TRADEOPS_LITELLM_MODEL
EOF
  if [[ -n "${API_BASE}" ]]; then
    echo '      api_base: os.environ/TRADEOPS_LITELLM_API_BASE'
  fi
  if [[ "${PROFILE}" == "hosted" ]]; then
    echo '      api_key: os.environ/LITELLM_PROVIDER_API_KEY'
  fi
  cat <<'EOF'
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
litellm_settings:
  set_verbose: false
EOF
} > "${CONFIG_FILE}"

oc -n tradeops create configmap d090-litellm-config   --from-file=config.yaml="${CONFIG_FILE}"   --dry-run=client -o yaml | oc apply -f - >/dev/null
rm -f "${CONFIG_FILE}"

oc apply -f infra/ai-access/litellm-deployment-crc.yaml >/dev/null
oc -n tradeops rollout restart deploy/litellm >/dev/null

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

oc -n tradeops exec -i deploy/ai-access-policy -- python - <<'PY'
import urllib.request
with urllib.request.urlopen("http://litellm:4000/health/readiness", timeout=10) as r:
    assert r.status == 200
print("D090_LITELLM_READINESS=PASS")
PY

if [[ "${PROFILE}" == "local-ollama" ]]; then
  if ! oc -n tradeops exec -i deploy/litellm -- python - <<'PY'
import json, os, urllib.request
base=os.environ["TRADEOPS_LITELLM_API_BASE"].rstrip("/")
with urllib.request.urlopen(base + "/api/tags", timeout=8) as r:
    assert r.status == 200
    payload=json.load(r)
assert isinstance(payload.get("models"), list)
print("D090_OLLAMA_REACHABILITY=PASS")
PY
  then
    echo "D090_OLLAMA_REACHABILITY=FAIL" >&2
    echo "action=verify Ollama on Windows; only if required set OLLAMA_HOST=0.0.0.0:11434 and restrict Windows Firewall TCP/11434 to the CRC virtual network" >&2
    exit 3
  fi

  oc -n tradeops exec -i deploy/litellm -- python - <<'PY'
import json, os, urllib.request
payload={
  "model":"tradeops-default",
  "messages":[{"role":"user","content":"Return exactly D090_LOCAL_MODEL_OK."}],
  "temperature":0,
}
req=urllib.request.Request(
  "http://127.0.0.1:4000/v1/chat/completions",
  data=json.dumps(payload).encode(),
  headers={
    "Authorization":"Bearer " + os.environ["LITELLM_MASTER_KEY"],
    "Content-Type":"application/json",
  },
  method="POST",
)
with urllib.request.urlopen(req, timeout=90) as r:
    body=json.load(r)
text=str(body["choices"][0]["message"]["content"])
assert text.strip(), body
model=str(body.get("model","")).strip()
assert model, body
print(f"D090_LITELLM_LOCAL_MODEL_E2E=PASS model={model}")
PY
  echo "D090_LOCAL_REAL_MODEL_PRECHECK=PASS"
fi

echo "D090_LITELLM_DEPLOY=PASS profile=${PROFILE} model=${MODEL}"
