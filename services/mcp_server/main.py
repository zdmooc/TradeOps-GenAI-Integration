"""MCP Server – Model Context Protocol server exposing internal tools.

Implements a lightweight MCP-compatible HTTP server (JSON-RPC style)
that exposes the following tools:
  1) market.get_last_price(symbol)
  2) risk.check_trade(symbol, side, qty)
  3) oms.place_order(symbol, side, qty)  [paper]
  4) db.get_workflow(workflow_id)
  5) db.list_audit(limit)

Each tool call is logged in audit_logs (kind = mcp.tool_call).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from services.common.audit import log_audit
from services.common.logging import setup_logging
from services.common.metrics import install
from services.mcp_server.tools import TOOL_REGISTRY, execute_tool
from services.mcp_server.state import MCPState

log = setup_logging("mcp-server")

app = FastAPI(title="MCP Server", version="0.1")
install(app, "mcp-server")

# Global MCP state (in-memory)
_state = MCPState()


# ── JSON-RPC Models ──────────────────────────────────────────────────

class ToolCallRequest(BaseModel):
    tool: str = Field(..., description="Tool name, e.g. market.get_last_price")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = Field(default=None)
    workflow_id: Optional[str] = Field(default=None)


class ToolCallResponse(BaseModel):
    tool: str
    result: Any
    correlation_id: str
    audit_hash: str


class ToolListItem(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-server"}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/tools")
def list_tools():
    """List all available MCP tools with their schemas."""
    items = []
    for name, meta in TOOL_REGISTRY.items():
        items.append(
            ToolListItem(
                name=name,
                description=meta["description"],
                parameters=meta["parameters"],
            )
        )
    return {"tools": items}


@app.post("/call", response_model=ToolCallResponse)
def call_tool(req: ToolCallRequest):
    """Execute a tool and return the result. Logs to audit_logs."""
    correlation_id = req.correlation_id or str(uuid.uuid4())
    workflow_id = req.workflow_id or ""

    # Update state
    _state.set_correlation_id(correlation_id)

    # Execute the tool
    result = execute_tool(req.tool, req.arguments)

    # Determine ref_id (workflow_id or order_id if present)
    ref_id = workflow_id
    if isinstance(result, dict) and "order_id" in result:
        ref_id = ref_id or str(result["order_id"])
    if not ref_id:
        ref_id = correlation_id

    # Audit log
    audit_data = {
        "tool": req.tool,
        "arguments": req.arguments,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    audit_hash = log_audit(
        kind="mcp.tool_call",
        ref_id=ref_id,
        data=audit_data,
        correlation_id=correlation_id,
    )

    log.info(
        "tool_call tool=%s corr=%s ref=%s hash=%s",
        req.tool,
        correlation_id,
        ref_id,
        audit_hash[:12],
    )

    return ToolCallResponse(
        tool=req.tool,
        result=result,
        correlation_id=correlation_id,
        audit_hash=audit_hash,
    )


@app.get("/state")
def get_state():
    """Return current MCP server state (for debugging)."""
    return _state.to_dict()
