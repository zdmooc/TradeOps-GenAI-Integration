#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

oc get clusterversion version >/dev/null
oc -n keycloak-system wait --for=condition=Ready keycloak/keycloak --timeout=60s >/dev/null
oc -n mayabank-api wait --for=condition=Available deploy/api-gateway --timeout=60s >/dev/null
oc -n shared-observability wait --for=condition=Available deploy/otel-collector --timeout=60s >/dev/null

curl -kfsS https://keycloak.apps-crc.testing/realms/mayabank/.well-known/openid-configuration >/dev/null

bash scripts/d090_bootstrap_oidc_crc.sh

oc apply -f infra/openshift/base/networkpolicies.yaml >/dev/null
oc apply -f infra/ai-access/ai-access-policy-crc.yaml >/dev/null
oc -n tradeops rollout status deploy/ai-access-policy --timeout=180s

echo "D090_G1A_PREPARE=PASS"
echo "next=enable canonical Kong /ai route, then configure LiteLLM provider"
