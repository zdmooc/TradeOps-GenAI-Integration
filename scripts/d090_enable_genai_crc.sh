#!/usr/bin/env bash
set -euo pipefail

oc -n tradeops wait --for=condition=Available deploy/ai-access-policy --timeout=120s >/dev/null
oc -n tradeops wait --for=condition=Available deploy/litellm --timeout=120s >/dev/null
oc -n mayabank-api wait --for=condition=Available deploy/api-gateway --timeout=120s >/dev/null
oc -n shared-observability wait --for=condition=Available deploy/otel-collector --timeout=120s >/dev/null

oc -n tradeops set env deploy/genai-api   LLM_PROVIDER=gateway   AI_GATEWAY_BASE_URL=http://api-gateway.mayabank-api.svc:8000/ai   AI_GATEWAY_MODEL_ALIAS=tradeops-default   AI_GATEWAY_AUTH_MODE=client_credentials   AI_ALLOWED_MODEL_ALIASES=tradeops-default   AI_OIDC_TOKEN_URL=http://keycloak-service.keycloak-system.svc:8080/realms/mayabank/protocol/openid-connect/token   AI_OIDC_CLIENT_ID=tradeops-ai   AI_OIDC_SCOPE=ai.inference   AI_OIDC_AUDIENCE=ai-gateway   AI_GATEWAY_TIMEOUT_SECONDS=120   OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.shared-observability.svc:4318 >/dev/null

oc -n tradeops patch deploy genai-api --type=strategic -p '{
  "spec":{"template":{"spec":{"containers":[{
    "name":"genai-api",
    "env":[{
      "name":"AI_OIDC_CLIENT_SECRET",
      "valueFrom":{"secretKeyRef":{"name":"tradeops-runtime-secrets","key":"AI_OIDC_CLIENT_SECRET"}}
    }]
  }]}}}
}' >/dev/null

oc -n tradeops rollout status deploy/genai-api --timeout=300s

oc -n tradeops exec -i deploy/genai-api -- python - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8013/health", timeout=10) as r:
    payload=json.load(r)
assert payload["llm_provider"] == "gateway", payload
print("D090_GENAI_GATEWAY_MODE=PASS")
PY
