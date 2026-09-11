# ADR-006 — Agent framework and governed tool boundary

Date: 2026-09-11
Status: ACCEPTED FOR I6

## Context

The pre-I6 `agent_controller` described itself as "LangGraph-style" but used a hand-written sequential loop and a heuristic confidence score. It could reach `APPROVE` and then call a paper-order tool. The pre-I6 tool server exposed an internal registry without server-side identity, scope authorization, strict argument validation, rate limiting, timeouts, or an explicit human-approval gate.

I6 needs a real agent framework for orchestration while preserving the program's separation between deterministic calculations, ML evidence, and agentic reasoning.

## Decision

Use **LangGraph 1.2.11** as the I6 orchestration framework.

Reasons:
- explicit state graph semantics fit specialist-agent orchestration;
- graph execution is testable without requiring an LLM provider;
- deterministic I1-I5 capabilities remain outside the agent layer;
- the graph can later be extended with I7 approval/fusion nodes without granting execution authority in I6.

Microsoft Agent Framework remains an evaluated alternative. On 2026-09-11 its Python package line is 1.18.0 and declares Production/Stable. It is not added to the runtime in I6 to avoid introducing two competing agent frameworks.

## MCP / tool boundary decision

The existing `/call` compatibility boundary is retained for I6 but hardened with:
- server-side bearer-token identity mapping;
- server-assigned scopes;
- explicit tool allowlist;
- strict argument validation and rejection of unknown fields;
- per-principal/tool rate limiting;
- execution timeout;
- audit redaction;
- separate agent and reviewer identities;
- `paper.execute` absent from the general-agent identity;
- explicit human approval required for the paper-order tool.

The official MCP Python SDK v2 was reviewed. The current stable line implements the 2026-07-28 protocol revision. I6 does **not** claim protocol-conformance testing or a native Streamable HTTP MCP deployment. A future migration must preserve the same authorization context and must not create a second ungoverned path around the I6 policy layer.

## Safety boundary

I6 is `ANALYSIS_ONLY`.

The specialist graph emits evidence states and directional assessment only. It never emits order execution permission. A deterministic I3 risk VETO is terminal. Human approval and executable decision fusion belong to I7.

## Consequences

Positive:
- real LangGraph execution replaces a "style" claim;
- disagreement and stale-data behavior are first-class;
- policy enforcement is testable independently of LLMs and databases;
- order capability is separated from the general agent.

Trade-offs:
- the graph is sequential in I6; parallel specialist execution is deferred;
- the RAG gate validates returned evidence but does not yet provide cryptographic document provenance;
- the compatibility tool API is not represented as MCP protocol conformance.
