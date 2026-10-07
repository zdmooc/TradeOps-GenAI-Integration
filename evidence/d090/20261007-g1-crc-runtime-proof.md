# D-090 G1 full governed CRC runtime proof — 2026-10-07

Status: **CRC_RUNTIME_PROVEN / SINGLE-CONSUMER GOVERNED REAL-MODEL PATH**

Environment: OpenShift Local / CRC single-node lab.

## Observed full path

```text
TradeOps genai-api
 -> Shared Keycloak
 -> canonical Kong
 -> AI Access policy
 -> LiteLLM
 -> Ollama/qwen2.5:3b
```

## Runtime markers

```text
D090_SHARED_OIDC_CLIENT=PASS client=tradeops-ai
D090_SHARED_OIDC_AUDIENCE=PASS audience=ai-gateway
D090_SHARED_OIDC_SCOPE=PASS scope=ai.inference
D090_RUNTIME_SECRET_MERGE=PASS
D090_G1_AUTH_MATERIAL_REFRESH=PASS

D090_G1_WINDOW_BASE_ACTIVE=PASS
D090_OLLAMA_HOST_RESOLUTION=PASS host=192.168.56.1 cidr=192.168.56.1/32
D090_OLLAMA_NETWORKPOLICY=PASS cidr=192.168.56.1/32 port=11434
D090_LITELLM_ROLLOUT=PASS
D090_LITELLM_READINESS=PASS
D090_OLLAMA_REACHABILITY=PASS
D090_LITELLM_LOCAL_MODEL_E2E=PASS model=tradeops-default
D090_LOCAL_REAL_MODEL_PRECHECK=PASS
D090_LITELLM_DEPLOY=PASS profile=local-ollama model=ollama/qwen2.5:3b
D090_G1_WINDOW_ACTIVE=PASS

D090_GENAI_GATEWAY_MODE=PASS
D090_RUNTIME_TOKEN_ISSUER=http://keycloak.apps-crc.testing:8080/realms/mayabank
D090_POLICY_ISSUER_ALIGN=PASS issuer=http://keycloak.apps-crc.testing:8080/realms/mayabank
D090_KONG_HOT_RELOAD=PASS
D090_KONG_AI_ROUTE=PASS
D090_KONG_NO_TOKEN_DENY=PASS
D090_KONG_CONFIG_PERSIST=PASS
D090_G1A_KONG=PASS
D090_G1_KONG_JWT_REFRESH=PASS issuer=http://keycloak.apps-crc.testing:8080/realms/mayabank

D090_OIDC_TOKEN=PASS
D090_CONSUMER_IDENTITY=PASS consumer=tradeops
D090_PROVIDER_EVIDENCE=PASS provider=litellm
D090_MODEL_EVIDENCE=PASS model=tradeops-default
D090_REAL_MODEL_PATH=PASS
D090_EVIDENCE_WRITTEN=/tmp/d090-real-model.json
D090_G1_CLAIM=LOCAL_REAL_MODEL_PROVEN
D090_G1_LIVE=PASS
D090_EVIDENCE_DIR=evidence/out/d090-20261007T130759Z
D090_G1_FROM_PARK=PASS
D090_G1_WINDOW_REPARK=PASS
```

## Telemetry boundary

The same run emitted:

```text
D090_SHARED_OTEL_TRACE=PENDING_NOT_OBSERVED
```

This does **not** invalidate G1. G1 acceptance is the governed real-model path. Shared OTel observation is carried forward to D-090 G2 live governance together with quota/budget/denial metrics.

## Issuer reconciliation learned from CRC

The workload token issuer observed from inside `genai-api` was:

```text
http://keycloak.apps-crc.testing:8080/realms/mayabank
```

The bounded CRC workflow now aligns both:
- `ai-access-policy OIDC_ISSUER`;
- Kong JWT credential key;

to that observed runtime issuer.

This is a CRC/local reconciliation mechanism. Production still requires a stable canonical issuer URI through correct Keycloak hostname/proxy configuration.

## Claim boundary

Allowed:

```text
D090_G1_CRC_RUNTIME_PROVEN
D090_G1_SINGLE_CONSUMER_GOVERNED_REAL_MODEL_PROVEN
```

Not implied:
- G2 live governance closure;
- distributed quota/budget;
- multi-consumer isolation;
- G3 ODM live shared-gateway proof;
- G4 multi-tenant isolation;
- production or HA readiness.

Next gate: **D-090 G2 live governance**.
