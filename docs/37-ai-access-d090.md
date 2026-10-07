# D-090 G0 — TradeOps AI Access decision

**Status:** G0 CLOSED / G1 CRC_RUNTIME_PROVEN / G2 IMPLEMENTED + CI_VALIDATED / LIVE GOVERNANCE PENDING  
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


## 2026-10-04 implementation update

### G1 implementation/package

Implemented:
- `GatewayLLM` OpenAI-compatible non-mock path;
- OAuth2 client-credentials token provider;
- server-derived consumer identity;
- AI Access policy service;
- Kong target template;
- LiteLLM v1.103.0 pinned deployment/config example;
- Helm workloads for `ai-access-policy` (disabled by default);
- opt-in `values-ai-access.example.yaml`;
- real-model probe `scripts/d090_real_model_probe.py`;
- static validator `scripts/d090_validate_ai_access.py`.

The default remains `LLM_PROVIDER=mock`. The real path is never silently enabled.

### G2 governance implementation

Implemented in the policy boundary:
- issuer/audience/signature validation;
- required `ai.inference` scope;
- trusted `azp/client_id -> consumer` mapping;
- per-consumer model allowlist;
- per-consumer RPM quota;
- lab budget/cost accounting;
- missing token / wrong audience / wrong scope / unknown consumer / forbidden model / quota / budget negative cases;
- Prometheus metrics for request outcome, denials, tokens, estimated cost and upstream duration.

The in-memory RPM/budget store remains **single-replica lab-only**.

### G3/G4 prepared evidence

`scripts/d090_shared_isolation_probe.py` is the live gate for:
- TradeOps identity -> `tradeops-default`;
- ODM identity -> `odm-extraction`;
- TradeOps -> ODM model denial;
- ODM -> TradeOps model denial;
- same deployed gateway for both consumers.

Unit/policy tests are not enough to promote `VERIFIED × SHARED` or `MULTI_TENANT_PROVEN`.

### Current proof boundary

```text
G0 = CLOSED / DESIGNED
G1 = CRC_RUNTIME_PROVEN / VERIFIED × SINGLE_CONSUMER
G2 = IMPLEMENTED + CI_VALIDATED / LIVE GOVERNANCE EVIDENCE PENDING
G3 = SECOND-CONSUMER CONTRACT + PROBE PREPARED / LIVE SHARED EVIDENCE PENDING
G4 = ISOLATION POLICY + PROBE PREPARED / LIVE MULTI-TENANT EVIDENCE PENDING
```


## 2026-10-07 G1 closure / G2 runtime gate

G1 is now runtime-proven on CRC through the full governed path:
`genai-api -> Shared Keycloak -> canonical Kong -> AI Access -> LiteLLM -> Ollama/qwen2.5:3b`.

Canonical evidence: `evidence/d090/20261007-g1-crc-runtime-proof.md`.

G2 live tooling is merged and CI-validated:
- bounded PARK-aware window;
- model denial;
- live RPM quota;
- live budget denial;
- AI Access metrics;
- Prometheus `ai-access-policy:8020` scrape target + PromQL proof;
- real `genai-api /review` path through `ObservedLLM`;
- Shared OTel collector receipt;
- policy restore + automatic re-PARK.

Runtime script: `scripts/crc/d090-g2-live-governance-from-park.sh`.

G2 remains **LIVE GOVERNANCE EVIDENCE PENDING** until that script passes on CRC.
