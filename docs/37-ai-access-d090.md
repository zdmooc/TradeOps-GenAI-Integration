# D-090 G0 — TradeOps AI Access decision

**Status:** G0 DESIGN CLOSED / G1 IMPLEMENTATION NEXT  
**Date:** 2026-10-03

## Decision

```text
TradeOps genai-api
  -> Shared Keycloak/RHBK client_credentials
  -> JWT
  -> Kong
       -> validate issuer/audience/scope
       -> derive consumer identity server-side
  -> LiteLLM (DEDICATED_FOR_TEST until G5)
       -> model alias / allowlist / quota / budget
  -> real model
  -> Shared OTel
```

Kong is the deterministic AuthN/AuthZ boundary. LiteLLM is the executable AI routing candidate for the lab. TradeOps owns the temporary integration until G5; this is not an independent enterprise AI platform claim.

## G1 acceptance criteria

- `MockLLM` remains available for deterministic/offline tests.
- non-mock mode must perform an OpenAI-compatible gateway request.
- client code must not send authoritative consumer identity headers.
- the response-reported model is captured and used in telemetry.
- configured model/provider values alone are never treated as execution evidence.
- provider/gateway errors fail explicitly; no silent fallback to mock.
- credentials are injected from environment/Secret references only.
- unit tests use a fake gateway and require no external API key.

## G2 acceptance criteria

- workload token can be acquired with OAuth2 client credentials;
- wrong/missing auth, audience/scope/model and quota conditions have deterministic negative tests/contracts;
- model alias allowlist is enforced as defense in depth;
- OTel captures requested alias, executed model, authenticated gateway consumer when available, latency and token/cost metadata with explicit estimated-vs-provider usage distinction.

## G3/G4 boundary

ODM must consume the same gateway contract with a distinct workload identity. Cross-consumer tests must prove policy/isolation before any `MULTI_TENANT_PROVEN` claim.

## Temporary debt

From G3 through G4, AI Access is hosted by TradeOps. Exit gate G5 decides whether to keep it there, extract a small specialized capability or move to a managed gateway.
