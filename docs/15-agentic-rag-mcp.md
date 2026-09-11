# I6 — Governed RAG, specialist agents and secure tool boundary

## Scope

Iteration 6 adds the agentic layer only after the deterministic and ML foundations from I1-I5.

The specialist agents are:
- Market Agent;
- Technical Agent;
- Pattern Agent;
- Macro Agent;
- Risk Agent;
- Fusion Agent.

They consume evidence; they do not calculate indicators, detect patterns, size positions, or override hard risk.

## Explicit states

Every specialist finding uses one of:
- `SUPPORTED`;
- `UNKNOWN`;
- `DATA_STALE`;
- `CONFLICT`;
- `VETO`.

Fusion precedence is fail-closed:
1. deterministic risk `VETO`;
2. `DATA_STALE`;
3. explicit specialist/RAG `CONFLICT`;
4. opposing LONG/SHORT evidence;
5. insufficient evidence -> `UNKNOWN`;
6. aligned evidence + deterministic risk ACCEPT -> `SUPPORTED`.

`SUPPORTED` is still analysis-only. It is not an order approval.

## LangGraph

`services/agent_controller/graph.py` now uses a real `StateGraph` from LangGraph. The graph executes:

`START -> Market -> Technical -> Pattern -> Macro -> Risk -> Fusion -> END`

The graph is intentionally deterministic for I6. No LLM is needed to test disagreement handling.

## RAG governance

The existing Qdrant-backed RAG service remains the retrieval service. Before a returned passage enters agent context, `rag_governance.py` checks:
- approved `.md` / `.txt` source type;
- score range and minimum relevance threshold;
- non-empty bounded text;
- prompt-injection markers.

Unsafe retrieved instructions produce `CONFLICT`; no acceptable evidence produces `UNKNOWN`.

The versioned I6 corpus contains strategy governance, deterministic risk policy, stale-data runbook, agent boundary, and evidence-lineage material.

## Governed tools

The tool boundary maps bearer tokens to server-side principals. Callers do not submit arbitrary scopes.

General agent scopes:
- `market.read`;
- `risk.evaluate`;
- `workflow.read`.

Human reviewer scopes additionally include:
- `audit.read`;
- `paper.execute`.

`oms.place_order` additionally requires `human_approved=true`. The general agent therefore cannot obtain paper execution merely by constructing different request arguments.

The boundary also rejects unknown tools/arguments, validates enums/types, rate-limits calls, applies execution timeouts, and redacts secret-like fields from audit payloads.

## Non-goals

I6 does not implement:
- I7 executable fusion or HITL workflow;
- automated real-money execution;
- LLM majority voting;
- probability claims beyond the I5 qualification status;
- protocol-conformance certification for the MCP compatibility API;
- full prompt-injection defense for arbitrary untrusted external documents.

## Demonstration

`data/agentic/i6_disagreement_scenarios.json` contains synthetic policy scenarios for:
- aligned LONG evidence;
- technical/pattern disagreement;
- stale market data;
- deterministic risk veto.

These scenarios validate policy mechanics only.
