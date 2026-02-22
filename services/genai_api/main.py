import uuid
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from services.common.logging import setup_logging
from services.common.metrics import install
from services.common.kafka import consumer, consume_forever, publish
from services.common.audit import publish_audit
from .rag import SimpleRAG
from .llm import get_llm
import os

log = setup_logging("genai-api")

app = FastAPI(title="GenAI Service API (RAG + LLM adapter)", version="0.1")
install(app, "genai-api")

RAG_CORPUS_PATH = os.getenv("RAG_CORPUS_PATH", "/app/rag_corpus")
rag = SimpleRAG(RAG_CORPUS_PATH)
llm = get_llm()

class ReviewRequest(BaseModel):
    workflow_id: str
    symbol: str
    side: str
    qty: float
    reason: str

@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": os.getenv("LLM_PROVIDER", "mock")}

@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

@app.post("/review")
async def review(req: ReviewRequest):
    correlation_id = str(uuid.uuid4())
    hits = rag.query(f"risk rules for {req.symbol} {req.side} qty {req.qty} because {req.reason}", top_k=3)
    sources = [h[0] for h in hits]
    context = "\n\n".join([f"[{doc_id}]\n{snippet}" for doc_id, snippet, _ in hits])
    system = "Tu es un assistant Risk/Compliance. Tu dois être factuel, citer les documents internes."
    user = f"""Demande trade:
- symbol: {req.symbol}
- side: {req.side}
- qty: {req.qty}
- reason: {req.reason}

Documents internes (extraits):
{context}

Rédige une revue courte:
- summary
- risk_notes
- recommendation (approve/reject) + justification
- cite sources (doc ids)
"""
    out = await llm.complete(system=system, user=user)
    data = {"workflow_id": req.workflow_id, "summary": out[:600], "sources": sources}
    await publish_audit("genai.review", req.workflow_id, data, correlation_id)
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "genai.review.created",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "payload": {"workflow_id": req.workflow_id, "summary": out[:900], "risk_notes": "see summary", "sources": sources},
    }
    await publish("genai.review.created", event, key=req.workflow_id)
    return {"correlation_id": correlation_id, "sources": sources, "review": out}

async def _on_workflow_requested(topic: str, msg: dict):
    # Auto-trigger review on event workflow.requested
    p = msg.get("payload", {})
    req = ReviewRequest(
        workflow_id=p["workflow_id"],
        symbol=p["symbol"],
        side=p["side"],
        qty=float(p["qty"]),
        reason=p.get("reason",""),
    )
    await review(req)

@app.on_event("startup")
async def startup():
    # Consumer runs in background
    cons = consumer(["workflow.requested"], group_id="genai-reviewer")
    import asyncio
    asyncio.create_task(consume_forever(cons, _on_workflow_requested))
    log.info("GenAI consumer started topic=workflow.requested")
