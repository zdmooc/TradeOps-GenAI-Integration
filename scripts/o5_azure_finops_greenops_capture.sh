#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?required}"
: "${ARO_RESOURCE_GROUP:?required}"
: "${ARO_CLUSTER_NAME:?required}"
: "${O5_COST_START_UTC:?required, e.g. 2026-09-12T00:00:00Z}"
: "${O5_COST_END_UTC:?required, e.g. 2026-09-13T00:00:00Z}"

OUT_ROOT="${O5_AZURE_EVIDENCE_ROOT:-evidence/graduation/live/azure-finops-greenops}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUT_ROOT/$STAMP"
SCOPE_LABEL="${O5_SCOPE_LABEL:-aro-graduation-lab}"
CARBON_MONTH="${O5_CARBON_MONTH:-}"
mkdir -p "$OUT"

for cmd in az python sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Missing required command: $cmd" >&2; exit 2; }
done

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
SUB_FINGERPRINT="$(printf '%s' "$AZURE_SUBSCRIPTION_ID" | sha256sum | awk '{print substr($1,1,16)}')"
GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"

sanitize_json_file() {
  local input="$1"
  local output="$2"
  python - "$input" "$output" "$AZURE_SUBSCRIPTION_ID" "$ARO_RESOURCE_GROUP" <<'PY'
import json
import sys
from pathlib import Path

src, dst, subscription_id, resource_group = sys.argv[1:]
data = json.loads(Path(src).read_text(encoding="utf-8"))

def scrub(value):
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return value.replace(subscription_id, "<redacted-subscription>").replace(
            subscription_id.lower(), "<redacted-subscription>"
        ).replace(resource_group, "<redacted-resource-group>").replace(
            resource_group.lower(), "<redacted-resource-group>"
        )
    return value

Path(dst).write_text(json.dumps(scrub(data), indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

sanitize_text_file() {
  local input="$1"
  local output="$2"
  python - "$input" "$output" "$AZURE_SUBSCRIPTION_ID" "$ARO_RESOURCE_GROUP" <<'PY'
import sys
from pathlib import Path

src, dst, subscription_id, resource_group = sys.argv[1:]
text = Path(src).read_text(encoding="utf-8", errors="replace")
text = text.replace(subscription_id, "<redacted-subscription>")
text = text.replace(subscription_id.lower(), "<redacted-subscription>")
text = text.replace(resource_group, "<redacted-resource-group>")
text = text.replace(resource_group.lower(), "<redacted-resource-group>")
Path(dst).write_text(text, encoding="utf-8")
PY
}

cat > "$OUT/00-scope.txt" <<EOF
capture_timestamp_utc=$STAMP
git_commit=$GIT_COMMIT
evidence_class=AZURE_PROVIDER_READ_ONLY
scope_label=$SCOPE_LABEL
subscription_fingerprint=sha256:$SUB_FINGERPRINT
resource_group_redacted=true
cluster_name=$ARO_CLUSTER_NAME
cost_window_start=$O5_COST_START_UTC
cost_window_end=$O5_COST_END_UTC
carbon_month=${CARBON_MONTH:-NOT_SET}
full_resilience_finops_greenops_gate_claim=false
EOF

az resource list \
  --resource-group "$ARO_RESOURCE_GROUP" \
  --query '[].{name:name,type:type,location:location,tags:tags}' \
  -o json > "$OUT/01-resource-inventory.json"

if az aro show --resource-group "$ARO_RESOURCE_GROUP" --name "$ARO_CLUSTER_NAME" >/dev/null 2>&1; then
  az aro show \
    --resource-group "$ARO_RESOURCE_GROUP" \
    --name "$ARO_CLUSTER_NAME" \
    --query '{name:name,location:location,provisioningState:provisioningState,version:clusterProfile.version,apiVisibility:apiserverProfile.visibility,ingressVisibility:ingressProfiles[0].visibility,masterVmSize:masterProfile.vmSize,workerVmSize:workerProfiles[0].vmSize,workerCount:workerProfiles[0].count,workerDiskGB:workerProfiles[0].diskSizeGB,tags:tags}' \
    -o json > "$OUT/02-aro-state.json"
else
  printf '{"cluster":"%s","state":"ABSENT"}\n' "$ARO_CLUSTER_NAME" > "$OUT/02-aro-state.json"
fi

python - "$O5_COST_START_UTC" "$O5_COST_END_UTC" > "$OUT/10-cost-query.json" <<'PY'
import json
import sys

start, end = sys.argv[1:]
print(json.dumps({
    "type": "ActualCost",
    "timeframe": "Custom",
    "timePeriod": {"from": start, "to": end},
    "dataset": {
        "granularity": "None",
        "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
    },
}, indent=2))
PY

RAW_COST="$(mktemp)"
ERR_COST="$(mktemp)"
RAW_CARBON_RANGE="$(mktemp)"
ERR_CARBON_RANGE="$(mktemp)"
RAW_CARBON_REPORT="$(mktemp)"
ERR_CARBON_REPORT="$(mktemp)"
RAW_CARBON_QUERY="$(mktemp)"
trap 'rm -f "$RAW_COST" "$ERR_COST" "$RAW_CARBON_RANGE" "$ERR_CARBON_RANGE" "$RAW_CARBON_REPORT" "$ERR_CARBON_REPORT" "$RAW_CARBON_QUERY"' EXIT

COST_URI="https://management.azure.com/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${ARO_RESOURCE_GROUP}/providers/Microsoft.CostManagement/query?api-version=2025-03-01"
if az rest --method post --uri "$COST_URI" --body "$(cat "$OUT/10-cost-query.json")" > "$RAW_COST" 2> "$ERR_COST"; then
  sanitize_json_file "$RAW_COST" "$OUT/11-cost-actual.json"
  python - "$OUT/11-cost-actual.json" > "$OUT/12-cost-summary.txt" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
props = payload.get("properties", {})
columns = [column.get("name", "") for column in props.get("columns", [])]
rows = props.get("rows", [])
if not rows:
    print("provider_cost_status=NO_ROWS_OR_PROVIDER_LAG")
    print("provider_cost_claim=NOT_MEASURED")
else:
    row = rows[0]
    mapping = {name: row[index] if index < len(row) else None for index, name in enumerate(columns)}
    cost_key = next((name for name in columns if "cost" in name.lower()), None)
    currency_key = next((name for name in columns if "currency" in name.lower()), None)
    value = mapping.get(cost_key) if cost_key else None
    currency = mapping.get(currency_key) if currency_key else "UNKNOWN"
    print("provider_cost_status=AZURE_COST_MANAGEMENT_RESPONSE_PRESENT")
    print(f"actual_cost_value={value}")
    print(f"actual_cost_currency={currency}")
    print("provider_cost_claim=REQUIRES_REVIEW_BEFORE_GRADUATION")
PY
else
  sanitize_text_file "$ERR_COST" "$OUT/11-cost-error.txt"
  cat > "$OUT/12-cost-summary.txt" <<'EOF'
provider_cost_status=QUERY_FAILED_OR_NOT_AUTHORIZED
provider_cost_claim=NOT_MEASURED
EOF
fi

if az rest \
  --method post \
  --uri 'https://management.azure.com/providers/Microsoft.Carbon/queryCarbonEmissionDataAvailableDateRange?api-version=2025-04-01' \
  > "$RAW_CARBON_RANGE" 2> "$ERR_CARBON_RANGE"; then
  sanitize_json_file "$RAW_CARBON_RANGE" "$OUT/20-carbon-available-range.json"
  CARBON_RANGE_STATUS="AVAILABLE_RANGE_CAPTURED"
else
  sanitize_text_file "$ERR_CARBON_RANGE" "$OUT/20-carbon-range-error.txt"
  CARBON_RANGE_STATUS="RANGE_QUERY_FAILED_OR_NOT_AUTHORIZED"
fi

CARBON_REPORT_STATUS="NOT_QUERIED"
if [[ -n "$CARBON_MONTH" ]]; then
  if ! [[ "$CARBON_MONTH" =~ ^[0-9]{4}-[0-9]{2}-01$ ]]; then
    echo "O5_CARBON_MONTH must be YYYY-MM-01." >&2
    exit 2
  fi

  python - "$AZURE_SUBSCRIPTION_ID" "$ARO_RESOURCE_GROUP" "$CARBON_MONTH" > "$RAW_CARBON_QUERY" <<'PY'
import json
import sys

subscription_id, resource_group, month = sys.argv[1:]
resource_group_url = f"/subscriptions/{subscription_id}/resourcegroups/{resource_group}".lower()
print(json.dumps({
    "reportType": "ItemDetailsReport",
    "subscriptionList": [subscription_id.lower()],
    "carbonScopeList": ["Scope1", "Scope2", "Scope3"],
    "dateRange": {"start": month, "end": month},
    "categoryType": "ResourceGroup",
    "resourceGroupUrlList": [resource_group_url],
    "orderBy": "LatestMonthEmissions",
    "sortDirection": "Desc",
    "pageSize": 100,
}, indent=2))
PY
  sanitize_json_file "$RAW_CARBON_QUERY" "$OUT/21-carbon-query.sanitized.json"

  if az rest \
    --method post \
    --uri 'https://management.azure.com/providers/Microsoft.Carbon/carbonEmissionReports?api-version=2025-04-01' \
    --body "$(cat "$RAW_CARBON_QUERY")" \
    > "$RAW_CARBON_REPORT" 2> "$ERR_CARBON_REPORT"; then
    sanitize_json_file "$RAW_CARBON_REPORT" "$OUT/22-carbon-report.json"
    CARBON_REPORT_STATUS="AZURE_CARBON_RESPONSE_PRESENT_REQUIRES_REVIEW"
  else
    sanitize_text_file "$ERR_CARBON_REPORT" "$OUT/22-carbon-error.txt"
    CARBON_REPORT_STATUS="REPORT_QUERY_FAILED_OR_DATA_NOT_AVAILABLE"
  fi
else
  CARBON_REPORT_STATUS="NOT_QUERIED_SET_O5_CARBON_MONTH_WHEN_PROVIDER_MONTH_IS_AVAILABLE"
fi

if grep -R -F "$AZURE_SUBSCRIPTION_ID" "$OUT" >/dev/null 2>&1; then
  echo "Secret/privacy scan failed: raw subscription ID found in retained evidence." >&2
  exit 1
fi
if grep -R -F "$ARO_RESOURCE_GROUP" "$OUT" >/dev/null 2>&1; then
  echo "Secret/privacy scan failed: raw resource group name found in retained evidence." >&2
  exit 1
fi
printf 'O5_AZURE_EVIDENCE_REDACTION_PASS\n' > "$OUT/90-secret-scan.txt"

{
  cat "$OUT/00-scope.txt"
  cat "$OUT/12-cost-summary.txt"
  echo "carbon_available_range_status=$CARBON_RANGE_STATUS"
  echo "carbon_report_status=$CARBON_REPORT_STATUS"
  echo "carbon_provider_lag_note=previous-month emissions are provider-published later; same-day lab emissions may not yet exist in Carbon Optimization"
  echo "evidence_ready_for_manual_gate_review=true"
  echo "automatic_graduation_claim=false"
  echo "verification=O5_AZURE_FINOPS_GREENOPS_CAPTURE_COMPLETED"
} > "$OUT/99-summary.txt"

echo "O5_AZURE_FINOPS_GREENOPS_CAPTURE_COMPLETED"
echo "Evidence directory: $OUT"
cat "$OUT/99-summary.txt"
