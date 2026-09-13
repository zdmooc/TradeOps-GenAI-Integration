#!/usr/bin/env bash
set -euo pipefail

namespace=tradeops

oc -n "$namespace" get pods -o wide
oc -n "$namespace" get resourcequota,limitrange,networkpolicy
oc -n "$namespace" get routes

for name in market-data workflow-api genai-api rag-api agent-controller mcp-server risk-engine paper-oms notifier otel-collector prometheus grafana tradeops-ui; do
  oc -n "$namespace" rollout status "deployment/$name" --timeout=180s
done
for name in postgres redpanda qdrant; do
  oc -n "$namespace" rollout status "statefulset/$name" --timeout=180s
done

if oc -n "$namespace" get deployment signal-engine >/dev/null 2>&1; then
  echo "I9_CRC_VERIFY_FAIL: legacy signal-engine must not be deployed"
  exit 1
fi

agent_host="$(oc -n "$namespace" get route agent-controller -o jsonpath='{.spec.host}')"
ui_host="$(oc -n "$namespace" get route tradeops-ui -o jsonpath='{.spec.host}')"
workflow_host="$(oc -n "$namespace" get route workflow-api -o jsonpath='{.spec.host}')"

curl -fsSk "https://${agent_host}/health" >/dev/null
curl -fsSk "https://${workflow_host}/health" >/dev/null
curl -fsSk "https://${ui_host}/healthz" >/dev/null
curl -fsSk "https://${ui_host}/api/agent/health" >/dev/null
curl -fsSk "https://${ui_host}/api/workflow/health" >/dev/null

printf 'TRADEOPS_UI_URL=https://%s\n' "$ui_host"
echo "I9_CRC_VERIFY_PASS"
