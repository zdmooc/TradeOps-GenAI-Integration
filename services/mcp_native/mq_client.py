from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx


PAYMENT_QUEUES = (
    "PAYMENT.REQUEST.Q",
    "PAYMENT.RESPONSE.Q",
    "PAYMENT.DLQ",
    "PAYMENT.BACKOUT.Q",
)


class MqOpsError(RuntimeError):
    pass


def _base_url() -> str:
    return os.getenv(
        "MQ_OPS_API_URL",
        "http://mq-ops-api.mayabank-mq-local.svc.cluster.local:8080",
    ).rstrip("/")


def _service_token() -> str:
    token_file = os.getenv("MQ_OPS_API_TOKEN_FILE", "").strip()
    if token_file:
        path = Path(token_file)
        if not path.is_file():
            raise MqOpsError("MQ ops service token file is missing")
        value = path.read_text(encoding="utf-8").strip()
    else:
        value = os.getenv("MQ_OPS_API_TOKEN", "").strip()
    if not value:
        raise MqOpsError("MQ ops service token is not configured")
    return value


def _get_json(path: str) -> dict[str, Any]:
    try:
        response = httpx.get(
            f"{_base_url()}{path}",
            headers={"Authorization": f"Bearer {_service_token()}"},
            timeout=3.0,
        )
    except httpx.HTTPError as exc:
        raise MqOpsError(f"MQ ops adapter is unreachable: {exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        raise MqOpsError(f"MQ ops adapter rejected request: HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise MqOpsError("MQ ops adapter returned invalid JSON")
    return payload


def get_queue_status(queue: str) -> dict[str, Any]:
    name = queue.strip().upper()
    if name not in PAYMENT_QUEUES:
        raise MqOpsError(f"queue is not allowed: {name}")
    return _get_json(f"/queues/{name}")


def _depth(item: dict[str, Any]) -> int:
    value = item.get("current_depth", 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _depth_percent(item: dict[str, Any]) -> float:
    value = item.get("depth_percent", 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def classify_payment_mq_health(payload: dict[str, Any]) -> dict[str, Any]:
    raw_items = payload.get("queues", [])
    if not isinstance(raw_items, list):
        raise MqOpsError("MQ ops adapter queues payload is invalid")

    queues: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        if isinstance(item, dict) and str(item.get("queue", "")) in PAYMENT_QUEUES:
            queues[str(item["queue"])] = dict(item)

    missing = [name for name in PAYMENT_QUEUES if name not in queues]
    if missing:
        raise MqOpsError(f"MQ ops adapter omitted queues: {', '.join(missing)}")

    request = queues["PAYMENT.REQUEST.Q"]
    response = queues["PAYMENT.RESPONSE.Q"]
    dlq = queues["PAYMENT.DLQ"]
    backout = queues["PAYMENT.BACKOUT.Q"]

    reasons: list[str] = []
    status = "HEALTHY"

    if _depth(dlq) > 0:
        status = "DEGRADED"
        reasons.append("PAYMENT.DLQ contains messages")
    if _depth(backout) > 0:
        status = "DEGRADED"
        reasons.append("PAYMENT.BACKOUT.Q contains messages")

    request_pct = _depth_percent(request)
    if request_pct >= 80.0:
        status = "DEGRADED"
        reasons.append("PAYMENT.REQUEST.Q is at or above 80% capacity")
    elif request_pct >= 50.0 and status == "HEALTHY":
        status = "WARNING"
        reasons.append("PAYMENT.REQUEST.Q is at or above 50% capacity")

    if _depth(request) > 0 and int(request.get("open_input_count", 0) or 0) == 0:
        if status == "HEALTHY":
            status = "WARNING"
        reasons.append("PAYMENT.REQUEST.Q has messages but no open input consumer")

    return {
        "source": "ibm-mq",
        "qmgr": payload.get("qmgr", "QM.MAYABANK"),
        "status": status,
        "reasons": reasons,
        "queues": queues,
        "observed_at": payload.get("observed_at"),
        "summary": {
            "request_depth": _depth(request),
            "response_depth": _depth(response),
            "dlq_depth": _depth(dlq),
            "backout_depth": _depth(backout),
            "request_depth_percent": request_pct,
        },
    }


def get_payment_mq_health() -> dict[str, Any]:
    return classify_payment_mq_health(_get_json("/queues"))


MQ_TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "mq.get_queue_status": {
        "description": "Read one allow-listed MayaBank IBM MQ payment queue status",
        "parameters": {"queue": {"type": "string", "required": True}},
        "handler": get_queue_status,
    },
    "payments.get_mq_health": {
        "description": "Read and deterministically classify the MayaBank payment MQ flow health",
        "parameters": {},
        "handler": get_payment_mq_health,
    },
}


def execute_mq_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    metadata = MQ_TOOL_REGISTRY.get(tool_name)
    if metadata is None:
        raise MqOpsError(f"unknown MQ tool: {tool_name}")
    return metadata["handler"](**arguments)
