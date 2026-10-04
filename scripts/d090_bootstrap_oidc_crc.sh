#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${TRADEOPS_NAMESPACE:-tradeops}"
KEYCLOAK_NAMESPACE="${KEYCLOAK_NAMESPACE:-keycloak-system}"
KEYCLOAK_URL="${KEYCLOAK_URL:-https://keycloak.apps-crc.testing}"
REALM="${SHARED_REALM:-mayabank}"
ADMIN_SECRET="${KEYCLOAK_ADMIN_SECRET:-keycloak-initial-admin}"
CLIENT_ID="${D090_CLIENT_ID:-tradeops-ai}"
AUDIENCE="${D090_AUDIENCE:-ai-gateway}"
SCOPE="${D090_SCOPE:-ai.inference}"

for cmd in oc curl jq python; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "ERROR: ${cmd} is required" >&2; exit 1; }
done

oc -n "${KEYCLOAK_NAMESPACE}" wait --for=condition=Ready keycloak/keycloak --timeout=60s >/dev/null
oc -n "${NAMESPACE}" get secret tradeops-runtime-secrets >/dev/null

ADMIN_USER="$(oc -n "${KEYCLOAK_NAMESPACE}" get secret "${ADMIN_SECRET}" -o jsonpath='{.data.username}' | base64 -d)"
ADMIN_PASSWORD="$(oc -n "${KEYCLOAK_NAMESPACE}" get secret "${ADMIN_SECRET}" -o jsonpath='{.data.password}' | base64 -d)"

ADMIN_TOKEN="$(curl -kfsS -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token"   -H 'Content-Type: application/x-www-form-urlencoded'   --data-urlencode 'client_id=admin-cli'   --data-urlencode 'grant_type=password'   --data-urlencode "username=${ADMIN_USER}"   --data-urlencode "password=${ADMIN_PASSWORD}" | jq -r '.access_token')"
test -n "${ADMIN_TOKEN}" && test "${ADMIN_TOKEN}" != "null"

admin_get() {
  curl -kfsS -H "Authorization: Bearer ${ADMIN_TOKEN}" "${KEYCLOAK_URL}$1"
}

admin_create() {
  local path="$1" data="$2" expected="${3:-201}" body code
  body="$(mktemp)"
  code="$(curl -ksS -o "${body}" -w '%{http_code}' -X POST "${KEYCLOAK_URL}${path}"     -H "Authorization: Bearer ${ADMIN_TOKEN}"     -H 'Content-Type: application/json'     --data-binary "${data}")"
  if [[ "${code}" != "${expected}" ]]; then
    echo "ERROR: Keycloak create failed: ${path}: HTTP ${code}" >&2
    cat "${body}" >&2
    rm -f "${body}"
    return 1
  fi
  rm -f "${body}"
}

ensure_client() {
  local client_id="$1" body="$2" uuid
  uuid="$(admin_get "/admin/realms/${REALM}/clients?clientId=${client_id}" | jq -r '.[0].id // empty')"
  if [[ -z "${uuid}" ]]; then
    admin_create "/admin/realms/${REALM}/clients" "${body}"
    uuid="$(admin_get "/admin/realms/${REALM}/clients?clientId=${client_id}" | jq -r '.[0].id')"
  fi
  printf '%s' "${uuid}"
}

ensure_scope() {
  local scope="$1" id
  id="$(admin_get "/admin/realms/${REALM}/client-scopes" | jq -r --arg n "${scope}" '.[] | select(.name==$n) | .id' | head -n1)"
  if [[ -z "${id}" ]]; then
    admin_create "/admin/realms/${REALM}/client-scopes"       "$(jq -nc --arg n "${scope}" '{name:$n,protocol:"openid-connect",attributes:{"include.in.token.scope":"true"}}')"
  fi
}

curl -kfsS "${KEYCLOAK_URL}/realms/${REALM}/.well-known/openid-configuration" >/dev/null
ensure_scope "${SCOPE}"

AUD_UUID="$(ensure_client "${AUDIENCE}" "$(jq -nc --arg c "${AUDIENCE}"   '{clientId:$c,enabled:true,protocol:"openid-connect",publicClient:true,standardFlowEnabled:false,directAccessGrantsEnabled:false,serviceAccountsEnabled:false}')")"

CLIENT_UUID="$(ensure_client "${CLIENT_ID}" "$(jq -nc --arg c "${CLIENT_ID}"   '{clientId:$c,enabled:true,protocol:"openid-connect",publicClient:false,serviceAccountsEnabled:true,fullScopeAllowed:false,standardFlowEnabled:false,directAccessGrantsEnabled:false}')")"

SCOPE_ID="$(admin_get "/admin/realms/${REALM}/client-scopes" | jq -r --arg n "${SCOPE}" '.[] | select(.name==$n) | .id' | head -n1)"
code="$(curl -ksS -o /tmp/d090-scope-link.out -w '%{http_code}' -X PUT   "${KEYCLOAK_URL}/admin/realms/${REALM}/clients/${CLIENT_UUID}/default-client-scopes/${SCOPE_ID}"   -H "Authorization: Bearer ${ADMIN_TOKEN}")"
[[ "${code}" == "204" || "${code}" == "409" ]] || {
  echo "ERROR: scope link failed HTTP ${code}" >&2
  cat /tmp/d090-scope-link.out >&2
  exit 1
}

MAPPER_ID="$(admin_get "/admin/realms/${REALM}/clients/${CLIENT_UUID}/protocol-mappers/models"   | jq -r --arg n "${AUDIENCE}-audience" '.[] | select(.name==$n) | .id' | head -n1)"
if [[ -z "${MAPPER_ID}" ]]; then
  admin_create "/admin/realms/${REALM}/clients/${CLIENT_UUID}/protocol-mappers/models"     "$(jq -nc --arg name "${AUDIENCE}-audience" --arg aud "${AUDIENCE}"       '{name:$name,protocol:"openid-connect",protocolMapper:"oidc-audience-mapper",config:{"included.client.audience":$aud,"access.token.claim":"true"}}')"
fi

CLIENT_SECRET="$(admin_get "/admin/realms/${REALM}/clients/${CLIENT_UUID}/client-secret" | jq -r '.value // empty')"
if [[ -z "${CLIENT_SECRET}" ]]; then
  CLIENT_SECRET="$(curl -kfsS -X POST     -H "Authorization: Bearer ${ADMIN_TOKEN}"     "${KEYCLOAK_URL}/admin/realms/${REALM}/clients/${CLIENT_UUID}/client-secret" | jq -r '.value')"
fi
test -n "${CLIENT_SECRET}" && test "${CLIENT_SECRET}" != "null"

TOKEN_RESPONSE="$(curl -kfsS -X POST "${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token"   -H 'Content-Type: application/x-www-form-urlencoded'   --data-urlencode 'grant_type=client_credentials'   --data-urlencode "client_id=${CLIENT_ID}"   --data-urlencode "client_secret=${CLIENT_SECRET}"   --data-urlencode "scope=${SCOPE}")"

TOKEN_RESPONSE="${TOKEN_RESPONSE}" CLIENT_ID="${CLIENT_ID}" AUDIENCE="${AUDIENCE}" SCOPE="${SCOPE}" REALM="${REALM}" KEYCLOAK_URL="${KEYCLOAK_URL}" python - <<'PY'
import base64, json, os
token=json.loads(os.environ["TOKEN_RESPONSE"])["access_token"]
payload=token.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims=json.loads(base64.urlsafe_b64decode(payload))
assert claims["iss"] == f'{os.environ["KEYCLOAK_URL"]}/realms/{os.environ["REALM"]}'
aud=claims.get("aud", [])
aud=[aud] if isinstance(aud,str) else aud
assert os.environ["AUDIENCE"] in aud, aud
assert os.environ["SCOPE"] in set(claims.get("scope","").split())
assert claims.get("azp") == os.environ["CLIENT_ID"]
PY

JWKS_JSON="$(curl -kfsS "${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/certs")"
POLICIES_JSON="$(python - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path("infra/ai-access/consumers.example.json").read_text())
print(json.dumps({"tradeops-ai": obj["tradeops-ai"]}, separators=(",",":")))
PY
)"

RUNTIME_LITELLM_KEY="$(oc -n "${NAMESPACE}" get secret tradeops-runtime-secrets -o jsonpath='{.data.LITELLM_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || true)"
if [[ -z "${RUNTIME_LITELLM_KEY}" ]]; then
  RUNTIME_LITELLM_KEY="$(python -c 'import secrets; print("sk-d090-"+secrets.token_urlsafe(32))')"
fi

export CLIENT_SECRET JWKS_JSON POLICIES_JSON RUNTIME_LITELLM_KEY
PATCH="$(python - <<'PY'
import base64, json, os
keys=["CLIENT_SECRET","JWKS_JSON","POLICIES_JSON","RUNTIME_LITELLM_KEY"]
mapping={
 "CLIENT_SECRET":"AI_OIDC_CLIENT_SECRET",
 "JWKS_JSON":"AI_ACCESS_OIDC_JWKS_JSON",
 "POLICIES_JSON":"AI_ACCESS_CONSUMERS_JSON",
 "RUNTIME_LITELLM_KEY":"LITELLM_API_KEY",
}
data={}
for env in keys:
    data[mapping[env]]=base64.b64encode(os.environ[env].encode()).decode()
print(json.dumps({"data":data},separators=(",",":")))
PY
)"
oc -n "${NAMESPACE}" patch secret tradeops-runtime-secrets --type=merge -p "${PATCH}" >/dev/null

unset ADMIN_TOKEN ADMIN_USER ADMIN_PASSWORD CLIENT_SECRET JWKS_JSON POLICIES_JSON RUNTIME_LITELLM_KEY TOKEN_RESPONSE PATCH
rm -f /tmp/d090-scope-link.out

echo "D090_SHARED_OIDC_CLIENT=PASS client=${CLIENT_ID}"
echo "D090_SHARED_OIDC_AUDIENCE=PASS audience=${AUDIENCE}"
echo "D090_SHARED_OIDC_SCOPE=PASS scope=${SCOPE}"
echo "D090_RUNTIME_SECRET_MERGE=PASS"
