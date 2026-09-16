"""Read-only MCP Host routes mounted by the Agent Controller runtime in R2."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.agent_controller.mcp_client import (
    McpContextError,
    discover_capabilities_sync,
    get_trade_context_sync,
)
from services.common.otel import current_correlation_id

router = APIRouter(prefix="/agent/mcp", tags=["agent-mcp"])


class McpTradeContextRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    side: str = Field(..., pattern="^(BUY|SELL)$")
    qty: float = Field(..., gt=0)


class McpHostResponse(BaseModel):
    correlation_id: str
    payload: dict[str, Any]


@router.get("/capabilities", response_model=McpHostResponse)
def mcp_capabilities() -> McpHostResponse:
    correlation_id = current_correlation_id() or str(uuid.uuid4())
    try:
        payload = discover_capabilities_sync()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"native MCP discovery failed: {exc}") from exc
    return McpHostResponse(correlation_id=correlation_id, payload=payload)


@router.post("/context", response_model=McpHostResponse)
def mcp_trade_context(req: McpTradeContextRequest) -> McpHostResponse:
    """Ask MCP for market/risk facts only; never execute an order."""
    correlation_id = current_correlation_id() or str(uuid.uuid4())
    try:
        payload = get_trade_context_sync(req.symbol, req.side, req.qty)
    except McpContextError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"native MCP context failed: {exc}") from exc
    return McpHostResponse(correlation_id=correlation_id, payload=payload)
