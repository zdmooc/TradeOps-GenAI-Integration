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

# ── In-memory price cache ────────────────────────────────────────────
_price_cache: Dict[str, Dict[str, Any]] = {}


def _synthetic_price(symbol: str) -> float:
    """Same logic as market-data service for consistency."""
    return 100 + (hash(symbol.upper()) % 1000) / 10.0


# ── Tool implementations ─────────────────────────────────────────────

def market_get_last_price(symbol: str) -> Dict[str, Any]:
    """Return last known price for a symbol (synthetic in demo mode)."""
    sym = symbol.upper()
    price = _synthetic_price(sym)
    ts = datetime.now(timezone.utc).isoformat()
    _price_cache[sym] = {"symbol": sym, "last": price, "ts": ts}
    return {"symbol": sym, "last": price, "ts": ts}


def risk_check_trade(symbol: str, side: str, qty: float) -> Dict[str, Any]:
    """Check if a trade passes basic risk rules (demo)."""
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

    passed = len(violations) == 0
    return {
        "symbol": sym,
        "side": side.upper(),
        "qty": qty,
        "notional": round(notional, 2),
        "passed": passed,
        "violations": violations,
    }


def oms_place_order(symbol: str, side: str, qty: float) -> Dict[str, Any]:
    """Place a paper order (writes to orders table, status=FILLED immediately in demo)."""
    sym = symbol.upper()
    order_id = str(uuid.uuid4())
    fill_price = _synthetic_price(sym)

    # We need a workflow_id – in demo mode we create a placeholder if none exists
    # The agent controller will provide the real workflow_id via the MCP call context
    execute(
        "INSERT INTO orders(order_id, workflow_id, status, symbol, side, qty, fill_price) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (order_id, str(uuid.uuid4()), "FILLED", sym, side.upper(), qty, fill_price),
    )

    log.info("paper order placed order_id=%s symbol=%s side=%s qty=%s fill=%s",
             order_id, sym, side, qty, fill_price)

    return {
        "order_id": order_id,
        "symbol": sym,
        "side": side.upper(),
        "qty": qty,
        "fill_price": fill_price,
        "status": "FILLED",
    }


def db_get_workflow(workflow_id: str) -> Dict[str, Any]:
    """Retrieve a workflow by ID."""
    row = fetchone(
        "SELECT workflow_id, status, payload, created_at, updated_at "
        "FROM workflows WHERE workflow_id = %s",
        (workflow_id,),
    )
    if not row:
        return {"error": "workflow not found", "workflow_id": workflow_id}
    # Convert to serialisable dict
    result = dict(row)
    for k in ("created_at", "updated_at"):
        if result.get(k):
            result[k] = result[k].isoformat()
    if isinstance(result.get("payload"), dict):
        pass  # already dict from RealDictCursor
    return result


def db_list_audit(limit: int = 20) -> Dict[str, Any]:
    """List recent audit log entries."""
    rows = fetchall(
        "SELECT audit_id, kind, ref_id, hash, correlation_id, created_at "
        "FROM audit_logs ORDER BY audit_id DESC LIMIT %s",
        (min(limit, 500),),
    )
    items = []
    for r in rows:
        item = dict(r)
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        items.append(item)
    return {"items": items, "count": len(items)}


# ── Registry ─────────────────────────────────────────────────────────

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
        "description": "Place a paper order (demo – fills immediately)",
        "parameters": {
            "symbol": {"type": "string", "required": True},
            "side": {"type": "string", "required": True, "enum": ["BUY", "SELL"]},
            "qty": {"type": "number", "required": True},
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
    """Dispatch a tool call to the appropriate handler."""
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"unknown tool: {tool_name}", "available": list(TOOL_REGISTRY.keys())}
    handler = TOOL_REGISTRY[tool_name]["handler"]
    return handler(**arguments)
