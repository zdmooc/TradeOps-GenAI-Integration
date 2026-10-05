# D-090 G1 — CRC runtime runbook

Status: **PREPARED / LIVE PROVIDER EVIDENCE PENDING**

Canonical ownership:

```text
Shared Keycloak / realm mayabank   -> shared platform + Keycloak specialist
Canonical Kong 3.9.3              -> API Management repository
AI Access policy + LiteLLM lab     -> TradeOps until G5
Shared OTel                        -> shared platform
```

## G1-A — no provider required

From TradeOps:

```bash
bash scripts/d090_prepare_crc.sh
```

Then from `mayabank-api-management-architecture`:

```bash
bash runtime/shared-platform/scripts/enable-d090-ai-access-crc.sh
```

Expected markers include:

```text
D090_SHARED_OIDC_CLIENT=PASS
D090_RUNTIME_SECRET_MERGE=PASS
D090_RUNTIME_IMAGE_BUILD=PASS
D090_G1A_PREPARE=PASS
D090_KONG_AI_ROUTE=PASS
D090_KONG_NO_TOKEN_DENY=PASS
```

## G1-B — real provider

The provider/model is deliberately a runtime choice, not committed configuration.

```bash
# Default path: OpenAI through LiteLLM.
export OPENAI_API_KEY='<runtime secret>'
# Optional override; default is openai/gpt-5.6-terra.
export D090_LITELLM_MODEL='openai/gpt-5.6-terra'

bash scripts/d090_deploy_litellm_crc.sh
unset OPENAI_API_KEY D090_PROVIDER_API_KEY

bash scripts/d090_enable_genai_crc.sh
bash scripts/d090_run_g1_live_crc.sh
```

Only `D090_REAL_MODEL_PATH=PASS` plus retained no-secret evidence can promote G1.

## Rollback

To return GenAI to deterministic offline mode:

```bash
oc -n tradeops set env deploy/genai-api LLM_PROVIDER=mock
oc -n tradeops rollout status deploy/genai-api --timeout=300s
```

The D-090 AI Access/LiteLLM lab may then be scaled down without changing the existing Payment API route.
