"""Native MCP v2 server for the TradeOps demonstrator.

R1 teaches and proves the three MCP server primitives without replacing the
existing governed HTTP boundary:

- tools: model-invoked capabilities;
- resources: application-provided context;
- prompts: reusable user/application-selected prompt templates.

Only read/evaluate capabilities are exposed in R1. Mutating capabilities such
as paper order placement remain on the governed legacy boundary until OAuth,
identity propagation and HITL are wired into the native MCP path in R2.
"""

from __future__ import annotations

import json

from mcp.server import MCPServer

from services.mcp_server.tools import market_get_last_price, risk_check_trade

mcp = MCPServer("TradeOps Native MCP")


@mcp.tool(name="market.get_last_price")
def get_last_price(symbol: str) -> dict[str, object]:
    """Return the latest demonstrator price for one symbol."""
    return market_get_last_price(symbol)


@mcp.tool(name="risk.check_trade")
def check_trade(symbol: str, side: str, qty: float) -> dict[str, object]:
    """Evaluate a proposed trade against deterministic demonstrator risk rules."""
    return risk_check_trade(symbol, side, qty)


@mcp.resource("tradeops://policy/risk", mime_type="application/json")
def risk_policy_resource() -> str:
    """Describe the deterministic risk boundary used by the R1 MCP tools."""
    return json.dumps(
        {
            "policy": "tradeops-r1-risk-policy",
            "authority": "deterministic",
            "rules": {
                "max_qty": 10000,
                "max_notional": 1000000,
                "allowed_sides": ["BUY", "SELL"],
            },
            "important": (
                "Agent or LLM output cannot override deterministic risk vetoes."
            ),
        },
        sort_keys=True,
    )


@mcp.prompt(name="analyze_trade")
def analyze_trade_prompt(symbol: str, side: str, qty: float) -> str:
    """Create a reusable instruction for a governed trade assessment."""
    return (
        "Assess the proposed trade without executing it. "
        f"Symbol={symbol.upper()}, side={side.upper()}, qty={qty}. "
        "Use market.get_last_price and risk.check_trade. "
        "If deterministic risk rejects the trade, report VETO and do not suggest "
        "bypassing the control."
    )


def run() -> None:
    """Run the native MCP endpoint using Streamable HTTP on port 8017."""
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8017,
        json_response=True,
    )


if __name__ == "__main__":
    run()
