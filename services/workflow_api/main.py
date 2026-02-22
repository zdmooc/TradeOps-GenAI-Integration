import json
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from services.common.logging import setup_logging
from services.common.metrics import install
from services.common.db import execute, fetchone, fetchall
from services.common.kafka import publish

log = setup_logging("workflow-api")

app = FastAPI(title="Workflow Orchestrator API", version="0.1")
install(app, "workflow-api")

class TradeRequest(BaseModel):
    symbol: str = Field(..., examples=["AAPL"])
    side: str = Field(..., pattern="^(BUY|SELL)$")
    qty: float = Field(..., gt=0)
    reason: str = Field(..., min_length=3)

class ApproveRequest(BaseModel):
    approver: str
    comment: str = ""

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

@app.post("/trade-requests")
async def create_trade_request(req: TradeRequest):
    workflow_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    payload = req.model_dump()
    execute(
        "INSERT INTO workflows(workflow_id,status,payload) VALUES (%s,%s,%s)",
        (workflow_id, "REQUESTED", json.dumps(payload)),
    )
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "workflow.requested",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "payload": {"workflow_id": workflow_id, **payload},
    }
    await publish("workflow.requested", event, key=workflow_id)
    log.info("workflow created id=%s corr=%s", workflow_id, correlation_id)
    return {"workflow_id": workflow_id, "correlation_id": correlation_id}

@app.post("/trade-requests/{workflow_id}/approve")
async def approve_trade_request(workflow_id: str, req: ApproveRequest):
    row = fetchone("SELECT workflow_id,status,payload FROM workflows WHERE workflow_id=%s", (workflow_id,))
    if not row:
        raise HTTPException(404, "workflow not found")
    if row["status"] != "REQUESTED":
        raise HTTPException(409, f"cannot approve status={row['status']}")
    execute("UPDATE workflows SET status=%s, updated_at=now() WHERE workflow_id=%s", ("APPROVED", workflow_id))
    correlation_id = str(uuid.uuid4())
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "workflow.approved",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "payload": {"workflow_id": workflow_id, "approver": req.approver, "comment": req.comment},
    }
    await publish("workflow.approved", event, key=workflow_id)
    log.info("workflow approved id=%s by=%s corr=%s", workflow_id, req.approver, correlation_id)
    return {"status": "APPROVED", "workflow_id": workflow_id, "correlation_id": correlation_id}

@app.get("/trade-requests/{workflow_id}")
def get_workflow(workflow_id: str):
    row = fetchone("SELECT workflow_id,status,payload,created_at,updated_at FROM workflows WHERE workflow_id=%s", (workflow_id,))
    if not row:
        raise HTTPException(404, "workflow not found")
    return row

@app.get("/audit")
def list_audit(limit: int = 50):
    rows = fetchall("SELECT audit_id,kind,ref_id,hash,correlation_id,created_at FROM audit_logs ORDER BY audit_id DESC LIMIT %s", (limit,))
    return {"items": rows}
