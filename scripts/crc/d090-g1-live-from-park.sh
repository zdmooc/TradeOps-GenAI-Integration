#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

NAMESPACE="${TRADEOPS_NAMESPACE:-tradeops}"
STATE_ROOT="${TRADEOPS_PARK_STATE_ROOT:-$ROOT/.runtime/tradeops-park}"
SNAPSHOT="${TRADEOPS_PARK_SNAPSHOT:-}"
PROFILE="${D090_LITELLM_PROFILE:-local-ollama}"
MODEL="${D090_LITELLM_MODEL:-ollama/qwen2.5:3b}"
API_BASE="${D090_LITELLM_API_BASE:-}"

REQUIRED_DEPLOYMENTS=(ai-access-policy genai-api litellm)
ACTIVATION_DEPLOYMENTS=(ai-access-policy genai-api)
WINDOW_FILE=""

for cmd in oc awk grep; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "D090_G1_WINDOW_FAIL: missing required command: $cmd" >&2
    exit 2
  fi
done

if [[ -z "$SNAPSHOT" ]]; then
  if [[ ! -f "$STATE_ROOT/LATEST" ]]; then
    echo "D090_G1_WINDOW_FAIL: no PARK snapshot found" >&2
    exit 2
  fi
  SNAPSHOT="$(cat "$STATE_ROOT/LATEST")"
fi

if [[ ! -d "$SNAPSHOT" || ! -f "$SNAPSHOT/deployments.tsv" ]]; then
  echo "D090_G1_WINDOW_FAIL: invalid PARK snapshot: $SNAPSHOT" >&2
  exit 2
fi

if [[ ! -f "$SNAPSHOT/status" ]] || ! grep -qx "PARKED" "$SNAPSHOT/status"; then
  echo "D090_G1_WINDOW_FAIL: TradeOps must still be PARKED" >&2
  exit 2
fi

if [[ "$PROFILE" != "local-ollama" ]]; then
  echo "D090_G1_WINDOW_FAIL: this bounded CRC wrapper currently supports local-ollama only" >&2
  exit 2
fi

if [[ "$MODEL" != ollama/* ]]; then
  echo "D090_G1_WINDOW_FAIL: local profile model must start with ollama/" >&2
  exit 2
fi

: "${API_BASE:?export D090_LITELLM_API_BASE explicitly, e.g. http://192.168.56.1:11434}"

WINDOW_FILE="$SNAPSHOT/g1-window.tsv"
: > "$WINDOW_FILE"

for name in "${REQUIRED_DEPLOYMENTS[@]}"; do
  line="$(awk -F '\t' -v n="$name" '$1==n {print $0}' "$SNAPSHOT/deployments.tsv")"
  if [[ -z "$line" ]]; then
    echo "D090_G1_WINDOW_FAIL: deployment/$name absent from PARK snapshot" >&2
    exit 1
  fi
  replicas="$(printf '%s\n' "$line" | awk -F '\t' '{print $2}')"
  if [[ ! "$replicas" =~ ^[0-9]+$ ]] || (( replicas < 1 )); then
    echo "D090_G1_WINDOW_FAIL: deployment/$name snapshot replicas=$replicas, expected >=1" >&2
    exit 1
  fi
  printf '%s\t%s\n' "$name" "$replicas" >> "$WINDOW_FILE"
done

oc whoami >/dev/null
oc get namespace "$NAMESPACE" >/dev/null
oc -n mayabank-api wait --for=condition=Available deploy/api-gateway --timeout=120s >/dev/null
oc -n shared-observability wait --for=condition=Available deploy/otel-collector --timeout=120s >/dev/null

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  local cleanup_fail=0

  if [[ -f "$WINDOW_FILE" ]]; then
    while IFS=$'\t' read -r name _replicas; do
      [[ -n "$name" ]] || continue
      if ! oc -n "$NAMESPACE" scale "deployment/$name" --replicas=0 >/dev/null; then
        echo "D090_G1_WINDOW_REPARK_FAIL: deployment/$name" >&2
        cleanup_fail=1
      fi
    done < "$WINDOW_FILE"

    while IFS=$'\t' read -r name _replicas; do
      [[ -n "$name" ]] || continue
      current="$(oc -n "$NAMESPACE" get "deployment/$name" -o jsonpath='{.spec.replicas}' 2>/dev/null || true)"
      if [[ "$current" != "0" ]]; then
        echo "D090_G1_WINDOW_REPARK_FAIL: deployment/$name desired=$current expected=0" >&2
        cleanup_fail=1
      fi
    done < "$WINDOW_FILE"
  fi

  if [[ "$cleanup_fail" == "0" ]]; then
    echo "D090_G1_WINDOW_REPARK=PASS"
  fi

  if [[ "$rc" != "0" ]]; then
    exit "$rc"
  fi
  if [[ "$cleanup_fail" != "0" ]]; then
    exit 1
  fi
}
trap cleanup EXIT INT TERM

for name in "${ACTIVATION_DEPLOYMENTS[@]}"; do
  replicas="$(awk -F '\t' -v n="$name" '$1==n {print $2}' "$WINDOW_FILE")"
  echo "G1 WINDOW deployment/$name: 0 -> $replicas"
  oc -n "$NAMESPACE" scale "deployment/$name" --replicas="$replicas"
done

for name in "${ACTIVATION_DEPLOYMENTS[@]}"; do
  oc -n "$NAMESPACE" rollout status "deployment/$name" --timeout=300s
done

echo "D090_G1_WINDOW_BASE_ACTIVE=PASS"

export D090_LITELLM_PROFILE="$PROFILE"
export D090_LITELLM_MODEL="$MODEL"
export D090_LITELLM_API_BASE="$API_BASE"

bash scripts/d090_deploy_litellm_crc.sh
echo "D090_G1_WINDOW_ACTIVE=PASS"
bash scripts/d090_enable_genai_crc.sh
bash scripts/d090_run_g1_live_crc.sh

if [[ "${D090_RUN_G3_G4_SHARED_ISOLATION:-no}" == "yes" ]]; then
  bash scripts/d090_shared_isolation_crc.sh
  echo "D090_G3_G4_FROM_PARK=PASS"
fi

echo "D090_G1_FROM_PARK=PASS"
