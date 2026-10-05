# D-090 G1-A — CRC closure

**Date:** 2026-10-05  
**Status:** RUNTIME_PROVEN / PRE-PROVIDER

Observed on the single-node CRC lab:

```text
D090_SHARED_OIDC_CLIENT=PASS client=tradeops-ai
D090_SHARED_OIDC_AUDIENCE=PASS audience=ai-gateway
D090_SHARED_OIDC_SCOPE=PASS scope=ai.inference
D090_RUNTIME_SECRET_MERGE=PASS
D090_RUNTIME_IMAGE_BUILD=PASS
D090_G1A_PREPARE=PASS

D090_KONG_ADMIN_PORT_FORWARD=PASS
D090_KONG_HOT_RELOAD=PASS
D090_KONG_AI_ROUTE=PASS
D090_KONG_NO_TOKEN_DENY=PASS
D090_KONG_CONFIG_PERSIST=PASS
D090_G1A_KONG=PASS
```

Post-check workloads:

```text
mayabank-api/api-gateway   1/1 Running
tradeops/ai-access-policy  1/1 Running
```

Claim boundary:
- G1-A is runtime-proven on CRC;
- G1 is not closed until LiteLLM executes a real provider/model and `D090_REAL_MODEL_PATH=PASS` is captured;
- no HA/production claim is implied.
