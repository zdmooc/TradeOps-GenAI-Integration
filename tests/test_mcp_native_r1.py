"""R1 native MCP protocol tests.

These tests use the official MCP Client directly against the MCPServer object in
memory. That proves protocol discovery and primitive invocation without needing
ports or Docker. HTTP/OAuth deployment evidence belongs to later iterations.
"""

from __future__ import annotations

import asyncio
import json

from mcp import Client

from services.mcp_native.server import mcp


def test_native_mcp_discovery_and_read_only_tools() -> None:
    async def scenario() -> None:
        async with Client(mcp, raise_exceptions=True) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            assert "market.get_last_price" in names
            assert "risk.check_trade" in names
            assert "oms.place_order" not in names

            price = await client.call_tool(
                "market.get_last_price", {"symbol": "CAC40"}
            )
            assert price.is_error is False
            assert price.structured_content is not None
            assert price.structured_content["symbol"] == "CAC40"

            risk = await client.call_tool(
                "risk.check_trade",
                {"symbol": "CAC40", "side": "BUY", "qty": 10.0},
            )
            assert risk.is_error is False
            assert risk.structured_content is not None
            assert risk.structured_content["passed"] is True

    asyncio.run(scenario())


def test_native_mcp_resource_and_prompt() -> None:
    async def scenario() -> None:
        async with Client(mcp, raise_exceptions=True) as client:
            resources = await client.list_resources()
            assert "tradeops://policy/risk" in {
                str(resource.uri) for resource in resources.resources
            }

            policy_result = await client.read_resource("tradeops://policy/risk")
            payload = json.loads(policy_result.contents[0].text)
            assert payload["authority"] == "deterministic"
            assert payload["rules"]["max_qty"] == 10000

            prompts = await client.list_prompts()
            assert "analyze_trade" in {prompt.name for prompt in prompts.prompts}

            prompt_result = await client.get_prompt(
                "analyze_trade",
                {"symbol": "CAC40", "side": "BUY", "qty": "10"},
            )
            assert prompt_result.messages
            text = prompt_result.messages[0].content.text
            assert "without executing" in text
            assert "risk.check_trade" in text

    asyncio.run(scenario())
