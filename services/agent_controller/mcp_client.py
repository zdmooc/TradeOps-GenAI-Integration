"""Native MCP client boundary used by the Agent Controller.

R2 turns the Agent Controller into an MCP Host without exposing mutating tools.
The client discovers capabilities and invokes the read/evaluate tools published by
services.mcp_native.server.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from mcp import Client


class McpContextError(RuntimeError):
    """Raised when the native MCP boundary cannot provide a valid context."""


def _target() -> str:
    return os.getenv("MCP_NATIVE_URL", "http://mcp-native:8017/mcp")


async def discover_capabilities(target: Any | None = None) -> dict[str, list[str]]:
    """Discover native MCP tools/resources/prompts from the Agent Controller side."""
    async with Client(target or _target(), raise_exceptions=True) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        return {
            "tools": sorted(tool.name for tool in tools.tools),
            "resources": sorted(str(resource.uri) for resource in resources.resources),
            "prompts": sorted(prompt.name for prompt in prompts.prompts),
        }


async def get_trade_context(
    symbol: str,
    side: str,
    qty: float,
    target: Any | None = None,
) -> dict[str, Any]:
    """Build a read-only market/risk context through the native MCP protocol."""
    symbol = symbol.upper()
    side = side.upper()

    async with Client(target or _target(), raise_exceptions=True) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        required = {"market.get_last_price", "risk.check_trade"}
        missing = sorted(required - names)
        if missing:
            raise McpContextError(f"required MCP tools are missing: {', '.join(missing)}")
        if "oms.place_order" in names:
            raise McpContextError("R2 fail-closed: mutating oms.place_order must not be exposed")

        price_result = await client.call_tool(
            "market.get_last_price",
            {"symbol": symbol},
        )
        risk_result = await client.call_tool(
            "risk.check_trade",
            {"symbol": symbol, "side": side, "qty": qty},
        )

        price = price_result.structured_content
        risk = risk_result.structured_content
        if not isinstance(price, dict):
            raise McpContextError("market.get_last_price returned invalid structured content")
        if not isinstance(risk, dict):
            raise McpContextError("risk.check_trade returned invalid structured content")

        return {
            "source": "native-mcp",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "market": price,
            "risk": risk,
            "risk_status": "ACCEPT" if bool(risk.get("passed")) else "VETO",
            "risk_reasons": list(risk.get("violations") or []),
            "tools_used": ["market.get_last_price", "risk.check_trade"],
        }


def discover_capabilities_sync(target: Any | None = None) -> dict[str, list[str]]:
    """Synchronous adapter for FastAPI sync handlers and CLI/demo use."""
    return asyncio.run(discover_capabilities(target))


def get_trade_context_sync(
    symbol: str,
    side: str,
    qty: float,
    target: Any | None = None,
) -> dict[str, Any]:
    """Synchronous adapter around get_trade_context()."""
    return asyncio.run(get_trade_context(symbol=symbol, side=side, qty=qty, target=target))
