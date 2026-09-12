#!/usr/bin/env bash
set -euo pipefail

: "${MLFLOW_TRACKING_URI:?set MLFLOW_TRACKING_URI}"
: "${MODEL_URI:?set MODEL_URI}"
: "${MODEL_QUALIFICATION:?set MODEL_QUALIFICATION}"
MODEL_SERVING_MODE="${MODEL_SERVING_MODE:-LAB}"

./scripts/i10_rhoai_preflight.sh
oc apply -f infra/openshift-ai/base/namespace.yaml
oc apply -f infra/openshift-ai/base/serviceaccount-rbac.yaml
oc apply -f infra/openshift-ai/base/build.yaml

oc -n tradeops-ai create secret generic tradeops-model-serving-config \
  --from-literal=model-uri="${MODEL_URI}" \
  --from-literal=qualification="${MODEL_QUALIFICATION}" \
  --from-literal=serving-mode="${MODEL_SERVING_MODE}" \
  --from-literal=mlflow-tracking-uri="${MLFLOW_TRACKING_URI}" \
  --dry-run=client -o yaml | oc apply -f -

oc start-build tradeops-ai-runtime --from-dir=. --follow -n tradeops-ai
oc apply -f infra/openshift-ai/base/servingruntime-signal-quality.yaml
oc apply -f infra/openshift-ai/base/inferenceservice-signal-quality.yaml
oc apply -f infra/openshift-ai/monitoring/slo-rules.yaml

echo "I10_RHOAI_DEPLOY_SUBMITTED"
