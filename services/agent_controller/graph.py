"""LangGraph-style agent graph for trade processing.

Implements the state machine:
  PLAN → RETRIEVE (RAG) → TOOL_CALLS (MCP) → EVALUATE → DECIDE

Uses a simple dict-based state and sequential node execution
(compatible with langgraph StateGraph pattern but implemented
without the langgraph dependency for portability).
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from services.common.audit import log_audit
from services.common.db import execute
from services.common.logging import setup_logging

log = setup_logging("agent-controller.graph")

# ── Configuration ────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
RAG_API_URL = os.getenv("RAG_API_URL", "http://rag-api:8014")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8016")


# ── State ────────────────────────────────────────────────────────────

class AgentState:
    """Mutable state passed through the graph nodes."""

    def __init__(
        self,
        symbol: str,
        side: str,
        qty: float,
        reason: str,
        workflow_id: str,
        correlation_id: str,
    ):
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.reason = reason
        self.workflow_id = workflow_id
        self.correlation_id = correlation_id

        # Populated by nodes
        self.plan: Dict[str, Any] = {}
        self.rag_hits: List[Dict[str, Any]] = []
        self.price_result: Dict[str, Any] = {}
        self.risk_result: Dict[str, Any] = {}
        self.order_result: Dict[str, Any] = {}
        self.confidence_score: float = 0.0
        self.decision: str = "DENY"  # APPROVE / DENY / NEEDS_HUMAN
        self.evaluation: Dict[str, Any] = {}


# ── Graph Nodes ──────────────────────────────────────────────────────

def node_plan(state: AgentState) -> AgentState:
    """PLAN – Formulate the execution plan."""
    state.plan = {
        "steps": [
            "1. Retrieve relevant policies and risk rules from RAG",
            "2. Get current market price via MCP",
            "3. Run risk check via MCP",
            "4. Evaluate confidence based on risk + RAG context",
            "5. Decide: APPROVE / DENY / NEEDS_HUMAN",
        ],
        "symbol": state.symbol,
        "side": state.side,
        "qty": state.qty,
        "reason": state.reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log_audit(
        kind="agent.plan",
        ref_id=state.workflow_id,
        data=state.plan,
        correlation_id=state.correlation_id,
    )
    log.info("PLAN completed wf=%s", state.workflow_id)
    return state


def node_retrieve(state: AgentState) -> AgentState:
    """RETRIEVE – Query RAG for relevant context."""
    query_text = (
        f"Trade request: {state.side} {state.qty} {state.symbol}. "
        f"Reason: {state.reason}. "
        f"What are the relevant risk rules and policies?"
    )
    try:
        resp = httpx.post(
            f"{RAG_API_URL}/query",
            json={"question": query_text, "top_k": 3},
            timeout=10.0,
        )
        resp.raise_for_status()
        state.rag_hits = resp.json().get("hits", [])
    except Exception as e:
        log.warning("RAG query failed (continuing without context): %s", e)
        state.rag_hits = []

    log_audit(
        kind="rag.retrieve",
        ref_id=state.workflow_id,
        data={
            "query": query_text,
            "hits_count": len(state.rag_hits),
            "hits": state.rag_hits[:3],
        },
        correlation_id=state.correlation_id,
    )
    log.info("RETRIEVE completed wf=%s hits=%d", state.workflow_id, len(state.rag_hits))
    return state


def _mcp_call(tool: str, arguments: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
    """Helper to call an MCP tool."""
    try:
        resp = httpx.post(
            f"{MCP_SERVER_URL}/call",
            json={
                "tool": tool,
                "arguments": arguments,
                "correlation_id": state.correlation_id,
                "workflow_id": state.workflow_id,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("result", {})
    except Exception as e:
        log.warning("MCP call %s failed: %s", tool, e)
        return {"error": str(e)}


def node_tool_calls(state: AgentState) -> AgentState:
    """TOOL_CALLS – Execute MCP tools (price + risk check)."""
    state.price_result = _mcp_call(
        "market.get_last_price",
        {"symbol": state.symbol},
        state,
    )
    state.risk_result = _mcp_call(
        "risk.check_trade",
        {"symbol": state.symbol, "side": state.side, "qty": state.qty},
        state,
    )
    log.info("TOOL_CALLS completed wf=%s", state.workflow_id)
    return state


def node_evaluate(state: AgentState) -> AgentState:
    """EVALUATE – Compute confidence score based on risk + RAG context."""
    score = 0.5  # base score

    # Risk check contribution
    risk_passed = state.risk_result.get("passed", False)
    if risk_passed:
        score += 0.3
    else:
        violations = state.risk_result.get("violations", [])
        score -= 0.1 * len(violations)

    # RAG context contribution
    if state.rag_hits:
        avg_rag_score = sum(h.get("score", 0) for h in state.rag_hits) / len(state.rag_hits)
        score += 0.1 * avg_rag_score  # small boost if relevant context found

    # Clamp to [0, 1]
    state.confidence_score = max(0.0, min(1.0, round(score, 4)))

    state.evaluation = {
        "confidence_score": state.confidence_score,
        "risk_passed": risk_passed,
        "risk_violations": state.risk_result.get("violations", []),
        "rag_hits_count": len(state.rag_hits),
        "price": state.price_result.get("last"),
        "notional": state.risk_result.get("notional"),
        "threshold": CONFIDENCE_THRESHOLD,
    }

    log_audit(
        kind="agent.evaluate",
        ref_id=state.workflow_id,
        data=state.evaluation,
        correlation_id=state.correlation_id,
    )
    log.info(
        "EVALUATE completed wf=%s confidence=%.4f threshold=%.2f",
        state.workflow_id,
        state.confidence_score,
        CONFIDENCE_THRESHOLD,
    )
    return state


def node_decide(state: AgentState) -> AgentState:
    """DECIDE – Make final decision based on confidence score."""
    if state.confidence_score >= CONFIDENCE_THRESHOLD:
        if state.risk_result.get("passed", False):
            state.decision = "APPROVE"
        else:
            state.decision = "DENY"
    else:
        state.decision = "NEEDS_HUMAN"

    # Update workflow in DB
    execute(
        "UPDATE workflows SET status = %s, updated_at = now() WHERE workflow_id = %s",
        (state.decision, state.workflow_id),
    )

    # Update new columns
    execute(
        "UPDATE workflows SET confidence_score = %s, decision = %s, reviewer = %s "
        "WHERE workflow_id = %s",
        (state.confidence_score, state.decision, "agent_controller", state.workflow_id),
    )

    log_audit(
        kind="agent.decision",
        ref_id=state.workflow_id,
        data={
            "decision": state.decision,
            "confidence_score": state.confidence_score,
            "symbol": state.symbol,
            "side": state.side,
            "qty": state.qty,
        },
        correlation_id=state.correlation_id,
    )
    log.info(
        "DECIDE completed wf=%s decision=%s confidence=%.4f",
        state.workflow_id,
        state.decision,
        state.confidence_score,
    )
    return state


def node_execute_order(state: AgentState) -> AgentState:
    """EXECUTE – If APPROVE, place the order via MCP/OMS."""
    if state.decision != "APPROVE":
        return state

    state.order_result = _mcp_call(
        "oms.place_order",
        {"symbol": state.symbol, "side": state.side, "qty": state.qty},
        state,
    )

    order_id = state.order_result.get("order_id", "")
    if order_id:
        # Update workflow status to FILLED
        execute(
            "UPDATE workflows SET status = %s, updated_at = now() WHERE workflow_id = %s",
            ("FILLED", state.workflow_id),
        )
        # Audit the fill
        log_audit(
            kind="order.filled",
            ref_id=order_id,
            data={
                "workflow_id": state.workflow_id,
                "order_id": order_id,
                "symbol": state.symbol,
                "side": state.side,
                "qty": state.qty,
                "fill_price": state.order_result.get("fill_price"),
            },
            correlation_id=state.correlation_id,
        )

    log.info(
        "EXECUTE completed wf=%s order_id=%s",
        state.workflow_id,
        order_id,
    )
    return state


# ── Graph Runner ─────────────────────────────────────────────────────

GRAPH_NODES = [
    ("PLAN", node_plan),
    ("RETRIEVE", node_retrieve),
    ("TOOL_CALLS", node_tool_calls),
    ("EVALUATE", node_evaluate),
    ("DECIDE", node_decide),
    ("EXECUTE", node_execute_order),
]


def run_agent_graph(
    symbol: str,
    side: str,
    qty: float,
    reason: str,
    workflow_id: str,
    correlation_id: str,
) -> AgentState:
    """Execute the full agent graph and return the final state."""
    state = AgentState(
        symbol=symbol,
        side=side,
        qty=qty,
        reason=reason,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
    )

    for node_name, node_fn in GRAPH_NODES:
        log.info("Running node %s for wf=%s", node_name, workflow_id)
        state = node_fn(state)

    return state
