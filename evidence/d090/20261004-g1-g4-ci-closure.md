# D-090 / D-092 — CI implementation closure — 2026-10-04

Status: **TESTED IN CI / LIVE RUNTIME EVIDENCE STILL REQUIRED**

## Authoritative CI

GitHub Actions run:

```text
37219490666
head: 28e0550e40ed358c0ee5d26442b2233b0a4357d7
conclusion: SUCCESS
```

Observed gates:

```text
SECURITY_AUDIT_PASS
SBOM_CHECK_PASS
D090_AI_ACCESS_VALIDATION_PASS
D092_A2A_VALIDATION_PASS
278 passed, 70 warnings
```

The successful workflow also completed:

- Ruff;
- frontend build;
- Helm lint;
- base Helm render;
- D-090 AI Access overlay render;
- D-092 A2A overlay render;
- I9/I10/I13 validators;
- Terraform fmt/init/validate;
- I11/I12 validators.

## Evidence status

### G1 — governed real-model path

**IMPLEMENTED + TESTED IN CI + PACKAGED**

Present:
- `GatewayLLM`;
- OAuth2 client-credentials provider;
- AI Access policy boundary;
- server-derived consumer identity;
- Kong target template;
- LiteLLM v1.103.0 pinned lab deployment/config example;
- Helm opt-in profile;
- real-model evidence probe.

Not yet proven:
- a real provider/model executed through the deployed chain.

Therefore G1 is not promoted to `DEPLOYED × SINGLE_CONSUMER`.

### G2 — governance

**IMPLEMENTED + TESTED IN CI**

Tested/validated:
- issuer/audience/signature/scope;
- consumer identity mapping;
- model allowlist;
- quota;
- budget;
- missing token / wrong audience / wrong scope / unknown consumer / forbidden model;
- consumer/token/cost/denial/upstream-duration metrics.

Not yet proven:
- live policy/telemetry using an actual provider request.

### D-092 A2A executable baseline

**IMPLEMENTED + TESTED IN CI**

Present:
- `a2a-sdk==1.2.1`;
- Payment Operations Agent;
- Agent Card;
- bounded skills;
- allowed peer and denied rogue peer;
- denied unauthorized skill;
- downstream native MCP provider seam;
- Helm packaging.

Not yet proven:
- authenticated live Agent A -> Agent B interoperability;
- live A2A -> native MCP trace.

### Native MCP

- R1-R4: **IMPLEMENTED + TESTED IN CI**.
- R5 `native MCP -> IBM MQ` live CRC: **PENDING**.

The expected marker in the R5 script/document is not itself evidence. A real local evidence bundle must exist before promotion.

### G3 — ODM second consumer

ODM contract already exists and has historical green CI:

```text
run 37104467767
7 passed
```

A real same-gateway ODM request remains pending.

### G4 — isolation

Policy/tests and `scripts/d090_shared_isolation_probe.py` are prepared.

Live proof still requires:
- TradeOps positive request;
- ODM positive request;
- TradeOps -> ODM model denied;
- ODM -> TradeOps model denied;
- same deployed gateway;
- distinct trusted consumer identities.

No `MULTI_TENANT_PROVEN` claim is made.

## Next runtime evidence gate

```text
TradeOps
 -> Shared Identity
 -> Kong
 -> AI Access policy
 -> LiteLLM
 -> real provider/model
```

Run `scripts/d090_real_model_probe.py` with real runtime credentials and retain the generated no-secret evidence.

## Truth boundary

CI proves code, contracts, tests and renderability.

CI does **not** prove:
- live provider/model execution;
- CRC deployment of this D-090 profile;
- authenticated live A2A interoperability;
- G3 `VERIFIED × SHARED`;
- G4 `VERIFIED × MULTI_TENANT_PROVEN`;
- production/HA.
