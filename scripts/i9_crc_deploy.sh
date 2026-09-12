#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_MODE="${DEPLOY_MODE:-direct}"

: "${POSTGRES_PASSWORD:?export POSTGRES_PASSWORD before deploying}"
: "${GRAFANA_ADMIN_PASSWORD:?export GRAFANA_ADMIN_PASSWORD before deploying}"

cd "$ROOT"

oc apply -k infra/openshift/overlays/crc
oc -n tradeops create secret generic tradeops-runtime-secrets \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --from-literal=GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD}" \
  --dry-run=client -o yaml | oc apply -f -

oc -n tradeops start-build tradeops-runtime --follow --wait

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
