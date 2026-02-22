import hashlib
import json
from typing import Any, Dict
from .db import execute
from .kafka import publish
from datetime import datetime, timezone
import uuid

def _hash(data: Dict[str, Any]) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def log_audit(kind: str, ref_id: str, data: Dict[str, Any], correlation_id: str):
    h = _hash({"kind": kind, "ref_id": ref_id, "data": data})
    execute(
        "INSERT INTO audit_logs(kind, ref_id, data, hash, correlation_id) VALUES (%s,%s,%s,%s,%s)",
        (kind, ref_id, json.dumps(data), h, correlation_id),
    )
    return h

async def publish_audit(kind: str, ref_id: str, data: Dict[str, Any], correlation_id: str):
    h = log_audit(kind, ref_id, data, correlation_id)
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "audit.logged",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "payload": {"kind": kind, "ref_id": ref_id, "hash": h, "data": data},
    }
    await publish("audit.logged", event, key=ref_id)
    return h
