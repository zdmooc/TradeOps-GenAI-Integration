#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

NAMESPACE="${TRADEOPS_NAMESPACE:-tradeops}"
MQ_REPO="${MQ_REPO:-$ROOT/../mayabank-ibm-mq-native-ha-openshift-eda-platform}"
STATE_ROOT="${TRADEOPS_PARK_STATE_ROOT:-$ROOT/.runtime/tradeops-park}"
SNAPSHOT="${TRADEOPS_PARK_SNAPSHOT:-}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK=""

for cmd in oc helm python openssl base64 sha256sum curl; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "R5_CRC_FROM_PARK_FAIL missing_command=$cmd" >&2
    exit 2
  }
done

[[ -f "$MQ_REPO/scripts/agentic/r5-deploy-mq-ops.sh" ]] || {
  echo "R5_CRC_FROM_PARK_FAIL mq_repo_not_found=$MQ_REPO" >&2
  exit 2
}

if [[ -z "$SNAPSHOT" ]]; then
  [[ -f "$STATE_ROOT/LATEST" ]] || {
    echo "R5_CRC_FROM_PARK_FAIL park_snapshot_missing" >&2
    exit 2
  }
  SNAPSHOT="$(cat "$STATE_ROOT/LATEST")"
fi
[[ -f "$SNAPSHOT/status" ]] && grep -qx PARKED "$SNAPSHOT/status" || {
  echo "R5_CRC_FROM_PARK_FAIL tradeops_not_parked snapshot=$SNAPSHOT" >&2
  exit 2
}
[[ -f "$SNAPSHOT/deployments.tsv" ]] || {
  echo "R5_CRC_FROM_PARK_FAIL deployment_snapshot_missing" >&2
  exit 2
}
echo "R5_CRC_PARK_PRECONDITION=PASS snapshot=$SNAPSHOT"

oc whoami >/dev/null
oc get namespace "$NAMESPACE" >/dev/null

ADOPTION="$(oc get capabilityconsumption tradeops-crc -o jsonpath='{.spec.lifecycle.adoptionPolicy}' 2>/dev/null || true)"
[[ "$ADOPTION" == "Observe" ]] || {
  echo "R5_CRC_FROM_PARK_FAIL tradeops_cr_must_remain_observe current=${ADOPTION:-ABSENT}" >&2
  exit 2
}
echo "R5_CRC_D093_OBSERVE_GUARD=PASS"

AGENT_ORIGINAL_REPLICAS="$(awk -F '\t' '$1=="agent-controller" {print $2}' "$SNAPSHOT/deployments.tsv")"
[[ "$AGENT_ORIGINAL_REPLICAS" =~ ^[0-9]+$ ]] && (( AGENT_ORIGINAL_REPLICAS >= 1 )) || {
  echo "R5_CRC_FROM_PARK_FAIL agent_controller_missing_from_snapshot" >&2
  exit 1
}
CURRENT_AGENT_REPLICAS="$(oc -n "$NAMESPACE" get deploy/agent-controller -o jsonpath='{.spec.replicas}')"
[[ "$CURRENT_AGENT_REPLICAS" == "0" ]] || {
  echo "R5_CRC_FROM_PARK_FAIL agent_controller_not_parked replicas=$CURRENT_AGENT_REPLICAS" >&2
  exit 1
}

WORK="$SNAPSHOT/r5-$STAMP"
mkdir -p "$WORK"

# Preserve the exact pre-existing Secret data except for the one R5 service-token key.
SECRET_FINGERPRINT_BEFORE="$(
  oc -n "$NAMESPACE" get secret tradeops-runtime-secrets -o json |
    python -c 'import hashlib,json,sys; d=json.load(sys.stdin).get("data",{}); d.pop("MQ_OPS_API_TOKEN",None); print(hashlib.sha256(json.dumps(d,sort_keys=True,separators=(",",":")).encode()).hexdigest())'
)"
echo "$SECRET_FINGERPRINT_BEFORE" > "$WORK/00-secret-fingerprint-before.txt"

read_secret() {
  local ns="$1" secret="$2" key="$3" encoded
  encoded="$(oc -n "$ns" get secret "$secret" -o "jsonpath={.data.$key}" 2>/dev/null || true)"
  [[ -n "$encoded" ]] || return 1
  printf '%s' "$encoded" | base64 -d 2>/dev/null
}

for required_key in POSTGRES_PASSWORD MCP_AGENT_TOKEN MCP_REVIEWER_TOKEN; do
  read_secret "$NAMESPACE" tradeops-runtime-secrets "$required_key" >/dev/null || {
    echo "R5_CRC_FROM_PARK_FAIL missing_tradeops_secret_key=$required_key" >&2
    exit 1
  }
done

MQ_OPS_SERVICE_TOKEN="${MQ_OPS_SERVICE_TOKEN:-}"
if [[ -z "$MQ_OPS_SERVICE_TOKEN" ]]; then
  MQ_OPS_SERVICE_TOKEN="$(read_secret mayabank-mq-local mq-ops-api-credentials token || true)"
fi
if [[ -z "$MQ_OPS_SERVICE_TOKEN" ]]; then
  MQ_OPS_SERVICE_TOKEN="$(read_secret "$NAMESPACE" tradeops-runtime-secrets MQ_OPS_API_TOKEN || true)"
fi
if [[ -z "$MQ_OPS_SERVICE_TOKEN" ]]; then
  MQ_OPS_SERVICE_TOKEN="$(openssl rand -hex 24 | tr -d '\r\n')"
  echo "R5_CRC_MQ_SERVICE_TOKEN=GENERATED_LOCAL"
else
  echo "R5_CRC_MQ_SERVICE_TOKEN=REUSED"
fi
export MQ_OPS_SERVICE_TOKEN

SECRET_PATCH="$(MQ_OPS_SERVICE_TOKEN="$MQ_OPS_SERVICE_TOKEN" python - <<'PY'
import base64,json,os
value=base64.b64encode(os.environ["MQ_OPS_SERVICE_TOKEN"].encode()).decode()
print(json.dumps({"data":{"MQ_OPS_API_TOKEN":value}},separators=(",",":")))
PY
)"
oc -n "$NAMESPACE" patch secret tradeops-runtime-secrets --type=merge -p "$SECRET_PATCH" >/dev/null
unset SECRET_PATCH

SECRET_FINGERPRINT_AFTER="$(
  oc -n "$NAMESPACE" get secret tradeops-runtime-secrets -o json |
    python -c 'import hashlib,json,sys; d=json.load(sys.stdin).get("data",{}); d.pop("MQ_OPS_API_TOKEN",None); print(hashlib.sha256(json.dumps(d,sort_keys=True,separators=(",",":")).encode()).hexdigest())'
)"
[[ "$SECRET_FINGERPRINT_BEFORE" == "$SECRET_FINGERPRINT_AFTER" ]] || {
  echo "R5_CRC_FROM_PARK_FAIL non_r5_secret_keys_changed" >&2
  exit 1
}
echo "R5_CRC_SECRET_MERGE=PASS"

printf '%s\n' "=== R5/1 MayaBank MQ read-only adapter ==="
(
  cd "$MQ_REPO"
  bash scripts/agentic/r5-deploy-mq-ops.sh
)

# Ensure only the runtime image required by agent-controller/mcp-native is current.
if ! oc -n "$NAMESPACE" get bc/tradeops-runtime >/dev/null 2>&1; then
  oc apply -f infra/openshift/base/build.yaml >/dev/null
fi

runtime_image() {
  oc -n "$NAMESPACE" get istag tradeops-runtime:i9 -o jsonpath='{.image.dockerImageReference}' 2>/dev/null || true
}

image_supports_mcp_native() {
  local image="$1" pod="r5-module-check-${STAMP,,}" phase=""
  [[ -n "$image" ]] || return 1
  oc -n "$NAMESPACE" delete pod "$pod" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  oc -n "$NAMESPACE" run "$pod" --image="$image" --restart=Never \
    --command --dry-run=client -o json -- python -c \
    'import services.mcp_native.server; print("R5_MCP_NATIVE_MODULE_PASS")' |
    python -c '
import json, sys
pod = json.load(sys.stdin)
pod["spec"]["enableServiceLinks"] = False
pod["spec"]["securityContext"] = {
    "runAsNonRoot": True,
    "seccompProfile": {"type": "RuntimeDefault"}
}
for container in pod["spec"]["containers"]:
    container["securityContext"] = {
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
        "runAsNonRoot": True
    }
json.dump(pod, sys.stdout)
' | oc -n "$NAMESPACE" apply -f - >/dev/null
  for _ in $(seq 1 60); do
    phase="$(oc -n "$NAMESPACE" get pod "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    case "$phase" in
      Succeeded)
        oc -n "$NAMESPACE" logs "$pod" > "$WORK/10-runtime-image-check.log" 2>&1 || true
        oc -n "$NAMESPACE" delete pod "$pod" --wait=false >/dev/null 2>&1 || true
        return 0
        ;;
      Failed)
        oc -n "$NAMESPACE" logs "$pod" > "$WORK/10-runtime-image-check.log" 2>&1 || true
        oc -n "$NAMESPACE" delete pod "$pod" --wait=false >/dev/null 2>&1 || true
        return 1
        ;;
    esac
    sleep 2
  done
  oc -n "$NAMESPACE" describe pod "$pod" > "$WORK/10-runtime-image-check.log" 2>&1 || true
  oc -n "$NAMESPACE" delete pod "$pod" --wait=false >/dev/null 2>&1 || true
  return 1
}

RUNTIME_IMAGE="$(runtime_image)"
if image_supports_mcp_native "$RUNTIME_IMAGE"; then
  echo "R5_CRC_RUNTIME_IMAGE=REUSED"
else
  if [[ "${R5_NO_AUTO_REBUILD:-false}" == "true" ]]; then
    echo "R5_CRC_RUNTIME_PROBE_FAILED_NO_REBUILD log=$WORK/10-runtime-image-check.log" >&2
    exit 1
  fi
  echo "R5_CRC_RUNTIME_IMAGE=REBUILD_REQUIRED"
  oc -n "$NAMESPACE" start-build tradeops-runtime --follow --wait
  RUNTIME_IMAGE="$(runtime_image)"
  [[ -n "$RUNTIME_IMAGE" ]] || {
    echo "R5_CRC_FROM_PARK_FAIL runtime_image_missing_after_build" >&2
    exit 1
  }
  image_supports_mcp_native "$RUNTIME_IMAGE" || {
    echo "R5_CRC_FROM_PARK_FAIL mcp_native_module_missing_after_build" >&2
    exit 1
  }
fi
echo "R5_CRC_RUNTIME_IMAGE_READY=PASS"

MCP_NATIVE_IN_SNAPSHOT=0
MCP_NATIVE_ORIGINAL_REPLICAS=0
if grep -q '^mcp-native[[:space:]]' "$SNAPSHOT/deployments.tsv"; then
  MCP_NATIVE_IN_SNAPSHOT=1
  MCP_NATIVE_ORIGINAL_REPLICAS="$(awk -F '\t' '$1=="mcp-native" {print $2}' "$SNAPSHOT/deployments.tsv")"
fi

if [[ "$MCP_NATIVE_IN_SNAPSHOT" == "0" ]] && oc -n "$NAMESPACE" get deploy/mcp-native >/dev/null 2>&1; then
  stale_replicas="$(oc -n "$NAMESPACE" get deploy/mcp-native -o jsonpath='{.spec.replicas}')"
  [[ "$stale_replicas" == "0" ]] || {
    echo "R5_CRC_FROM_PARK_FAIL unexpected_running_mcp_native=$stale_replicas" >&2
    exit 1
  }
  oc -n "$NAMESPACE" delete deploy/mcp-native svc/mcp-native --ignore-not-found >/dev/null
fi

AGENT_OLD_IMAGE="$(oc -n "$NAMESPACE" get deploy/agent-controller -o jsonpath='{.spec.template.spec.containers[0].image}')"
AGENT_OLD_MCP_URL="$(
  oc -n "$NAMESPACE" get deploy/agent-controller -o json |
    python -c 'import json,sys; d=json.load(sys.stdin); env=d["spec"]["template"]["spec"]["containers"][0].get("env",[]); print(next((x.get("value","") for x in env if x.get("name")=="MCP_NATIVE_URL"),""))'
)"
AGENT_OLD_MCP_PRESENT="$(
  oc -n "$NAMESPACE" get deploy/agent-controller -o json |
    python -c 'import json,sys; d=json.load(sys.stdin); env=d["spec"]["template"]["spec"]["containers"][0].get("env",[]); print("1" if any(x.get("name")=="MCP_NATIVE_URL" for x in env) else "0")'
)"

ROUTE_CREATED=0
cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  local cleanup_fail=0

  oc -n "$NAMESPACE" scale deploy/agent-controller --replicas=0 >/dev/null 2>&1 || cleanup_fail=1

  if [[ "$MCP_NATIVE_IN_SNAPSHOT" == "1" ]]; then
    oc -n "$NAMESPACE" scale deploy/mcp-native --replicas=0 >/dev/null 2>&1 || cleanup_fail=1
  else
    oc -n "$NAMESPACE" delete deploy/mcp-native svc/mcp-native --ignore-not-found --wait=false >/dev/null 2>&1 || cleanup_fail=1
  fi

  oc -n "$NAMESPACE" set image deploy/agent-controller "agent-controller=$AGENT_OLD_IMAGE" >/dev/null 2>&1 || cleanup_fail=1
  if [[ "$AGENT_OLD_MCP_PRESENT" == "1" ]]; then
    oc -n "$NAMESPACE" set env deploy/agent-controller "MCP_NATIVE_URL=$AGENT_OLD_MCP_URL" >/dev/null 2>&1 || cleanup_fail=1
  else
    oc -n "$NAMESPACE" set env deploy/agent-controller MCP_NATIVE_URL- >/dev/null 2>&1 || cleanup_fail=1
  fi

  if [[ "$ROUTE_CREATED" == "1" ]]; then
    oc -n "$NAMESPACE" delete route/agent-controller --ignore-not-found >/dev/null 2>&1 || cleanup_fail=1
  fi

  if [[ "$cleanup_fail" == "0" ]]; then
    echo "R5_CRC_WINDOW_REPARK=PASS"
  else
    echo "R5_CRC_WINDOW_REPARK=FAIL" >&2
  fi

  if [[ "$rc" != "0" ]]; then
    exit "$rc"
  fi
  [[ "$cleanup_fail" == "0" ]] || exit 1
}
trap cleanup EXIT INT TERM

# Render/apply only mcp-native from the existing chart; never Helm-upgrade the full release.
R5_VALUES="$WORK/20-r5-only-values.yaml"
cat > "$R5_VALUES" <<'YAML'
apps:
  market-data:
    enabled: false
  workflow-api:
    enabled: false
  ai-access-policy:
    enabled: false
  a2a-ops-agent:
    enabled: false
  genai-api:
    enabled: false
  rag-api:
    enabled: false
  agent-controller:
    enabled: false
  mcp-server:
    enabled: false
  mcp-native:
    enabled: true
  risk-engine:
    enabled: false
  paper-oms:
    enabled: false
  notifier:
    enabled: false
YAML

helm template tradeops infra/helm/tradeops \
  -f infra/helm/tradeops/values.yaml \
  -f infra/helm/tradeops/values-crc.yaml \
  -f "$R5_VALUES" \
  --show-only templates/app-workloads.yaml \
  > "$WORK/21-mcp-native-rendered.yaml"
oc -n "$NAMESPACE" apply -f "$WORK/21-mcp-native-rendered.yaml" >/dev/null
oc -n "$NAMESPACE" set image deploy/mcp-native "mcp-native=$RUNTIME_IMAGE" >/dev/null

# Apply only the canonical R5 NetworkPolicy document from the base file.
python - infra/openshift/base/networkpolicies.yaml > "$WORK/22-r5-networkpolicy.yaml" <<'PY'
import re,sys
text=open(sys.argv[1],encoding="utf-8").read()
for doc in re.split(r"(?m)^---\s*$", text):
    if re.search(r"(?m)^\s*name:\s*allow-mcp-native-to-mayabank-mq-ops\s*$", doc):
        print(doc.strip())
        raise SystemExit(0)
raise SystemExit("R5 NetworkPolicy document not found")
PY
oc -n "$NAMESPACE" apply -f "$WORK/22-r5-networkpolicy.yaml" >/dev/null

oc -n "$NAMESPACE" set image deploy/agent-controller "agent-controller=$RUNTIME_IMAGE" >/dev/null
oc -n "$NAMESPACE" set env deploy/agent-controller MCP_NATIVE_URL=http://mcp-native:8017/mcp >/dev/null

if ! oc -n "$NAMESPACE" get route/agent-controller >/dev/null 2>&1; then
  cat <<'YAML' | oc apply -f - >/dev/null
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: agent-controller
  namespace: tradeops
spec:
  to:
    kind: Service
    name: agent-controller
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
YAML
  ROUTE_CREATED=1
fi

oc -n "$NAMESPACE" scale deploy/agent-controller --replicas="$AGENT_ORIGINAL_REPLICAS" >/dev/null
oc -n "$NAMESPACE" rollout status deploy/mcp-native --timeout=180s
oc -n "$NAMESPACE" rollout status deploy/agent-controller --timeout=180s
echo "R5_CRC_BOUNDED_WINDOW_ACTIVE=PASS"

bash scripts/r5_crc_mcp_mq_verify.sh

echo "R5_CRC_FROM_PARK=PASS"
echo "R5_CRC_BOUNDED_EVIDENCE=$WORK"
