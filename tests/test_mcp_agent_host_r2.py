"""R2 tests: Agent Controller acts as MCP Host for read/evaluate capabilities."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from services.agent_controller.mcp_client import discover_capabilities, get_trade_context
from services.agent_controller.run import app
from services.mcp_native.server import mcp


def test_agent_controller_can_discover_native_mcp_capabilities_in_process() -> None:
    async def scenario() -> None:
        capabilities = await discover_capabilities(mcp)
        assert "market.get_last_price" in capabilities["tools"]
        assert "risk.check_trade" in capabilities["tools"]
        assert "oms.place_order" not in capabilities["tools"]
        assert "tradeops://policy/risk" in capabilities["resources"]
        assert "analyze_trade" in capabilities["prompts"]

    asyncio.run(scenario())


def test_agent_controller_builds_read_only_trade_context_via_mcp() -> None:
    async def scenario() -> None:
        context = await get_trade_context("CAC40", "BUY", 10.0, mcp)
        assert context["source"] == "native-mcp"
        assert context["symbol"] == "CAC40"
        assert context["risk_status"] == "ACCEPT"
        assert context["tools_used"] == ["market.get_last_price", "risk.check_trade"]

    asyncio.run(scenario())


def test_agent_mcp_context_http_contract(monkeypatch) -> None:
    import services.agent_controller.mcp_routes as routes

    monkeypatch.setattr(
        routes,
        "get_trade_context_sync",
        lambda symbol, side, qty: {
            "source": "native-mcp",
            "symbol": symbol.upper(),
            "side": side.upper(),
            "qty": qty,
            "market": {"symbol": symbol.upper(), "last": 123.4},
            "risk": {"passed": True, "violations": []},
            "risk_status": "ACCEPT",
            "risk_reasons": [],
            "tools_used": ["market.get_last_price", "risk.check_trade"],
        },
    )

    client = TestClient(app)
    response = client.post(
        "/agent/mcp/context",
        json={"symbol": "cac40", "side": "BUY", "qty": 10},
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["source"] == "native-mcp"
    assert payload["risk_status"] == "ACCEPT"
    assert "order_id" not in payload
