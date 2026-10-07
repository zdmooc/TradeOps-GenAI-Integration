# D-090 G2 CRC live-governance attempt #1 — 2026-10-07

Status: **RUNTIME ATTEMPT INCOMPLETE / SAFETY CLEANUP PASS / PROMETHEUS CONFIG PATCH FIXED**

## Observed pass markers before failure

```text
D090_SHARED_OIDC_CLIENT=PASS client=tradeops-ai
D090_SHARED_OIDC_AUDIENCE=PASS audience=ai-gateway
D090_SHARED_OIDC_SCOPE=PASS scope=ai.inference
D090_RUNTIME_SECRET_MERGE=PASS
D090_G2_AUTH_MATERIAL_REFRESH=PASS
D090_G2_WINDOW_BASE_ACTIVE=PASS
D090_LITELLM_ROLLOUT=PASS
D090_LITELLM_READINESS=PASS
D090_OLLAMA_REACHABILITY=PASS
D090_LITELLM_LOCAL_MODEL_E2E=PASS model=tradeops-default
D090_LOCAL_REAL_MODEL_PRECHECK=PASS
D090_LITELLM_DEPLOY=PASS profile=local-ollama model=ollama/qwen2.5:3b
D090_GENAI_GATEWAY_MODE=PASS
D090_G2_WINDOW_ACTIVE=PASS
D090_G2_RUNTIME_TOKEN_ISSUER=http://keycloak.apps-crc.testing:8080/realms/mayabank
D090_KONG_HOT_RELOAD=PASS
D090_KONG_AI_ROUTE=PASS
D090_KONG_NO_TOKEN_DENY=PASS
D090_KONG_CONFIG_PERSIST=PASS
D090_G1A_KONG=PASS
D090_G2_AUTH_CHAIN=PASS
```

## Failure

The run stopped before baseline/quota/budget/OTel governance probes with:

```text
genai-api target anchor missing
```

Cause: the runtime ConfigMap formatting did not match an exact indentation-sensitive string used by the G2 wrapper.

This was not a Prometheus functional failure and did not invalidate G1.

## Safety cleanup

The failed run still completed:

```text
D090_G2_POLICY_RESTORE=PASS
D090_G2_WINDOW_REPARK=PASS
```

Therefore:
- the original `AI_ACCESS_CONSUMERS_JSON` policy was restored;
- `ai-access-policy`, `genai-api`, and LiteLLM were re-PARKED;
- StatefulSets were not scaled;
- Prometheus was not restarted.

## Corrective action

TradeOps PR #17 replaced the fragile string substitution with a dedicated, tested config patch helper that:
- locates the top-level `scrape_configs:` section;
- inserts a dedicated `ai-access-policy:8020` job independent of existing target formatting;
- preserves following top-level Prometheus sections;
- is idempotent;
- fails closed if `scrape_configs` is missing.

Merged commit:

```text
7d3138c267ba86dcbde53e95dd2ef66ff7888554
```

CI:

```text
37634386011 SUCCESS
```

G2 remains **CRC_RUNTIME_PENDING** until the corrected full run emits `D090_G2_GOVERNANCE=PASS`.
