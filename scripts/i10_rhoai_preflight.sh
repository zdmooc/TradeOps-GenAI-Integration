#!/usr/bin/env bash
set -euo pipefail

command -v oc >/dev/null
command -v python >/dev/null
oc whoami >/dev/null
oc get datasciencecluster default-dsc >/dev/null
oc get crd inferenceservices.serving.kserve.io >/dev/null
oc get crd servingruntimes.serving.kserve.io >/dev/null

KSTATE="$(oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.kserve.managementState}')"
MSTATE="$(oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.mlflowoperator.managementState}')"
[[ "${KSTATE}" == "Managed" ]] || { echo "KServe is not Managed" >&2; exit 1; }
[[ "${MSTATE}" == "Managed" ]] || { echo "MLflow Operator is not Managed" >&2; exit 1; }

oc get clusterrole mlflow-operator-mlflow-integration >/dev/null
oc get servingruntime -A | grep -E 'vllm|vLLM' >/dev/null || true

echo "I10_RHOAI_PREFLIGHT_PASS"
