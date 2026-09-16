#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MQ_REPO="${MQ_REPO:-$ROOT/../mayabank-ibm-mq-native-ha-openshift-eda-platform}"

: "${POSTGRES_PASSWORD:?export POSTGRES_PASSWORD}"
: "${GRAFANA_ADMIN_PASSWORD:?export GRAFANA_ADMIN_PASSWORD}"
: "${MCP_AGENT_TOKEN:?export MCP_AGENT_TOKEN}"
: "${MCP_REVIEWER_TOKEN:?export MCP_REVIEWER_TOKEN}"
: "${MQ_OPS_SERVICE_TOKEN:?export MQ_OPS_SERVICE_TOKEN}"

[[ -f "$MQ_REPO/scripts/agentic/r5-deploy-mq-ops.sh" ]] || {
  echo "STOP: MayaBank MQ repository not found at: $MQ_REPO" >&2
  echo "Set MQ_REPO=/path/to/mayabank-ibm-mq-native-ha-openshift-eda-platform" >&2
  exit 1
}

command -v oc >/dev/null
command -v helm >/dev/null

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
