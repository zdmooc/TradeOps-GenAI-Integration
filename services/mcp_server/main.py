"""Governed tool boundary for agent-accessible capabilities.

The existing HTTP compatibility endpoint is retained, but every call now goes
through server-side authentication, scope authorization, strict argument
validation, rate limiting, timeouts, audit redaction and HITL policy.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from services.common.audit import log_audit
from services.common.logging import setup_logging
from services.common.metrics import install
from services.mcp_server.governance import (
    Principal,
    StaticTokenAuthenticator,
    ToolGovernor,
    redact_sensitive,
)
from services.mcp_server.state import MCPState
from services.mcp_server.tools import TOOL_REGISTRY, execute_tool

log = setup_logging("mcp-server")

app = FastAPI(title="Governed Tool Server", version="0.2")
install(app, "mcp-server")

_state = MCPState()
_governor = ToolGovernor()


def _build_authenticator() -> StaticTokenAuthenticator:
    agent_token = os.getenv("MCP_AGENT_TOKEN", "")
    reviewer_token = os.getenv("MCP_REVIEWER_TOKEN", "")
    return StaticTokenAuthenticator(
        {
            agent_token: Principal(
                name="agent-controller",
                scopes=frozenset({"market.read", "risk.evaluate", "workflow.read"}),
            ),
            reviewer_token: Principal(
                name="human-reviewer",
                scopes=frozenset(
                    {
                        "market.read",
                        "risk.evaluate",
                        "workflow.read",
                        "audit.read",
                        "paper.execute",
                    }
                ),
            ),
        }
    )


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


class ToolCallRequest(BaseModel):
    tool: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    workflow_id: str | None = None
    purpose: str = Field(default="agent-analysis", min_length=3)
    human_approved: bool = False


class ToolCallResponse(BaseModel):
    tool: str
    result: Any
    correlation_id: str
    audit_hash: str
    policy_code: str
    duration_ms: float


class ToolListItem(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-server", "governed": True}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/tools")
def list_tools(authorization: str | None = Header(default=None)):
    principal = _build_authenticator().authenticate(_bearer_token(authorization))
    if principal is None:
        raise HTTPException(status_code=401, detail="valid bearer token required")
    items = [
        ToolListItem(
            name=name,
            description=meta["description"],
            parameters=meta["parameters"],
        )
        for name, meta in TOOL_REGISTRY.items()
    ]
    return {"tools": items, "principal": principal.name}


def _status_for_policy_code(code: str) -> int:
    if code == "UNAUTHENTICATED":
        return 401
    if code in {"FORBIDDEN", "HUMAN_APPROVAL_REQUIRED", "TOOL_NOT_ALLOWED"}:
        return 403
    if code == "RATE_LIMITED":
        return 429
    if code == "TIMEOUT":
        return 504
    return 400


@app.post("/call", response_model=ToolCallResponse)
def call_tool(
    req: ToolCallRequest,
    authorization: str | None = Header(default=None),
):
    correlation_id = req.correlation_id or str(uuid.uuid4())
    workflow_id = req.workflow_id or ""
    _state.set_correlation_id(correlation_id)

    principal = _build_authenticator().authenticate(_bearer_token(authorization))
    execution = _governor.execute(
        tool_name=req.tool,
        arguments=req.arguments,
        principal=principal,
        tool_registry=TOOL_REGISTRY,
        human_approved=req.human_approved,
        executor=execute_tool,
    )

    ref_id = workflow_id or correlation_id
    audit_data = {
        "tool": req.tool,
        "principal": principal.name if principal else "UNAUTHENTICATED",
        "purpose": req.purpose,
        "human_approved": req.human_approved,
        "policy_code": execution.code,
        "allowed": execution.allowed,
        "arguments": execution.sanitized_arguments,
        "result": redact_sensitive(execution.result),
        "duration_ms": round(execution.duration_ms, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    audit_hash = log_audit(
        kind="mcp.tool_call",
        ref_id=ref_id,
        data=audit_data,
        correlation_id=correlation_id,
    )

    if not execution.allowed:
        log.warning(
            "tool_denied tool=%s principal=%s code=%s corr=%s",
            req.tool,
            principal.name if principal else "UNAUTHENTICATED",
            execution.code,
            correlation_id,
        )
        raise HTTPException(
            status_code=_status_for_policy_code(execution.code),
            detail={
                "code": execution.code,
                "reason": execution.reason,
                "correlation_id": correlation_id,
                "audit_hash": audit_hash,
            },
        )

    log.info(
        "tool_call tool=%s principal=%s corr=%s duration_ms=%.3f",
        req.tool,
        principal.name if principal else "UNAUTHENTICATED",
        correlation_id,
        execution.duration_ms,
    )
    return ToolCallResponse(
        tool=req.tool,
        result=execution.result,
        correlation_id=correlation_id,
        audit_hash=audit_hash,
        policy_code=execution.code,
        duration_ms=execution.duration_ms,
    )


@app.get("/state")
def get_state():
    return _state.to_dict()
