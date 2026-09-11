"""Agent Controller I7: governed assessment, deterministic fusion and HITL.

I6 analysis remains available. I7 adds a persisted decision proposal/review workflow.
No decision is auto-approved: eligible proposals become REVIEW_REQUIRED and require
an authenticated human reviewer before SHADOW or PAPER execution.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from services.agent_controller.contracts import AgentContext, Direction
from services.agent_controller.graph import run_agent_graph
from services.agent_controller.rag_governance import RagPolicy, assess_rag_hits
from services.common.audit import log_audit
from services.common.logging import setup_logging
from services.common.metrics import install
from services.decision_fusion.models import DecisionInput, ExecutionMode, ReviewDecision
from services.decision_fusion.policy import FusionPolicy, fuse_decision
from services.decision_fusion.store import PostgresDecisionStore
from services.decision_fusion.workflow import (
    WorkflowError,
    execute_approved_case,
    open_case,
    review_case,
)

log = setup_logging("agent-controller")
app = FastAPI(title="Agent Controller", version="0.3")
install(app, "agent-controller")

RAG_API_URL = os.getenv("RAG_API_URL", "http://rag-api:8014")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8016")
_decision_store = PostgresDecisionStore()


class AgentAssessmentRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    event_age_ms: float | None = Field(default=None, ge=0)
    max_freshness_ms: float = Field(default=5_000.0, gt=0)
    market_direction: str = Field(default="UNKNOWN")
    technical_structure: str = Field(default="UNKNOWN")
    pattern_directions: list[str] = Field(default_factory=list)
    macro_state: str = Field(default="UNKNOWN")
    event_risk: bool = False
    risk_status: str = Field(default="UNKNOWN")
    risk_reasons: list[str] = Field(default_factory=list)
    rag_question: str | None = None
    rag_hits: list[dict[str, Any]] | None = None
    ml_score: float | None = Field(default=None, ge=0, le=1)
    ml_probability_status: str = Field(default="SCORE_ONLY")


class AgentAssessmentResponse(BaseModel):
    correlation_id: str
    assessment: dict[str, Any]
    rag_rejected: list[str]


class DecisionProposalRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    direction: str = Field(..., pattern="^(LONG|SHORT)$")
    qty: float = Field(..., gt=0)
    entry: float = Field(..., gt=0)
    stop: float = Field(..., gt=0)
    targets: list[float] = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    regime: str = Field(..., min_length=1)
    pattern: str = Field(..., min_length=1)
    assessment_status: str
    risk_status: str
    event_age_ms: float = Field(..., ge=0)
    max_freshness_ms: float = Field(default=5_000.0, gt=0)
    evidence_quality: float = Field(..., ge=0, le=1)
    rr: float = Field(..., gt=0)
    historical_expectancy_r: float
    historical_trade_count: int = Field(..., ge=0)
    ml_score: float | None = Field(default=None, ge=0, le=1)
    ml_probability_status: str = Field(default="SCORE_ONLY")
    evidence: list[str] = Field(default_factory=list)
    execution_mode: str = Field(default="SHADOW", pattern="^(SHADOW|PAPER)$")


class ReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(APPROVE|REJECT)$")
    rationale: str = Field(..., min_length=3)


class CaseResponse(BaseModel):
    case: dict[str, Any]


def _parse_direction(value: str) -> Direction:
    try:
        return Direction(value.upper())
    except ValueError:
        return Direction.UNKNOWN


def _retrieve_rag(question: str) -> list[dict[str, Any]]:
    try:
        response = httpx.post(
            f"{RAG_API_URL}/query",
            json={"question": question, "top_k": 5},
            timeout=3.0,
        )
        response.raise_for_status()
        payload = response.json()
        hits = payload.get("hits", [])
        return hits if isinstance(hits, list) else []
    except Exception as exc:
        log.warning("RAG retrieval failed closed: %s", exc)
        return []


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _require_role(authorization: str | None, role: str) -> str:
    token = _bearer_token(authorization)
    env_name = "MCP_AGENT_TOKEN" if role == "agent" else "MCP_REVIEWER_TOKEN"
    expected = os.getenv(env_name, "")
    if not expected or token != expected:
        raise HTTPException(status_code=401, detail=f"valid {role} bearer token required")
    return "agent-controller" if role == "agent" else "human-reviewer"


def _audit(kind: str, case_payload: dict[str, Any], correlation_id: str) -> str:
    return log_audit(
        kind=kind,
        ref_id=str(case_payload["proposal"]["proposal_id"]),
        data=case_payload,
        correlation_id=correlation_id,
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "agent-controller",
        "mode": "ANALYSIS_PLUS_HITL",
        "framework": "LangGraph",
        "execution": "SHADOW_OR_PAPER_AFTER_HUMAN_APPROVAL",
    }


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.post("/agent/assessment", response_model=AgentAssessmentResponse)
def agent_assessment(req: AgentAssessmentRequest):
    correlation_id = str(uuid.uuid4())
    hits = req.rag_hits
    if hits is None:
        question = req.rag_question or f"{req.symbol} trading setup risk policy strategy runbook evidence"
        hits = _retrieve_rag(question)
    rag = assess_rag_hits(hits, RagPolicy())
    context = AgentContext(
        symbol=req.symbol.upper(),
        event_age_ms=req.event_age_ms,
        max_freshness_ms=req.max_freshness_ms,
        market_direction=_parse_direction(req.market_direction),
        technical_structure=req.technical_structure,
        pattern_directions=tuple(_parse_direction(item) for item in req.pattern_directions),
        macro_state=req.macro_state,
        event_risk=req.event_risk,
        risk_status=req.risk_status,
        risk_reasons=tuple(req.risk_reasons),
        rag_status=rag.status,
        rag_evidence=rag.evidence,
        ml_score=req.ml_score,
        ml_probability_status=req.ml_probability_status,
    )
    assessment = run_agent_graph(context)
    payload = assessment.to_dict()
    payload["rag_evidence"] = list(context.rag_evidence)
    payload["ml_score"] = context.ml_score
    payload["ml_probability_status"] = context.ml_probability_status
    return AgentAssessmentResponse(
        correlation_id=correlation_id,
        assessment=payload,
        rag_rejected=list(rag.rejected),
    )


@app.post("/decision/propose", response_model=CaseResponse)
def propose_decision(req: DecisionProposalRequest, authorization: str | None = Header(default=None)):
    _require_role(authorization, "agent")
    item = DecisionInput(
        symbol=req.symbol.upper(),
        direction=req.direction,
        qty=req.qty,
        entry=req.entry,
        stop=req.stop,
        targets=tuple(req.targets),
        timeframe=req.timeframe,
        regime=req.regime,
        pattern=req.pattern,
        assessment_status=req.assessment_status,
        risk_status=req.risk_status,
        event_age_ms=req.event_age_ms,
        max_freshness_ms=req.max_freshness_ms,
        evidence_quality=req.evidence_quality,
        rr=req.rr,
        historical_expectancy_r=req.historical_expectancy_r,
        historical_trade_count=req.historical_trade_count,
        ml_score=req.ml_score,
        ml_probability_status=req.ml_probability_status,
        evidence=tuple(req.evidence),
    )
    proposal = fuse_decision(item, ExecutionMode(req.execution_mode), FusionPolicy())
    case = open_case(proposal)
    _decision_store.create(case)
    payload = case.to_dict()
    _audit("decision.proposed", payload, proposal.correlation_id)
    return CaseResponse(case=payload)


@app.get("/decision/{proposal_id}", response_model=CaseResponse)
def get_decision(proposal_id: str, authorization: str | None = Header(default=None)):
    token = _bearer_token(authorization)
    if token not in {os.getenv("MCP_AGENT_TOKEN", ""), os.getenv("MCP_REVIEWER_TOKEN", "")} or not token:
        raise HTTPException(status_code=401, detail="valid bearer token required")
    case = _decision_store.get(proposal_id)
    if case is None:
        raise HTTPException(status_code=404, detail="decision case not found")
    return CaseResponse(case=case.to_dict())


@app.post("/decision/{proposal_id}/review", response_model=CaseResponse)
def review_decision(
    proposal_id: str,
    req: ReviewRequest,
    authorization: str | None = Header(default=None),
):
    reviewer = _require_role(authorization, "reviewer")
    case = _decision_store.get(proposal_id)
    if case is None:
        raise HTTPException(status_code=404, detail="decision case not found")
    try:
        updated = review_case(
            case,
            reviewer=reviewer,
            decision=ReviewDecision(req.decision),
            rationale=req.rationale,
        )
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _decision_store.save(updated)
    payload = updated.to_dict()
    _audit("decision.reviewed", payload, updated.proposal.correlation_id)
    return CaseResponse(case=payload)


def _execute_paper(case) -> dict[str, Any]:
    token = os.getenv("MCP_REVIEWER_TOKEN", "")
    if not token:
        raise WorkflowError("MCP reviewer token is not configured")
    item = case.proposal.input
    response = httpx.post(
        f"{MCP_SERVER_URL}/call",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "tool": "oms.place_order",
            "arguments": {
                "symbol": item.symbol,
                "side": "BUY" if item.direction.upper() == "LONG" else "SELL",
                "qty": item.qty,
                "workflow_id": case.proposal.proposal_id,
            },
            "correlation_id": case.proposal.correlation_id,
            "workflow_id": case.proposal.proposal_id,
            "purpose": "i7-hitl-approved-paper",
            "human_approved": True,
        },
        timeout=5.0,
    )
    if response.status_code >= 400:
        raise WorkflowError(f"governed paper execution failed: HTTP {response.status_code}")
    result = response.json().get("result")
    if not isinstance(result, dict):
        raise WorkflowError("governed paper execution returned invalid result")
    return result


@app.post("/decision/{proposal_id}/execute", response_model=CaseResponse)
def execute_decision(proposal_id: str, authorization: str | None = Header(default=None)):
    _require_role(authorization, "reviewer")
    case = _decision_store.get(proposal_id)
    if case is None:
        raise HTTPException(status_code=404, detail="decision case not found")
    try:
        updated = execute_approved_case(case, paper_executor=_execute_paper)
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _decision_store.save(updated)
    payload = updated.to_dict()
    _audit("decision.executed", payload, updated.proposal.correlation_id)
    return CaseResponse(case=payload)


@app.post("/agent/trade")
def autonomous_trade_disabled():
    raise HTTPException(
        status_code=409,
        detail={
            "code": "AUTONOMOUS_EXECUTION_DISABLED",
            "message": (
                "Autonomous agent execution remains disabled. I7 requires a fusion "
                "proposal plus authenticated human review before SHADOW/PAPER."
            ),
        },
    )
