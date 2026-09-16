"""Native MCP client boundary used by the Agent Controller.

R3 adds authenticated Streamable HTTP for network calls. The Agent Controller uses
an agent token for read/evaluate tools and a reviewer token only for the final
HITL-approved paper-order tool.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


class McpContextError(RuntimeError):
    """Raised when the native MCP boundary cannot provide a valid context."""


class StaticBearerAuth(httpx2.Auth):
    """Attach one already-issued bearer token to MCP HTTP requests."""

    def __init__(self, token: str) -> None:
        self.token = token

    def auth_flow(self, request: httpx2.Request) -> Generator[httpx2.Request, httpx2.Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


def _target() -> str:
    return os.getenv("MCP_NATIVE_URL", "http://mcp-native:8017/mcp")


def _agent_token() -> str:
    if os.getenv("TRADEOPS_AUTH_MODE", "static").strip().lower() == "oidc":
        return os.getenv("OIDC_AGENT_ACCESS_TOKEN", "").strip()
    return os.getenv("MCP_AGENT_TOKEN", "").strip()


def _reviewer_token() -> str:
    if os.getenv("TRADEOPS_AUTH_MODE", "static").strip().lower() == "oidc":
        return os.getenv("OIDC_REVIEWER_ACCESS_TOKEN", "").strip()
    return os.getenv("MCP_REVIEWER_TOKEN", "").strip()


@asynccontextmanager
async def _client(
    target: Any | None = None,
    *,
    token: str | None = None,
) -> AsyncIterator[Client]:
    """Open an in-memory test client or an authenticated HTTP MCP client."""
    resolved = target or _target()
    if not isinstance(resolved, str):
        async with Client(resolved, raise_exceptions=True) as client:
            yield client
        return

    bearer = (token or _agent_token()).strip()
    if not bearer:
        raise McpContextError("MCP bearer token is not configured")

    auth = StaticBearerAuth(bearer)
    async with httpx2.AsyncClient(auth=auth) as http_client:
        transport = streamable_http_client(resolved, http_client=http_client)
        async with Client(transport, raise_exceptions=True) as client:
            yield client


async def discover_capabilities(target: Any | None = None) -> dict[str, list[str]]:
    """Discover native MCP tools/resources/prompts from the Agent Controller side."""
    async with _client(target) as client:
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

    async with _client(target, token=_agent_token() if isinstance(target or _target(), str) else None) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        required = {"market.get_last_price", "risk.check_trade"}
        missing = sorted(required - names)
        if missing:
            raise McpContextError(f"required MCP tools are missing: {', '.join(missing)}")

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


async def execute_approved_paper(workflow_id: str, target: Any | None = None) -> dict[str, Any]:
    """Invoke the native mutating tool with the reviewer identity only."""
    token = _reviewer_token()
    if not token and isinstance(target or _target(), str):
        raise McpContextError("reviewer MCP bearer token is not configured")
    async with _client(target, token=token or None) as client:
        result = await client.call_tool("oms.place_order", {"workflow_id": workflow_id})
        payload = result.structured_content
        if not isinstance(payload, dict) or not payload.get("order_id"):
            raise McpContextError("native MCP paper execution returned invalid result")
        return payload


def discover_capabilities_sync(target: Any | None = None) -> dict[str, list[str]]:
    return asyncio.run(discover_capabilities(target))


def get_trade_context_sync(
    symbol: str,
    side: str,
    qty: float,
    target: Any | None = None,
) -> dict[str, Any]:
    return asyncio.run(get_trade_context(symbol=symbol, side=side, qty=qty, target=target))


def execute_approved_paper_sync(workflow_id: str, target: Any | None = None) -> dict[str, Any]:
    return asyncio.run(execute_approved_paper(workflow_id=workflow_id, target=target))
