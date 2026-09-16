"""Native MCP v2 server for TradeOps.

R1 introduced the protocol primitives. R3 added the enterprise security boundary.
R4 adds read-only IBM MQ payment observability through a separate MayaBank MQ
adapter; the LLM never receives queue-manager credentials or arbitrary MQ access.
"""

from __future__ import annotations

import json

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

from services.mcp_native.auth import NativeMcpAuthConfig, TradeOpsTokenVerifier
from services.mcp_native.governance import NativeMcpGovernor
from services.mcp_native.mq_client import MQ_TOOL_REGISTRY, execute_mq_tool
from services.mcp_server.tools import market_get_last_price, risk_check_trade


def build_mcp(*, secure: bool = False, governor: NativeMcpGovernor | None = None) -> MCPServer:
    """Build a learning server or the secured HTTP resource server.

    In-memory tests deliberately use ``secure=False`` because MCP authorization is
    an HTTP concern. ``run()`` always uses ``secure=True``.
    """
    auth_config = NativeMcpAuthConfig.from_env()
    kwargs = {}
    if secure:
        kwargs = {
            "token_verifier": TradeOpsTokenVerifier(auth_config=auth_config),
            "auth": AuthSettings(
                issuer_url=AnyHttpUrl(auth_config.issuer_url),
                resource_server_url=AnyHttpUrl(auth_config.resource_url),
                validate_token_resource=True,
            ),
        }

    server = MCPServer("TradeOps Native MCP", **kwargs)
    native_governor = governor or NativeMcpGovernor()

    @server.tool(name="market.get_last_price")
    def get_last_price(symbol: str) -> dict[str, object]:
        """Return the latest demonstrator price for one symbol."""
        if not secure:
            return market_get_last_price(symbol)
        result = native_governor.execute_read(
            tool_name="market.get_last_price",
            arguments={"symbol": symbol},
            access_token=get_access_token(),
        )
        return dict(result)

    @server.tool(name="risk.check_trade")
    def check_trade(symbol: str, side: str, qty: float) -> dict[str, object]:
        """Evaluate a proposed trade against deterministic risk rules."""
        if not secure:
            return risk_check_trade(symbol, side, qty)
        result = native_governor.execute_read(
            tool_name="risk.check_trade",
            arguments={"symbol": symbol, "side": side, "qty": qty},
            access_token=get_access_token(),
        )
        return dict(result)

    @server.resource("tradeops://policy/risk", mime_type="application/json")
    def risk_policy_resource() -> str:
        """Describe the deterministic risk boundary used by TradeOps."""
        return json.dumps(
            {
                "policy": "tradeops-risk-policy",
                "authority": "deterministic",
                "rules": {
                    "max_qty": 10000,
                    "max_notional": 1000000,
                    "allowed_sides": ["BUY", "SELL"],
                },
                "important": "Agent or LLM output cannot override deterministic risk vetoes.",
            },
            sort_keys=True,
        )

    @server.prompt(name="analyze_trade")
    def analyze_trade_prompt(symbol: str, side: str, qty: float) -> str:
        """Create a reusable instruction for a governed trade assessment."""
        return (
            "Assess the proposed trade without executing it. "
            f"Symbol={symbol.upper()}, side={side.upper()}, qty={qty}. "
            "Use market.get_last_price and risk.check_trade. "
            "If deterministic risk rejects the trade, report VETO and do not suggest "
            "bypassing the control."
        )

    if secure:

        @server.tool(name="security.whoami")
        def whoami() -> dict[str, object]:
            """Return the caller identity propagated by the MCP bearer boundary."""
            token = get_access_token()
            if token is None:
                raise PermissionError("authenticated MCP request required")
            return {
                "subject": token.subject or token.client_id,
                "client_id": token.client_id,
                "scopes": sorted(token.scopes),
                "roles": sorted((token.claims or {}).get("roles", [])),
                "authn_method": (token.claims or {}).get("authn_method", "unknown"),
            }

        @server.tool(name="mq.get_queue_status")
        def get_mq_queue_status(queue: str) -> dict[str, object]:
            """Read one allow-listed MayaBank IBM MQ payment queue status."""
            result = native_governor.execute_read(
                tool_name="mq.get_queue_status",
                arguments={"queue": queue},
                access_token=get_access_token(),
                tool_registry=MQ_TOOL_REGISTRY,
                executor=execute_mq_tool,
            )
            return dict(result)

        @server.tool(name="payments.get_mq_health")
        def get_payment_mq_health() -> dict[str, object]:
            """Deterministically summarize the MayaBank payment MQ flow health."""
            result = native_governor.execute_read(
                tool_name="payments.get_mq_health",
                arguments={},
                access_token=get_access_token(),
                tool_registry=MQ_TOOL_REGISTRY,
                executor=execute_mq_tool,
            )
            return dict(result)

        @server.tool(name="oms.place_order")
        def place_approved_paper_order(workflow_id: str) -> dict[str, object]:
            """Execute exactly the PAPER order stored in an approved HITL workflow.

            The caller cannot supply symbol, side or quantity here; those parameters
            are derived server-side from the approved decision record.
            """
            return native_governor.execute_approved_paper_order(
                workflow_id=workflow_id,
                access_token=get_access_token(),
            )

    return server


# Backward-compatible in-memory learning/test object. HTTP auth is intentionally
# not applied here; the secured network server is built in run().
mcp = build_mcp(secure=False)


def run() -> None:
    """Run the secured native MCP resource server on Streamable HTTP."""
    secure_mcp = build_mcp(secure=True)
    secure_mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8017,
        json_response=True,
    )


if __name__ == "__main__":
    run()
