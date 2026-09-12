#!/usr/bin/env bash
set -euo pipefail

oc wait --for=condition=Ready inferenceservice/tradeops-signal-quality \
  -n tradeops-ai --timeout=10m
READY="$(oc get inferenceservice tradeops-signal-quality -n tradeops-ai \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')"
[[ "${READY}" == "True" ]]

oc get servingruntime tradeops-mlflow-runtime -n tradeops-ai >/dev/null
oc get prometheusrule tradeops-ai-serving-slos -n tradeops-ai >/dev/null
oc get rolebinding tradeops-model-serving-mlflow -n tradeops-ai >/dev/null

URL="$(oc get inferenceservice tradeops-signal-quality -n tradeops-ai \
  -o jsonpath='{.status.url}')"
[[ -n "${URL}" ]]
echo "inference_url=${URL}"
echo "I10_RHOAI_VERIFY_PASS"
