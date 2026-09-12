#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/evidence/graduation/live/observability/$STAMP"
mkdir -p "$OUT"
cd "$ROOT"

log() {
  local name="$1"
  shift
  echo "==> $name"
  "$@" 2>&1 | tee "$OUT/$name.txt"
}

log 01-preflight bash scripts/i9_crc_preflight.sh
log 02-pods oc -n tradeops get pods -o wide
log 03-networkpolicies oc -n tradeops get networkpolicy

AGENT_HOST="$(oc -n tradeops get route agent-controller -o jsonpath='{.spec.host}')"
GRAFANA_HOST="$(oc -n tradeops get route grafana -o jsonpath='{.spec.host}')"
CORR="o2-${STAMP}"

curl -fsSk "https://${AGENT_HOST}/health" | tee "$OUT/04-agent-health.txt"
curl -fsSk "https://${GRAFANA_HOST}/api/health" | tee "$OUT/05-grafana-health.txt"

# Generate a real application request carrying an explicit correlation id.
curl -fsSk \
  -D "$OUT/06-assessment-headers.txt" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: ${CORR}" \
  -d '{"symbol":"O2-PROBE","event_age_ms":0,"risk_status":"UNKNOWN","rag_question":"risk architecture trading"}' \
  "https://${AGENT_HOST}/agent/assessment" \
  | tee "$OUT/07-assessment-response.json"

python - "$OUT/07-assessment-response.json" "$CORR" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = sys.argv[2]
actual = payload.get("correlation_id")
if actual != expected:
    raise SystemExit(f"correlation mismatch: expected={expected!r} actual={actual!r}")
print("O2_CORRELATION_PASS")
PY

grep -qi '^x-trace-id:' "$OUT/06-assessment-headers.txt"
echo "O2_TRACE_HEADER_PASS" | tee "$OUT/08-trace-header-check.txt"

# Prove the live identity boundary fails closed without a bearer token.
HTTP_CODE="$(curl -sSk -o "$OUT/09-unauthorized-body.json" -w '%{http_code}' \
  "https://${AGENT_HOST}/decision/o2-security-probe")"
echo "http_status=${HTTP_CODE}" | tee "$OUT/10-unauthorized-status.txt"
if [[ "$HTTP_CODE" != "401" ]]; then
  echo "O2_SECURITY_BOUNDARY_FAIL expected=401 actual=${HTTP_CODE}" >&2
  exit 1
fi
echo "O2_SECURITY_BOUNDARY_PASS" | tee -a "$OUT/10-unauthorized-status.txt"

# Give Prometheus at least one scrape interval to retain the generated evidence.
sleep 20

AGENT_POD="$(oc -n tradeops get pods -l app.kubernetes.io/name=agent-controller -o jsonpath='{.items[0].metadata.name}')"

oc -n tradeops exec "$AGENT_POD" -- python -c '
import urllib.parse, urllib.request
q = "up{job=\"tradeops-apis\"}"
url = "http://prometheus:9090/api/v1/query?" + urllib.parse.urlencode({"query": q})
print(urllib.request.urlopen(url, timeout=10).read().decode())
' | tee "$OUT/11-prometheus-up.json"

python - "$OUT/11-prometheus-up.json" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
results = payload.get("data", {}).get("result", [])
if len(results) < 6:
    raise SystemExit(f"expected at least 6 tradeops-api targets, got {len(results)}")
not_up = [item for item in results if float(item.get("value", [0, "0"])[1]) != 1.0]
if not_up:
    raise SystemExit(f"Prometheus targets not up: {not_up}")
print(f"O2_PROMETHEUS_TARGETS_PASS count={len(results)}")
PY

oc -n tradeops exec "$AGENT_POD" -- python -c '
import urllib.parse, urllib.request
q = "tradeops_security_denials_total{boundary=\"agent-controller\",reason=\"decision_read\"}"
url = "http://prometheus:9090/api/v1/query?" + urllib.parse.urlencode({"query": q})
print(urllib.request.urlopen(url, timeout=10).read().decode())
' | tee "$OUT/12-security-denial-metric.json"

python - "$OUT/12-security-denial-metric.json" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
results = payload.get("data", {}).get("result", [])
values = [float(item.get("value", [0, "0"])[1]) for item in results]
if not values or max(values) < 1:
    raise SystemExit(f"security denial metric missing or zero: {values}")
print(f"O2_SECURITY_METRIC_PASS max={max(values):g}")
PY

oc -n tradeops logs deployment/otel-collector --since=5m | tee "$OUT/13-otel-traces.txt"
if ! grep -Eqi 'Traces|Span #[0-9]+|ResourceSpans' "$OUT/13-otel-traces.txt"; then
  echo "O2_OTEL_TRACE_FAIL: no exported trace evidence found in collector logs" >&2
  exit 1
fi
echo "O2_OTEL_TRACE_PASS" | tee "$OUT/14-otel-check.txt"

oc -n tradeops get deployment agent-controller prometheus grafana otel-collector \
  -o custom-columns='NAME:.metadata.name,READY:.status.readyReplicas,AVAILABLE:.status.availableReplicas,SA:.spec.template.spec.serviceAccountName,AUTOMOUNT:.spec.template.spec.automountServiceAccountToken' \
  | tee "$OUT/15-runtime-security.txt"

{
  echo "timestamp_utc=$STAMP"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "namespace=tradeops"
  echo "agent_controller_route=https://${AGENT_HOST}"
  echo "grafana_route=https://${GRAFANA_HOST}"
  echo "correlation_id=${CORR}"
  echo "evidence_class=LIVE_OPERATIONAL"
  echo "verification=OBSERVABILITY_SECURITY_LIVE_PASS"
} > "$OUT/00-summary.txt"

# Evidence must not contain common credential material. This scans content, not Secret objects.
if grep -R -Eqi '(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|password[[:space:]]*[:=][[:space:]]*[^[:space:]]+|bearer[[:space:]]+[A-Za-z0-9._~-]{16,})' "$OUT"; then
  echo "O2_SECRET_SCAN_FAIL" >&2
  exit 1
fi
echo "O2_SECRET_SCAN_PASS" | tee "$OUT/16-secret-scan.txt"

echo "OBSERVABILITY_SECURITY_LIVE_PASS"
echo "Evidence directory: $OUT"
