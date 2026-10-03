# D-090 AI Access runtime profile

Status: **IMPLEMENTED CONTRACT / REAL MODEL + CRC EVIDENCE PENDING**.

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
