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

Preferred no-cost proof path for the current local lab.

When TradeOps is still PARKED after the T1/T2 capacity gate, use the bounded G1 window instead of resuming the full product:

```bash
export D090_LITELLM_API_BASE='http://192.168.56.1:11434'
bash scripts/crc/d090-g1-live-from-park.sh
```

The wrapper:
- requires the existing PARK snapshot;
- restores only `ai-access-policy` and `genai-api` from their snapshotted replica counts;
- lets the canonical LiteLLM deployment script activate LiteLLM;
- runs `d090_deploy_litellm_crc.sh`, `d090_enable_genai_crc.sh` and `d090_run_g1_live_crc.sh`;
- automatically scales `ai-access-policy`, `genai-api` and `litellm` back to zero on success or failure;
- never scales StatefulSets;
- leaves the rest of TradeOps PARKED.

Expected success markers include:

```text
D090_G1_WINDOW_BASE_ACTIVE=PASS
D090_LOCAL_REAL_MODEL_PRECHECK=PASS
D090_REAL_MODEL_PATH=PASS
D090_G1_LIVE=PASS
D090_G1_FROM_PARK=PASS
D090_G1_WINDOW_REPARK=PASS
```

The lower-level commands remain available when a full manual investigation is needed:

```bash
export D090_LITELLM_PROFILE=local-ollama
export D090_LITELLM_MODEL='ollama/qwen2.5:3b'
# Current HP ZBook / CRC Windows observation:
# 192.168.56.1 (host-only adapter) is reachable from the CRC node.
export D090_LITELLM_API_BASE='http://192.168.56.1:11434'

bash scripts/d090_deploy_litellm_crc.sh
bash scripts/d090_enable_genai_crc.sh
bash scripts/d090_run_g1_live_crc.sh
```

The deploy script:
- requires an explicit local Ollama `api_base` and resolves/validates its IPv4 from inside CRC;
- renders `allow-litellm-to-local-ollama` with exactly one resolved IPv4 `/32`;
- opens only TCP/11434 and only for the `litellm` pod selector;
- does not require or persist a provider credential;
- removes any stale `LITELLM_PROVIDER_API_KEY` from the TradeOps runtime secret;
- verifies Ollama `/api/tags` from the LiteLLM pod;
- executes a real `tradeops-default` chat completion through LiteLLM.

Do **not** encode a workstation-specific IP as a platform-wide default in Git.

Observed on the current Windows workstation on 2026-10-05:
- `host.crc.testing -> 192.168.127.254` timed out from the LiteLLM pod even with `host-network-access=true`;
- CRC node debug successfully reached Ollama on `192.168.56.1`, `172.20.240.1`, and `192.168.1.37`;
- `192.168.56.1` is preferred for this workstation because it is an internal host-only adapter and avoids exposing Ollama on the LAN address.

For this workstation, bind Ollama to `192.168.56.1:11434` and use the same address as `D090_LITELLM_API_BASE`. The generated OpenShift egress policy will then be narrowed to `192.168.56.1/32:11434`.

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


## PRECHECK RUNTIME PROOF — 2026-10-05

Observed on the current CRC/Windows workstation:

```text
D090_OLLAMA_HOST_RESOLUTION=PASS host=192.168.56.1 cidr=192.168.56.1/32
D090_OLLAMA_NETWORKPOLICY=PASS cidr=192.168.56.1/32 port=11434
D090_LITELLM_ROLLOUT=PASS
D090_LITELLM_READINESS=PASS
D090_OLLAMA_REACHABILITY=PASS
D090_LITELLM_LOCAL_MODEL_E2E=PASS model=tradeops-default
D090_LOCAL_REAL_MODEL_PRECHECK=PASS
D090_LITELLM_DEPLOY=PASS profile=local-ollama model=ollama/qwen2.5:3b
```

Classification:
`LiteLLM -> local Ollama/qwen2.5:3b` = **RUNTIME_PROVEN on single-node CRC**.

This does **not** close G1 yet. G1 closes only after the full governed
`genai-api -> Shared Keycloak -> canonical Kong -> AI Access -> LiteLLM -> Ollama`
probe emits `D090_REAL_MODEL_PATH=PASS` and `D090_G1_LIVE=PASS`.
