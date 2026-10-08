#!/usr/bin/env bash
# D-099 AA1: read-only baseline checks; no model inference or cluster change.
set -euo pipefail
echo "D099_AA1_PREFLIGHT_START"
if [[ "${D099_AA1_INFERENCE:-NO}" == "YES" ]]; then
  echo "AA1_INFERENCE_DENIED=use_separate_supervised_test" >&2
  exit 3
fi
for required in opencode ollama curl; do
  if ! command -v "$required" >/dev/null 2>&1; then
    echo "AA1_MISSING_TOOL=$required" >&2
    exit 2
  fi
done
echo "AA1_OPENCODE_VERSION_START"
opencode --version
echo "AA1_OLLAMA_VERSION_START"
ollama --version
echo "AA1_OLLAMA_SERVER_VERSION_START"
curl --fail --silent --show-error --max-time 8 http://127.0.0.1:11434/api/version
printf '\n'
echo "AA1_INSTALLED_MODELS_START"
ollama list
echo "D099_AA1_PREFLIGHT_PASS"
echo "D099_AA1_OPEN_CODE_MODEL_INFERENCE=PENDING"
echo "D099_AA1_TOOL_GOVERNANCE_RUNTIME=PENDING"
echo "D099_AA1_LOCAL_MODEL_BASELINE_VALIDATED=NO"
