#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_MODE="${DEPLOY_MODE:-direct}"

: "${POSTGRES_PASSWORD:?export POSTGRES_PASSWORD before deploying}"
: "${GRAFANA_ADMIN_PASSWORD:?export GRAFANA_ADMIN_PASSWORD before deploying}"
: "${MCP_AGENT_TOKEN:?export MCP_AGENT_TOKEN before deploying}"
: "${MCP_REVIEWER_TOKEN:?export MCP_REVIEWER_TOKEN before deploying}"
: "${MQ_OPS_SERVICE_TOKEN:?export MQ_OPS_SERVICE_TOKEN before deploying R5}"

cd "$ROOT"

oc apply -k infra/openshift/overlays/crc
SECRET_PATCH="$(POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  GRAFANA_ADMIN_PASSWORD="$GRAFANA_ADMIN_PASSWORD" \
  MCP_AGENT_TOKEN="$MCP_AGENT_TOKEN" \
  MCP_REVIEWER_TOKEN="$MCP_REVIEWER_TOKEN" \
  MQ_OPS_SERVICE_TOKEN="$MQ_OPS_SERVICE_TOKEN" python - <<'PY'
import base64
import json
import os

values = {
    "POSTGRES_PASSWORD": os.environ["POSTGRES_PASSWORD"],
    "GRAFANA_ADMIN_PASSWORD": os.environ["GRAFANA_ADMIN_PASSWORD"],
    "MCP_AGENT_TOKEN": os.environ["MCP_AGENT_TOKEN"],
    "MCP_REVIEWER_TOKEN": os.environ["MCP_REVIEWER_TOKEN"],
    "MQ_OPS_API_TOKEN": os.environ["MQ_OPS_SERVICE_TOKEN"],
}
print(json.dumps({
    "data": {
        key: base64.b64encode(value.encode()).decode()
        for key, value in values.items()
    }
}, separators=(",", ":")))
PY
)"
oc -n tradeops patch secret tradeops-runtime-secrets --type=merge -p "$SECRET_PATCH" >/dev/null
unset SECRET_PATCH

oc -n tradeops start-build tradeops-runtime --follow --wait
oc -n tradeops start-build tradeops-ui --follow --wait

if oc api-resources --api-group=policies.kyverno.io 2>/dev/null | grep -q ValidatingPolicy; then
  oc apply -k infra/openshift/policies/kyverno
else
  echo "Kyverno ValidatingPolicy CRD not present: policy manifests retained but not applied."
fi

if [[ "$DEPLOY_MODE" == "gitops" ]]; then
  oc get namespace argocd >/dev/null
  oc api-resources --api-group=argoproj.io | grep -q Application
  oc apply -f gitops/argocd/project.yaml
  oc apply -f gitops/argocd/platform-guardrails.yaml
  oc apply -f gitops/argocd/kyverno-policies.yaml
  oc apply -f gitops/argocd/application.yaml
  echo "I9_CRC_DEPLOY_SUBMITTED mode=gitops"
else
  helm upgrade --install tradeops infra/helm/tradeops \
    --namespace tradeops \
    --create-namespace \
    -f infra/helm/tradeops/values.yaml \
    -f infra/helm/tradeops/values-crc.yaml \
    --wait --timeout 15m
  echo "I9_CRC_DEPLOY_PASS mode=direct"
fi
