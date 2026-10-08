#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v oc >/dev/null
command -v curl >/dev/null
command -v python >/dev/null

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${R5_EVIDENCE_DIR:-$ROOT/evidence/r5/live/crc/$TS}"
mkdir -p "$OUT"

AGENT_HOST="$(oc -n tradeops get route agent-controller -o jsonpath='{.spec.host}')"
[[ -n "$AGENT_HOST" ]] || { echo "STOP: agent-controller route missing" >&2; exit 1; }

{
  echo "timestamp_utc=$TS"
  echo "tradeops_commit=$(git rev-parse HEAD)"
  echo "agent_controller_route=https://$AGENT_HOST"
} > "$OUT/00-summary.txt"

crc status > "$OUT/01-crc-status.txt" 2>&1 || true
oc version > "$OUT/02-oc-version.txt" 2>&1
oc get nodes -o wide > "$OUT/03-nodes.txt"

oc -n tradeops rollout status deployment/mcp-native --timeout=180s
oc -n tradeops rollout status deployment/agent-controller --timeout=180s
oc -n mayabank-mq-local rollout status deployment/mq --timeout=180s
oc -n mayabank-mq-local rollout status deployment/mq-ops-api --timeout=180s

oc -n tradeops get deploy,pod,svc,route -o wide > "$OUT/04-tradeops-runtime.txt"
oc -n mayabank-mq-local get deploy,pod,svc -o wide > "$OUT/05-mayabank-runtime.txt"
oc -n tradeops get networkpolicy -o yaml > "$OUT/06-tradeops-networkpolicies.yaml"
oc -n mayabank-mq-local get networkpolicy -o yaml > "$OUT/07-mayabank-networkpolicies.yaml"
oc -n tradeops get endpointslice -o wide > "$OUT/08-tradeops-endpoints.txt" 2>&1 || true
oc -n mayabank-mq-local get endpointslice -o wide > "$OUT/09-mayabank-endpoints.txt" 2>&1 || true

curl -fsSk "https://$AGENT_HOST/health" > "$OUT/10-agent-health.json"
curl -fsSk "https://$AGENT_HOST/agent/mcp/capabilities" > "$OUT/11-mcp-capabilities.json"
MQ_HTTP_CODE="$(curl -sSk --connect-timeout 5 --max-time 20 \
  -o "$OUT/12-mq-health-via-mcp.json" \
  -w '%{http_code}' \
  "https://$AGENT_HOST/agent/mcp/mq/health")" || MQ_HTTP_CODE="${MQ_HTTP_CODE:-000}"

if [[ "$MQ_HTTP_CODE" != "200" ]]; then
  echo "R5_MQ_HEALTH_HTTP_FAIL status=$MQ_HTTP_CODE evidence=$OUT" >&2
  oc -n tradeops logs deployment/agent-controller --tail=200 > "$OUT/20-agent-controller.log" 2>&1 || true
  oc -n tradeops logs deployment/mcp-native --tail=200 > "$OUT/19-mcp-native.log" 2>&1 || true
  oc -n mayabank-mq-local logs deployment/mq-ops-api --tail=200 > "$OUT/21-mq-ops-api.log" 2>&1 || true
  exit 1
fi

python - "$OUT/11-mcp-capabilities.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))['payload']
tools=set(p.get('tools', []))
required={'mq.get_queue_status','payments.get_mq_health'}
missing=required-tools
if missing:
    raise SystemExit('missing MCP tools: '+','.join(sorted(missing)))
print('MCP_TOOLS_PASS')
PY

python - "$OUT/12-mq-health-via-mcp.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))['payload']
assert p.get('qmgr') == 'QM.MAYABANK', p
assert p.get('status') in {'HEALTHY','WARNING','DEGRADED'}, p
assert p.get('source') == 'ibm-mq', p
print('MQ_HEALTH_PAYLOAD_PASS')
PY

# The request queue can move while payment-processing is alive. Prove equivalence
# with up to three tightly coupled MCP/runmqsc observations rather than assuming an
# idle queue forever.
MATCHED=0
MCP_DEPTH=""
MQ_DEPTH=""
for attempt in 1 2 3; do
  curl -fsSk "https://$AGENT_HOST/agent/mcp/mq/queues/PAYMENT.REQUEST.Q" \
    > "$OUT/13-request-queue-via-mcp-attempt-${attempt}.json"
  MCP_DEPTH="$(python - "$OUT/13-request-queue-via-mcp-attempt-${attempt}.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))['payload']
assert p.get('qmgr') == 'QM.MAYABANK', p
assert p.get('queue') == 'PAYMENT.REQUEST.Q', p
print(int(p['current_depth']))
PY
)"

  printf 'DISPLAY QLOCAL(PAYMENT.REQUEST.Q) CURDEPTH MAXDEPTH IPPROCS OPPROCS\nEND\n' |
    oc -n mayabank-mq-local exec -i deployment/mq -- runmqsc QM.MAYABANK \
    > "$OUT/14-request-queue-runmqsc-attempt-${attempt}.txt"
  MQ_DEPTH="$(sed -n 's/.*CURDEPTH(\([0-9][0-9]*\)).*/\1/p' \
    "$OUT/14-request-queue-runmqsc-attempt-${attempt}.txt" | head -n1)"
  [[ -n "$MQ_DEPTH" ]] || { echo "STOP: unable to parse CURDEPTH from runmqsc" >&2; exit 1; }
  if [[ "$MCP_DEPTH" == "$MQ_DEPTH" ]]; then
    MATCHED=1
    cp "$OUT/13-request-queue-via-mcp-attempt-${attempt}.json" "$OUT/13-request-queue-via-mcp.json"
    cp "$OUT/14-request-queue-runmqsc-attempt-${attempt}.txt" "$OUT/14-request-queue-runmqsc.txt"
    break
  fi
  sleep 1
done
[[ "$MATCHED" -eq 1 ]] || {
  echo "STOP: MCP and runmqsc CURDEPTH did not match after 3 observations" >&2
  exit 1
}
printf 'mcp_current_depth=%s\nrunmqsc_current_depth=%s\nMATCH=PASS\n' \
  "$MCP_DEPTH" "$MQ_DEPTH" > "$OUT/15-depth-comparison.txt"

NEG_CODE="$(curl -sk -o "$OUT/16-forbidden-queue.json" -w '%{http_code}' \
  "https://$AGENT_HOST/agent/mcp/mq/queues/SYSTEM.ADMIN.COMMAND.QUEUE")"
[[ "$NEG_CODE" == "403" ]] || {
  echo "STOP: expected explicit HTTP 403, got HTTP $NEG_CODE" >&2
  exit 1
}
python - "$OUT/16-forbidden-queue.json" <<'CHECK'
import json, sys
body = json.load(open(sys.argv[1], encoding="utf-8"))
assert body.get("detail") == "queue is not allowed", body
print("R5_FORBIDDEN_QUEUE_POLICY_PASS")
CHECK
echo "forbidden_queue_http=$NEG_CODE" > "$OUT/17-negative-tool-policy.txt"

# Network isolation proof: agent-controller is not allowed to bypass MCP and call
# the cross-namespace adapter directly. The only allowed TradeOps source is mcp-native.
set +e
oc -n tradeops exec deployment/agent-controller -- python -c \
  "import socket; s=socket.create_connection(('mq-ops-api.mayabank-mq-local.svc.cluster.local',8080),3); s.close()" \
  > "$OUT/18-direct-bypass-attempt.txt" 2>&1
BYPASS_RC=$?
set -e
if [[ "$BYPASS_RC" -eq 0 ]]; then
  echo "STOP: agent-controller bypassed MCP and reached mq-ops-api directly" >&2
  exit 1
fi
echo "DIRECT_BYPASS_DENIED=PASS rc=$BYPASS_RC" >> "$OUT/18-direct-bypass-attempt.txt"

oc -n tradeops logs deployment/mcp-native --tail=200 > "$OUT/19-mcp-native.log" 2>&1 || true
oc -n tradeops logs deployment/agent-controller --tail=200 > "$OUT/20-agent-controller.log" 2>&1 || true
oc -n mayabank-mq-local logs deployment/mq-ops-api --tail=200 > "$OUT/21-mq-ops-api.log" 2>&1 || true
oc -n mayabank-mq-local logs deployment/mq --tail=120 > "$OUT/22-mq.log" 2>&1 || true
oc adm top nodes > "$OUT/23-top-nodes.txt" 2>&1 || true
oc -n tradeops adm top pods > "$OUT/24-top-tradeops.txt" 2>&1 || true
oc -n mayabank-mq-local adm top pods > "$OUT/25-top-mayabank.txt" 2>&1 || true

cat >> "$OUT/00-summary.txt" <<EOF
mcp_request_queue_depth=$MCP_DEPTH
runmqsc_request_queue_depth=$MQ_DEPTH
depth_match=PASS
forbidden_queue_http=$NEG_CODE
direct_bypass_denied=PASS
verification=R5_CRC_MCP_MQ_VERIFY_PASS
evidence_class=LIVE_OPERATIONAL
EOF

printf '%s\n' "Evidence: $OUT"
echo "R5_CRC_MCP_MQ_VERIFY_PASS"
