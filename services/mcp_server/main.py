"""Governed tool boundary with I8 observable authentication and authorization."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from services.common.audit import log_audit
from services.common.logging import setup_logging
from services.common.metrics import install
from services.common.observability_metrics import SECURITY_DENIALS
from services.common.otel import start_span
from services.mcp_server.governance import Principal, ToolGovernor, redact_sensitive
from services.mcp_server.state import MCPState
from services.mcp_server.tools import TOOL_REGISTRY, execute_tool
from services.security.identity import SecurityPrincipal, authenticate_authorization

log = setup_logging("mcp-server")
app = FastAPI(title="Governed Tool Server", version="0.3")
install(app, "mcp-server")

_state = MCPState()
_governor = ToolGovernor()


def _static_principals() -> dict[str, SecurityPrincipal]:
    return {
        os.getenv("MCP_AGENT_TOKEN", ""): SecurityPrincipal(
            subject="agent-controller",
            roles=frozenset({"agent"}),
            scopes=frozenset({"market.read", "risk.evaluate", "workflow.read"}),
            authn_method="static",
        ),
        os.getenv("MCP_REVIEWER_TOKEN", ""): SecurityPrincipal(
            subject="human-reviewer",
            roles=frozenset({"reviewer"}),
            scopes=frozenset(
                {
                    "market.read",
                    "risk.evaluate",
                    "workflow.read",
                    "audit.read",
                    "paper.execute",
                }
            ),
            authn_method="static",
        ),
    }


def _security_principal(authorization: str | None) -> SecurityPrincipal | None:
    return authenticate_authorization(
        authorization, static_principals=_static_principals()
    )


def _governor_principal(principal: SecurityPrincipal | None) -> Principal | None:
    if principal is None:
        return None
    return Principal(name=principal.subject, scopes=principal.scopes)


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
    return {
        "status": "ok",
        "service": "mcp-server",
        "governed": True,
        "auth_modes": ["static", "oidc"],
        "observability": "OTEL_PROMETHEUS_I8",
    }


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST
    )


@app.get("/tools")
def list_tools(authorization: str | None = Header(default=None)):
    principal = _security_principal(authorization)
    if principal is None:
        SECURITY_DENIALS.labels(boundary="mcp-server", reason="UNAUTHENTICATED").inc()
        raise HTTPException(status_code=401, detail="valid bearer token required")
    items = [
        ToolListItem(
            name=name,
            description=meta["description"],
            parameters=meta["parameters"],
        )
        for name, meta in TOOL_REGISTRY.items()
    ]
    return {"tools": items, "principal": principal.subject}


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
def call_tool(req: ToolCallRequest, authorization: str | None = Header(default=None)):
    correlation_id = req.correlation_id or str(uuid.uuid4())
    workflow_id = req.workflow_id or ""
    _state.set_correlation_id(correlation_id)

    security_principal = _security_principal(authorization)
    principal = _governor_principal(security_principal)
    with start_span(
        "mcp.tool_call",
        attributes={
            "tradeops.tool.name": req.tool,
            "tradeops.human_approved": req.human_approved,
            "tradeops.authn_method": (
                security_principal.authn_method if security_principal else "none"
            ),
        },
    ) as span:
        execution = _governor.execute(
            tool_name=req.tool,
            arguments=req.arguments,
            principal=principal,
            tool_registry=TOOL_REGISTRY,
            human_approved=req.human_approved,
            executor=execute_tool,
        )
        span.set_attribute("tradeops.tool.policy_code", execution.code)
        span.set_attribute("tradeops.tool.allowed", execution.allowed)

    ref_id = workflow_id or correlation_id
    audit_data = {
        "tool": req.tool,
        "principal": principal.name if principal else "UNAUTHENTICATED",
        "authn_method": security_principal.authn_method if security_principal else "none",
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
        SECURITY_DENIALS.labels(boundary="mcp-server", reason=execution.code).inc()
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
