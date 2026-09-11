"""MCP Tool implementations.

Each tool is registered in TOOL_REGISTRY with its metadata (description, parameters).
execute_tool() dispatches to the correct handler.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from services.common.db import execute, fetchall, fetchone
from services.common.logging import setup_logging

log = setup_logging("mcp-server.tools")
_price_cache: Dict[str, Dict[str, Any]] = {}


def _synthetic_price(symbol: str) -> float:
    return 100 + (hash(symbol.upper()) % 1000) / 10.0


def market_get_last_price(symbol: str) -> Dict[str, Any]:
    sym = symbol.upper()
    price = _synthetic_price(sym)
    ts = datetime.now(timezone.utc).isoformat()
    _price_cache[sym] = {"symbol": sym, "last": price, "ts": ts}
    return {"symbol": sym, "last": price, "ts": ts}


def risk_check_trade(symbol: str, side: str, qty: float) -> Dict[str, Any]:
    sym = symbol.upper()
    price = _synthetic_price(sym)
    notional = price * qty
    violations = []
    if qty > 10_000:
        violations.append(f"qty {qty} exceeds max 10,000 units")
    if notional > 1_000_000:
        violations.append(f"notional ${notional:,.0f} exceeds $1,000,000 limit")
    if side.upper() not in ("BUY", "SELL"):
        violations.append(f"invalid side: {side}")
    return {
        "symbol": sym,
        "side": side.upper(),
        "qty": qty,
        "notional": round(notional, 2),
        "passed": len(violations) == 0,
        "violations": violations,
    }


def oms_place_order(
    symbol: str,
    side: str,
    qty: float,
    workflow_id: str | None = None,
) -> Dict[str, Any]:
    """Place a paper order only after governed HITL authorization upstream."""
    sym = symbol.upper()
    order_id = str(uuid.uuid4())
    fill_price = _synthetic_price(sym)
    linked_workflow_id = workflow_id or str(uuid.uuid4())
    execute(
        "INSERT INTO orders(order_id, workflow_id, status, symbol, side, qty, fill_price) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (order_id, linked_workflow_id, "FILLED", sym, side.upper(), qty, fill_price),
    )
    log.info(
        "paper order placed order_id=%s workflow_id=%s symbol=%s side=%s qty=%s fill=%s",
        order_id,
        linked_workflow_id,
        sym,
        side,
        qty,
        fill_price,
    )
    return {
        "order_id": order_id,
        "workflow_id": linked_workflow_id,
        "symbol": sym,
        "side": side.upper(),
        "qty": qty,
        "fill_price": fill_price,
        "status": "FILLED",
    }


def db_get_workflow(workflow_id: str) -> Dict[str, Any]:
    row = fetchone(
        "SELECT workflow_id, status, payload, created_at, updated_at FROM workflows WHERE workflow_id = %s",
        (workflow_id,),
    )
    if not row:
        return {"error": "workflow not found", "workflow_id": workflow_id}
    result = dict(row)
    for key in ("created_at", "updated_at"):
        if result.get(key):
            result[key] = result[key].isoformat()
    return result


def db_list_audit(limit: int = 20) -> Dict[str, Any]:
    rows = fetchall(
        "SELECT audit_id, kind, ref_id, hash, correlation_id, created_at "
        "FROM audit_logs ORDER BY audit_id DESC LIMIT %s",
        (min(limit, 500),),
    )
    items = []
    for row in rows:
        item = dict(row)
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        items.append(item)
    return {"items": items, "count": len(items)}


TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "market.get_last_price": {
        "description": "Get the last known price for a symbol",
        "parameters": {"symbol": {"type": "string", "required": True}},
        "handler": market_get_last_price,
    },
    "risk.check_trade": {
        "description": "Check if a trade passes risk rules",
        "parameters": {
            "symbol": {"type": "string", "required": True},
            "side": {"type": "string", "required": True, "enum": ["BUY", "SELL"]},
            "qty": {"type": "number", "required": True},
        },
        "handler": risk_check_trade,
    },
    "oms.place_order": {
        "description": "Place a HITL-approved paper order",
        "parameters": {
            "symbol": {"type": "string", "required": True},
            "side": {"type": "string", "required": True, "enum": ["BUY", "SELL"]},
            "qty": {"type": "number", "required": True},
            "workflow_id": {"type": "string", "required": False},
        },
        "handler": oms_place_order,
    },
    "db.get_workflow": {
        "description": "Retrieve a workflow by ID",
        "parameters": {"workflow_id": {"type": "string", "required": True}},
        "handler": db_get_workflow,
    },
    "db.list_audit": {
        "description": "List recent audit log entries",
        "parameters": {"limit": {"type": "integer", "required": False, "default": 20}},
        "handler": db_list_audit,
    },
}


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"unknown tool: {tool_name}", "available": list(TOOL_REGISTRY.keys())}
    handler = TOOL_REGISTRY[tool_name]["handler"]
    return handler(**arguments)
