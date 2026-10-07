# D-090 AI Access runtime profile

Status: **G1 CRC_RUNTIME_PROVEN / G2 IMPLEMENTED + CI_VALIDATED, CRC LIVE PENDING / G3-G4 PROBES PREPARED**.

Target:

```text
TradeOps or ODM
  -> Shared Keycloak/RHBK JWT
  -> Kong JWT boundary
  -> ai-access-policy
       -> verify issuer/audience/scope again
       -> derive consumer from signed azp/client_id
       -> model allowlist
       -> lab RPM/budget guard
       -> inject server-held LiteLLM key
  -> LiteLLM
  -> approved model
```

Why the small policy adapter exists:

- LiteLLM OSS is not treated as the enterprise JWT boundary in this lab;
- the consumer never receives the LiteLLM key;
- consumer identity is derived from a verified JWT, not from a client-supplied header;
- the same contract can be exercised by TradeOps and ODM before G5 decides whether to extract a dedicated platform.

The adapter's in-memory quota/budget store is intentionally **lab-only / single replica**. It is not a production distributed quota implementation.

## Required runtime inputs

- Shared Keycloak issuer/JWKS;
- audience `ai-gateway`;
- scope `ai.inference`;
- consumer policy JSON;
- server-held `LITELLM_API_KEY`;
- `LITELLM_BASE_URL`;
- LiteLLM configured with model aliases such as `tradeops-default` and `odm-extraction`;
- real provider/model credentials held by LiteLLM, never by the consumer.

## Evidence boundary

Unit/CI tests may prove contract logic without external credentials.

Do not claim `DEPLOYED × SINGLE_CONSUMER` until a real-model request is observed end-to-end.


## Real-model evidence probe

After Kong, the AI Access policy service, LiteLLM and a real provider/model are actually deployed, run:

```bash
export AI_GATEWAY_BASE_URL=https://<gateway>/ai
export AI_GATEWAY_MODEL_ALIAS=tradeops-default
export AI_OIDC_TOKEN_URL=https://<keycloak>/realms/mayabank/protocol/openid-connect/token
export AI_OIDC_CLIENT_ID=tradeops-ai
export AI_OIDC_CLIENT_SECRET=<runtime-secret>
export AI_OIDC_SCOPE=ai.inference

python scripts/d090_real_model_probe.py \
  --evidence-out evidence/d090/runtime/tradeops-real-model.json
```

The probe never writes credentials. It requires:

```text
D090_OIDC_TOKEN=PASS
D090_CONSUMER_IDENTITY=PASS consumer=tradeops
D090_PROVIDER_EVIDENCE=PASS provider=<actual>
D090_MODEL_EVIDENCE=PASS model=<actual>
D090_REAL_MODEL_PATH=PASS
```

G1 was observed passing on CRC on 2026-10-07 and is promoted to `VERIFIED × SINGLE_CONSUMER`. Evidence: `evidence/d090/20261007-g1-crc-runtime-proof.md`.


## Packaging added on 2026-10-04

Base Helm values contain `ai-access-policy`, disabled by default.

Opt-in profile:

```bash
-f infra/ai-access/values-ai-access.example.yaml
```

LiteLLM reference:
- pinned example image `ghcr.io/berriai/litellm:v1.103.0`;
- aliases `tradeops-default` and `odm-extraction`;
- provider/model/key are runtime inputs;
- no provider credential is committed.

The LiteLLM example is a lab/reference deployment. Production LiteLLM state, distributed quotas and HA require a separate ADR and evidence.

## G2 metrics

`ai-access-policy:/metrics` exposes:
- `mayabank_ai_access_requests_total`;
- `mayabank_ai_access_denials_total`;
- `mayabank_ai_access_tokens_total`;
- `mayabank_ai_access_cost_usd_total`;
- `mayabank_ai_access_upstream_duration_seconds`.

Labels use the trusted server-derived consumer where applicable.

## G3/G4 shared-consumer probe

After TradeOps and ODM credentials are provisioned against the same deployed gateway:

```bash
export AI_GATEWAY_BASE_URL=https://<gateway>/ai
export AI_OIDC_TOKEN_URL=https://<keycloak>/realms/mayabank/protocol/openid-connect/token
export AI_OIDC_CLIENT_ID=tradeops-ai
export AI_OIDC_CLIENT_SECRET=<runtime-secret>
export ODM_AI_CLIENT_ID=odm-ai
export ODM_AI_CLIENT_SECRET=<runtime-secret>

python scripts/d090_shared_isolation_probe.py \
  --evidence-out evidence/d090/runtime/shared-isolation.json
```

Required final marker:

```text
D090_SHARED_ISOLATION=PASS
```

No secret is persisted in the evidence file.
