"""Small native MCP client used for manual learning/demo.

Run the server first:
    python -m services.mcp_native.server

Then run:
    python -m services.mcp_native.client_smoke
"""

from __future__ import annotations

import asyncio
import os

from mcp import Client


async def main() -> None:
    url = os.getenv("MCP_NATIVE_URL", "http://127.0.0.1:8017/mcp")
    async with Client(url) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        print("TOOLS:", [tool.name for tool in tools.tools])
        print("RESOURCES:", [str(resource.uri) for resource in resources.resources])
        print("PROMPTS:", [prompt.name for prompt in prompts.prompts])

        price = await client.call_tool("market.get_last_price", {"symbol": "CAC40"})
        print("PRICE:", price.structured_content)

        risk = await client.call_tool(
            "risk.check_trade",
            {"symbol": "CAC40", "side": "BUY", "qty": 10},
        )
        print("RISK:", risk.structured_content)

        policy = await client.read_resource("tradeops://policy/risk")
        print("POLICY:", policy.contents[0].text)

        prompt = await client.get_prompt(
            "analyze_trade",
            {"symbol": "CAC40", "side": "BUY", "qty": "10"},
        )
        print("PROMPT:", prompt.messages[0].content)


if __name__ == "__main__":
    asyncio.run(main())
