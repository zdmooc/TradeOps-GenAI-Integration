# I8 — End-to-End Observability, Security and LLMOps

Iteration 8 hardens the I7 decision workflow with trace correlation, business metrics,
OIDC-compatible JWT verification, secret hygiene, dependency SBOM and executable
threat-model tests. It does **not** start the OpenShift/GitOps work assigned to I9.

## Trace architecture

The previous `services/common/otel.py` placeholder is replaced by a real OpenTelemetry
SDK layer. The runtime now supports:

- W3C `traceparent` extraction/injection;
- `X-Correlation-ID` propagation across HTTP and Kafka-compatible messages;
- `X-Trace-ID` on FastAPI responses;
- trace/span/correlation identifiers in structured log context;
- OTLP/HTTP export when `OTEL_EXPORTER_OTLP_ENDPOINT` is configured;
- explicit spans for decision fusion, deterministic risk, agent assessment, RAG calls,
  governed MCP tool calls and LLM calls;
- producer/consumer spans on the common Kafka adapter, so every service that uses the
  shared adapter inherits event-backbone trace propagation.

No prompt, RAG document text, bearer token, secret or order payload is written to span
attributes by the I8 instrumentation.

The local compose file adds OpenTelemetry Collector Contrib `0.160.0`, pinned to the
current reviewed release line at I8 implementation time. The collector accepts OTLP
HTTP/gRPC and uses the debug exporter. I8 therefore proves export compatibility; it
does not claim a production trace-storage backend.

## Prometheus and Grafana

The existing Prometheus/Grafana stack is reused rather than duplicated.

Prometheus now scrapes all HTTP APIs in the current runnable slice, including RAG,
agent-controller and MCP. I8 adds low-cardinality business metrics for:

- decision outcome and execution mode;
- failed fusion gate;
- deterministic risk outcome;
- Kafka produce/consume status and handler latency;
- LLM request outcome/latency;
- estimated input/output tokens and estimated cost;
- authentication/authorization/tool-policy denials.

The I8 Grafana dashboard covers request rate, p95 latency, decisions, gate failures,
security denials, estimated LLM tokens and deterministic risk outcomes.

Prometheus rules encode operational alert examples for sustained HTTP 5xx rate above
2%, p95 HTTP latency above 1 second, security-denial surges and repeated LLM errors.
These are demo SLO alert rules, not a production SLO certification.

## LLMOps accounting

The LLM adapter is wrapped once, so future providers inherit the same telemetry
contract. I8 records provider/model identifiers, latency, request success/failure,
estimated tokens and estimated cost.

The token count is deliberately named **estimated**. It is a portable `ceil(chars/4)`
approximation and is not represented as provider-billed usage. Cost remains zero unless
explicit per-1k estimated rates are configured. Prompt and response content are not
exported as telemetry attributes.

## Identity and RBAC

The local static bearer-token mode remains available for deterministic tests and demos.
I8 adds an optional `TRADEOPS_AUTH_MODE=oidc` mode with cryptographic RS256 JWT
verification using a pinned JWKS document. Verification requires issuer, audience,
subject, issued-at and expiry claims. Roles and scopes are mapped into a common
principal contract.

Agent-controller requires the `agent` role to propose and the `reviewer` role to
approve/execute. MCP continues to enforce tool scopes and human approval independently.

I8 calls this **OIDC-compatible JWT verification**, not production OIDC federation:
automatic discovery, remote JWKS refresh/rotation, IdP availability handling and
enterprise identity lifecycle remain deployment work.

## Secret hygiene and SBOM

The tracked `.env` file is removed. `.env` and `.env.*` are ignored except
`.env.example`. CI executes `scripts/security_audit.py`, which fails on:

- a tracked `.env`;
- PEM private-key markers;
- selected literal secret assignments outside approved example/test material.

CI also validates `security/sbom.spdx.json`. The committed SPDX 2.3 document is generated
deterministically from every exact Python requirement pin. It is a **Python dependency
SBOM**, not a container-image SBOM.

## Threat-model evidence

I8 tests prove:

- HTTP correlation ID preservation and trace ID generation;
- W3C trace context propagation through generic and Kafka headers;
- I7 fusion reuses the active correlation ID;
- OIDC JWT signature/issuer/audience/expiry and role checks fail closed;
- static local auth remains backward compatible;
- tracked-env/private-key/literal-secret checks reject unsafe fixtures;
- the SBOM matches current pinned requirements;
- I6 prompt-injection evidence remains fail closed;
- existing I6/I7 tests continue proving tool allowlist, scopes, human approval and
  duplicate-execution controls.

## Explicit non-claims

I8 does not claim:

- production IdP/OIDC discovery or JWKS rotation;
- production mTLS/service-mesh enforcement;
- a persistent distributed trace backend such as Tempo/Jaeger;
- Phoenix deployment (its ELv2 licensing remains an explicit review point);
- container image vulnerability scanning or signed image provenance;
- Kubernetes/OpenShift NetworkPolicy or Kyverno Policy-as-Code;
- OpenShift/GitOps deployment validation;
- automated real-money execution.

The cluster-specific security controls, image admission/scanning integration and
OpenShift/GitOps packaging remain I9 scope.
