"""Agent Controller – FastAPI service implementing an Agentic AI trade processor.

POST /agent/trade  – submit a trade for autonomous agent processing
GET  /health       – liveness probe
"""

import json
import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from services.common.db import execute
from services.common.logging import setup_logging
from services.common.metrics import install
from services.agent_controller.graph import run_agent_graph

log = setup_logging("agent-controller")

app = FastAPI(title="Agent Controller", version="0.1")
install(app, "agent-controller")


# ── Schemas ──────────────────────────────────────────────────────────

class AgentTradeRequest(BaseModel):
    symbol: str = Field(..., examples=["AAPL"])
    side: str = Field(..., pattern="^(BUY|SELL)$")
    qty: float = Field(..., gt=0)
    reason: str = Field(..., min_length=3)


class AgentTradeResponse(BaseModel):
    workflow_id: str
    correlation_id: str
    decision: str
    confidence_score: float
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    status: str


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "agent-controller"}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/agent/trade", response_model=AgentTradeResponse)
def agent_trade(req: AgentTradeRequest):
    """Submit a trade for autonomous agent processing.

    The agent controller:
    1. Creates a workflow (status=REQUESTED)
    2. Runs the LangGraph: PLAN → RETRIEVE → TOOL_CALLS → EVALUATE → DECIDE
    3. If APPROVE: places the order via MCP/OMS
    4. Returns the full result
    """
    workflow_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    payload = req.model_dump()

    # Create workflow
    execute(
        "INSERT INTO workflows(workflow_id, status, payload) VALUES (%s, %s, %s)",
        (workflow_id, "REQUESTED", json.dumps(payload)),
    )
    log.info("workflow created wf=%s corr=%s", workflow_id, correlation_id)

    # Run the agent graph
    state = run_agent_graph(
        symbol=req.symbol,
        side=req.side,
        qty=req.qty,
        reason=req.reason,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
    )

    # Build response
    order_id = state.order_result.get("order_id") if state.order_result else None
    fill_price = state.order_result.get("fill_price") if state.order_result else None

    # Determine final status
    if state.decision == "APPROVE" and order_id:
        final_status = "FILLED"
    elif state.decision == "APPROVE":
        final_status = "APPROVED"
    else:
        final_status = state.decision

    log.info(
        "agent trade completed wf=%s decision=%s confidence=%.4f order=%s",
        workflow_id,
        state.decision,
        state.confidence_score,
        order_id,
    )

    return AgentTradeResponse(
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        decision=state.decision,
        confidence_score=state.confidence_score,
        order_id=order_id,
        fill_price=fill_price,
        status=final_status,
    )
