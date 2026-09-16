#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MQ_REPO="${MQ_REPO:-$ROOT/../mayabank-ibm-mq-native-ha-openshift-eda-platform}"

command -v oc >/dev/null
command -v helm >/dev/null
command -v openssl >/dev/null
command -v base64 >/dev/null

[[ -f "$MQ_REPO/scripts/agentic/r5-deploy-mq-ops.sh" ]] || {
  echo "STOP: MayaBank MQ repository not found at: $MQ_REPO" >&2
  echo "Set MQ_REPO=/path/to/mayabank-ibm-mq-native-ha-openshift-eda-platform" >&2
  exit 1
}

read_secret() {
  local ns="$1" secret="$2" key="$3" encoded
  encoded="$(oc -n "$ns" get secret "$secret" -o "jsonpath={.data.$key}" 2>/dev/null || true)"
  [[ -n "$encoded" ]] || return 1
  printf '%s' "$encoded" | base64 -d 2>/dev/null
}

ensure_value() {
  local var_name="$1" ns="$2" secret="$3" key="$4" value=""
  value="${!var_name:-}"
  if [[ -z "$value" ]]; then
    value="$(read_secret "$ns" "$secret" "$key" || true)"
  fi
  if [[ -z "$value" ]]; then
    value="$(openssl rand -hex 24 | tr -d '\r\n')"
    echo "Generated missing $var_name for local CRC (value hidden)."
  else
    echo "Reusing existing $var_name for local CRC (value hidden)."
  fi
  printf -v "$var_name" '%s' "$value"
  export "$var_name"
}

# Reuse the already deployed TradeOps secrets whenever possible. Fresh local CRCs
# get new random values, never printed and never written to git.
ensure_value POSTGRES_PASSWORD tradeops tradeops-runtime-secrets POSTGRES_PASSWORD
ensure_value GRAFANA_ADMIN_PASSWORD tradeops tradeops-runtime-secrets GRAFANA_ADMIN_PASSWORD
ensure_value MCP_AGENT_TOKEN tradeops tradeops-runtime-secrets MCP_AGENT_TOKEN
ensure_value MCP_REVIEWER_TOKEN tradeops tradeops-runtime-secrets MCP_REVIEWER_TOKEN

# Both sides of the internal TradeOps -> mq-ops-api link must share one service
# token. Prefer the MayaBank secret because it is the adapter's authoritative copy.
if [[ -z "${MQ_OPS_SERVICE_TOKEN:-}" ]]; then
  MQ_OPS_SERVICE_TOKEN="$(read_secret mayabank-mq-local mq-ops-api-credentials token || true)"
fi
if [[ -z "${MQ_OPS_SERVICE_TOKEN:-}" ]]; then
  MQ_OPS_SERVICE_TOKEN="$(read_secret tradeops tradeops-runtime-secrets MQ_OPS_API_TOKEN || true)"
fi
if [[ -z "${MQ_OPS_SERVICE_TOKEN:-}" ]]; then
  MQ_OPS_SERVICE_TOKEN="$(openssl rand -hex 24 | tr -d '\r\n')"
  echo "Generated missing MQ_OPS_SERVICE_TOKEN for local CRC (value hidden)."
else
  echo "Reusing existing MQ_OPS_SERVICE_TOKEN for local CRC (value hidden)."
fi
export MQ_OPS_SERVICE_TOKEN

printf '%s\n' "=== R5/1 MayaBank MQ read-only adapter ==="
(
  cd "$MQ_REPO"
  bash scripts/agentic/r5-deploy-mq-ops.sh
)

printf '%s\n' "=== R5/2 TradeOps native MCP runtime ==="
(
  cd "$ROOT"
  DEPLOY_MODE=direct bash scripts/i9_crc_deploy.sh
)

printf '%s\n' "=== R5/3 Rollout gates ==="
oc -n mayabank-mq-local rollout status deployment/mq --timeout=180s
oc -n mayabank-mq-local rollout status deployment/mq-ops-api --timeout=180s
oc -n tradeops rollout status deployment/mcp-native --timeout=180s
oc -n tradeops rollout status deployment/agent-controller --timeout=180s

printf '%s\n' "=== R5/4 Runtime inventory ==="
oc -n mayabank-mq-local get pods -l 'app in (mayabank-mq,mq-ops-api)' -o wide
oc -n tradeops get pods -l 'app.kubernetes.io/name in (mcp-native,agent-controller)' -o wide
oc -n mayabank-mq-local get svc mq mq-ops-api
oc -n tradeops get svc mcp-native agent-controller

echo "R5_CRC_DEPLOY_PASS"
echo "Next: bash scripts/r5_crc_mcp_mq_verify.sh"
