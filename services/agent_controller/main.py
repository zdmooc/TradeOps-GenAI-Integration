"""Agent Controller I6.

The service produces governed analysis-only assessments from deterministic,
ML, RAG and risk evidence. Autonomous order placement is intentionally disabled.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from services.agent_controller.contracts import AgentContext, Direction
from services.agent_controller.graph import run_agent_graph
from services.agent_controller.rag_governance import RagPolicy, assess_rag_hits
from services.common.logging import setup_logging
from services.common.metrics import install

log = setup_logging("agent-controller")

app = FastAPI(title="Agent Controller", version="0.2")
install(app, "agent-controller")

RAG_API_URL = os.getenv("RAG_API_URL", "http://rag-api:8014")


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


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "agent-controller",
        "mode": "ANALYSIS_ONLY",
        "framework": "LangGraph",
    }


@app.get("/metrics")
def metrics():
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/agent/assessment", response_model=AgentAssessmentResponse)
def agent_assessment(req: AgentAssessmentRequest):
    correlation_id = str(uuid.uuid4())
    hits = req.rag_hits
    if hits is None:
        question = req.rag_question or (
            f"{req.symbol} trading setup risk policy strategy runbook evidence"
        )
        hits = _retrieve_rag(question)

    rag = assess_rag_hits(hits, RagPolicy())
    context = AgentContext(
        symbol=req.symbol.upper(),
        event_age_ms=req.event_age_ms,
        max_freshness_ms=req.max_freshness_ms,
        market_direction=_parse_direction(req.market_direction),
        technical_structure=req.technical_structure,
        pattern_directions=tuple(
            _parse_direction(item) for item in req.pattern_directions
        ),
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
    log.info(
        "assessment corr=%s symbol=%s status=%s direction=%s",
        correlation_id,
        context.symbol,
        assessment.status.value,
        assessment.direction.value,
    )
    return AgentAssessmentResponse(
        correlation_id=correlation_id,
        assessment=payload,
        rag_rejected=list(rag.rejected),
    )


@app.post("/agent/trade")
def autonomous_trade_disabled():
    raise HTTPException(
        status_code=409,
        detail={
            "code": "AUTONOMOUS_EXECUTION_DISABLED",
            "message": (
                "I6 agent workflows are analysis-only. Use /agent/assessment. "
                "Human approval/fusion execution belongs to I7."
            ),
        },
    )
