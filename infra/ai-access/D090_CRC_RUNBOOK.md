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

## G1-B — real model

The model/provider is deliberately a runtime choice, not committed configuration.

### Free local profile — Ollama on the Windows CRC host

Preferred no-cost proof path for the current local lab:

```bash
export D090_LITELLM_PROFILE=local-ollama
export D090_LITELLM_MODEL='ollama/qwen2.5:3b'
export D090_LITELLM_API_BASE='http://host.crc.testing:11434'

bash scripts/d090_deploy_litellm_crc.sh
bash scripts/d090_enable_genai_crc.sh
bash scripts/d090_run_g1_live_crc.sh
```

The deploy script:
- resolves `host.crc.testing` from inside CRC with Python/socket;
- renders `allow-litellm-to-local-ollama` with exactly one resolved IPv4 `/32`;
- opens only TCP/11434 and only for the `litellm` pod selector;
- does not require or persist a provider credential;
- removes any stale `LITELLM_PROVIDER_API_KEY` from the TradeOps runtime secret;
- verifies Ollama `/api/tags` from the LiteLLM pod;
- executes a real `tradeops-default` chat completion through LiteLLM.

Do **not** assume a fixed host IP in Git.

First try with Ollama's current bind configuration. If `D090_OLLAMA_REACHABILITY=FAIL`, configure Windows Ollama with `OLLAMA_HOST=0.0.0.0:11434`, restart Ollama, and create a Windows Firewall inbound rule limited to TCP/11434 from the CRC virtual network only. Never open 11434 to Any for this lab.

Successful local proof is classified as:

```text
G1 = DEPLOYED × SINGLE_CONSUMER
claim = LOCAL_REAL_MODEL_PROVEN
runtime = CRC single-node
model = Ollama / qwen2.5:3b
```

It is not an external-provider, cloud, HA or production claim.

### Hosted provider profile

The hosted path remains supported:

```bash
# Default path: OpenAI through LiteLLM.
export OPENAI_API_KEY='<runtime secret>'
# Optional override; default is openai/gpt-6-luna.
export D090_LITELLM_MODEL='openai/gpt-6-luna'

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
