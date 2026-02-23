# Agentic AI Architecture

## Overview

The TradeOps platform now integrates an **Enterprise AI Agent** layer that automates trade evaluation and execution through a structured, auditable pipeline. The architecture follows three complementary paradigms: **LLM Workflow** (existing GenAI review), **RAG** (retrieval-augmented generation for policy enrichment), and **Agentic AI** (autonomous decision-making with confidence gating).

## High-Level Architecture

```
                         ┌─────────────────────────────────┐
                         │        Agent Controller          │
                         │     (LangGraph State Machine)    │
                         │         Port 8015                │
                         └──────────┬──────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌──────────┐   ┌──────────────┐  ┌──────────┐
            │  RAG API │   │  MCP Server  │  │ Postgres │
            │  :8014   │   │    :8016     │  │  :5432   │
            └────┬─────┘   └──────┬───────┘  └──────────┘
                 │                │
            ┌────┴────┐    ┌─────┴──────────────────────┐
            │ Qdrant  │    │  Tools:                     │
            │ :6333   │    │  market.get_last_price      │
            └─────────┘    │  risk.check_trade           │
                           │  oms.place_order            │
                           │  db.get_workflow            │
                           │  db.list_audit              │
                           └────────────────────────────┘
```

## Agent Graph (State Machine)

The Agent Controller executes a sequential graph inspired by **LangGraph**:

```
┌──────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐    ┌────────┐    ┌─────────┐
│ PLAN │───►│ RETRIEVE │───►│ TOOL_CALLS │───►│ EVALUATE │───►│ DECIDE │───►│ EXECUTE │
└──────┘    └──────────┘    └────────────┘    └──────────┘    └────────┘    └─────────┘
                │                  │                │               │              │
                ▼                  ▼                ▼               ▼              ▼
          audit_logs:        audit_logs:      audit_logs:     audit_logs:    audit_logs:
          rag.retrieve       mcp.tool_call    agent.evaluate  agent.decision order.filled
```

Each node in the graph produces an audit trail entry, ensuring full traceability.

## Sequence Diagram

```
Client              Agent Controller      RAG API       MCP Server      Postgres
  │                       │                  │              │               │
  │  POST /agent/trade    │                  │              │               │
  │──────────────────────►│                  │              │               │
  │                       │  INSERT workflow │              │               │
  │                       │─────────────────────────────────────────────────►
  │                       │                  │              │               │
  │                       │  PLAN            │              │               │
  │                       │  (audit: agent.plan)            │               │
  │                       │─────────────────────────────────────────────────►
  │                       │                  │              │               │
  │                       │  POST /query     │              │               │
  │                       │─────────────────►│              │               │
  │                       │  ◄── hits ───────│              │               │
  │                       │  (audit: rag.retrieve)          │               │
  │                       │─────────────────────────────────────────────────►
  │                       │                  │              │               │
  │                       │  POST /call (price + risk)      │               │
  │                       │─────────────────────────────────►               │
  │                       │  ◄── results ───────────────────│               │
  │                       │  (audit: mcp.tool_call x2)      │               │
  │                       │                  │              │               │
  │                       │  EVALUATE        │              │               │
  │                       │  (audit: agent.evaluate)        │               │
  │                       │─────────────────────────────────────────────────►
  │                       │                  │              │               │
  │                       │  DECIDE          │              │               │
  │                       │  (audit: agent.decision)        │               │
  │                       │─────────────────────────────────────────────────►
  │                       │                  │              │               │
  │                       │  [if APPROVE] POST /call (oms)  │               │
  │                       │─────────────────────────────────►               │
  │                       │  (audit: order.filled)          │               │
  │                       │─────────────────────────────────────────────────►
  │                       │                  │              │               │
  │  ◄── response ────────│                  │              │               │
  │                       │                  │              │               │
```

## Confidence Gating

The agent computes a **confidence_score** (0.0 to 1.0) based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| Base score | 0.5 | Starting point for every trade |
| Risk check passed | +0.3 | If all risk rules are satisfied |
| Risk violations | -0.1 each | Per violation detected |
| RAG context quality | +0.1 * avg_score | Relevance of retrieved policies |

The `CONFIDENCE_THRESHOLD` environment variable (default: 0.7) determines the gating:

| Condition | Decision |
|-----------|----------|
| `confidence >= threshold` AND risk passed | **APPROVE** |
| `confidence >= threshold` AND risk failed | **DENY** |
| `confidence < threshold` | **NEEDS_HUMAN** |

## Audit Trail

Every step of the agent pipeline writes to `audit_logs`:

| Kind | Description |
|------|-------------|
| `agent.plan` | Execution plan formulated by the agent |
| `rag.retrieve` | RAG query and retrieved passages |
| `mcp.tool_call` | Each MCP tool invocation (price, risk, order) |
| `agent.evaluate` | Confidence score computation details |
| `agent.decision` | Final decision (APPROVE/DENY/NEEDS_HUMAN) |
| `order.filled` | Order execution confirmation (if approved) |

All entries share the same `correlation_id` for end-to-end tracing.
