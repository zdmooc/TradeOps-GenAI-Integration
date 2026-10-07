#!/usr/bin/env bash
set -euo pipefail

PREFERRED="${D090_PREFERRED_API_BASE:-${D090_LITELLM_API_BASE:-}}"
PORT="${D090_OLLAMA_PORT:-11434}"
NODE="${D090_CRC_NODE:-$(oc get nodes -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)}"

for cmd in oc curl python; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "D090_OLLAMA_DISCOVERY=FAIL missing=$cmd" >&2
    exit 2
  }
done

if [[ -z "$NODE" ]]; then
  echo "D090_OLLAMA_DISCOVERY=FAIL no_crc_node" >&2
  exit 2
fi

normalize_base() {
  local raw="$1"
  [[ -n "$raw" ]] || return 1
  python - "$raw" "$PORT" <<'PY'
import sys, urllib.parse
raw=sys.argv[1].strip()
port=int(sys.argv[2])
if "://" not in raw:
    raw=f"http://{raw}"
u=urllib.parse.urlparse(raw)
if u.scheme != "http" or not u.hostname:
    raise SystemExit(1)
if u.port not in (None, port):
    raise SystemExit(1)
print(f"http://{u.hostname}:{port}")
PY
}

valid_ollama_json() {
  python -c 'import json,sys
try:
    obj=json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if isinstance(obj.get("models"), list) else 1)'
}

host_responds() {
  local base="$1"
  curl -fsS --connect-timeout 2 --max-time 4 "$base/api/tags" 2>/dev/null | valid_ollama_json
}

crc_node_responds() {
  local base="$1"
  local out
  out="$(
    oc debug "node/$NODE" --       chroot /host curl -fsS --connect-timeout 2 --max-time 5 "$base/api/tags"       2>/dev/null || true
  )"
  printf '%s' "$out" | grep -q '"models"'
}

declare -a candidates=()

add_candidate() {
  local raw="$1" normalized=""
  normalized="$(normalize_base "$raw" 2>/dev/null || true)"
  [[ -n "$normalized" ]] || return 0
  local existing
  for existing in "${candidates[@]:-}"; do
    [[ "$existing" == "$normalized" ]] && return 0
  done
  candidates+=("$normalized")
}

add_candidate "$PREFERRED"

# Discover host IPv4 addresses without encoding any workstation-specific IP in Git.
if command -v powershell.exe >/dev/null 2>&1; then
  while IFS= read -r ip; do
    ip="${ip//$'\r'/}"
    [[ -n "$ip" ]] && add_candidate "http://$ip:$PORT"
  done < <(
    powershell.exe -NoProfile -Command       'Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Sort-Object @{Expression={if ($_.InterfaceAlias -match "Virtual|vEthernet|Hyper-V|VMware") {0} else {1}}},InterfaceMetric | Select-Object -ExpandProperty IPAddress'       2>/dev/null || true
  )
elif command -v ipconfig.exe >/dev/null 2>&1; then
  while IFS= read -r ip; do
    add_candidate "http://$ip:$PORT"
  done < <(ipconfig.exe 2>/dev/null | tr -d '\r' | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' || true)
fi

if (( ${#candidates[@]} == 0 )); then
  echo "D090_OLLAMA_DISCOVERY=FAIL no_candidates" >&2
  exit 3
fi

echo "D090_OLLAMA_DISCOVERY_CANDIDATES=${#candidates[@]}" >&2

for base in "${candidates[@]}"; do
  if ! host_responds "$base"; then
    echo "D090_OLLAMA_ENDPOINT_REJECTED=$base reason=host_api_unreachable" >&2
    continue
  fi
  echo "D090_OLLAMA_HOST_API=PASS base=$base" >&2

  if ! crc_node_responds "$base"; then
    echo "D090_OLLAMA_ENDPOINT_REJECTED=$base reason=crc_node_unreachable" >&2
    continue
  fi

  echo "D090_OLLAMA_CRC_NODE_REACHABILITY=PASS base=$base" >&2
  echo "D090_OLLAMA_ENDPOINT_SELECTED=$base" >&2
  printf '%s\n' "$base"
  exit 0
done

echo "D090_OLLAMA_DISCOVERY=FAIL no_endpoint_reachable_from_crc" >&2
echo "action=ensure Ollama listens on a Windows IPv4 interface reachable from CRC and restrict TCP/$PORT with Windows Firewall" >&2
exit 4
