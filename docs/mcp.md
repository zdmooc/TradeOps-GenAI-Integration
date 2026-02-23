# MCP Server – Model Context Protocol

## Overview

The MCP Server standardises access to internal tools (database, OMS, risk engine, market data) through a single HTTP endpoint. It follows the **Model Context Protocol** pattern: a tool registry, a unified `/call` endpoint, and automatic audit logging for every invocation.

The Agent Controller (and any future LLM-based agent) interacts with the platform exclusively through the MCP Server, ensuring that every action is traceable and auditable.

## Architecture

```
Agent Controller  ──►  POST /call  ──►  MCP Server (port 8016)
                                            │
                     ┌──────────────────────┼──────────────────────┐
                     ▼                      ▼                      ▼
              market.get_last_price   risk.check_trade      oms.place_order
                                            │
                                     ┌──────┴──────┐
                                     ▼              ▼
                              db.get_workflow  db.list_audit
                                            │
                                            ▼
                                     audit_logs (PostgreSQL)
```

Every tool call writes an entry to `audit_logs` with `kind = mcp.tool_call`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/tools` | List all registered tools with their schemas |
| `POST` | `/call` | Execute a tool by name |
| `GET` | `/state` | Return current MCP server state (debug) |

## Tool Catalog

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `market.get_last_price` | Get last known price for a symbol | `symbol` (string) |
| `risk.check_trade` | Check if a trade passes risk rules | `symbol`, `side`, `qty` |
| `oms.place_order` | Place a paper order (fills immediately) | `symbol`, `side`, `qty` |
| `db.get_workflow` | Retrieve a workflow by ID | `workflow_id` (string) |
| `db.list_audit` | List recent audit log entries | `limit` (int, default 20) |

## Request / Response Examples

### POST /call

**Request:**

```json
{
  "tool": "market.get_last_price",
  "arguments": {"symbol": "AAPL"},
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_id": "wf-123"
}
```

**Response:**

```json
{
  "tool": "market.get_last_price",
  "result": {"symbol": "AAPL", "last": 142.3, "ts": "2026-02-23T10:00:00Z"},
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "audit_hash": "a1b2c3d4..."
}
```

### GET /tools

Returns the full tool registry with parameter schemas, enabling dynamic tool discovery by the Agent Controller.

## Audit Integration

Every tool call produces an `audit_logs` entry:

| Field | Value |
|-------|-------|
| `kind` | `mcp.tool_call` |
| `ref_id` | `workflow_id` or `order_id` (if applicable) |
| `data` | JSON with `tool`, `arguments`, `result`, `timestamp` |
| `correlation_id` | Propagated from the request |
| `hash` | SHA-256 of the data payload |

## In-Memory State

The MCP server maintains a lightweight in-memory state that tracks the current `correlation_id` and a cumulative tool-call counter. This state is accessible via `GET /state` for debugging purposes.

## Environment Variables

The MCP server reuses the standard project configuration (`services/common/config.py`). No additional environment variables are required beyond the standard PostgreSQL and Kafka settings.

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8016` | HTTP listen port |
