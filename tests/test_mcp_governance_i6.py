import time

from services.mcp_server.governance import (
    Principal,
    SlidingWindowRateLimiter,
    StaticTokenAuthenticator,
    ToolGovernor,
    ToolPolicy,
    redact_sensitive,
)


REGISTRY = {
    "market.get_last_price": {
        "parameters": {"symbol": {"type": "string", "required": True}}
    },
    "risk.check_trade": {
        "parameters": {
            "symbol": {"type": "string", "required": True},
            "side": {"type": "string", "required": True, "enum": ["BUY", "SELL"]},
            "qty": {"type": "number", "required": True},
        }
    },
    "oms.place_order": {
        "parameters": {
            "symbol": {"type": "string", "required": True},
            "side": {"type": "string", "required": True, "enum": ["BUY", "SELL"]},
            "qty": {"type": "number", "required": True},
        }
    },
}


def _agent():
    return Principal("agent", frozenset({"market.read", "risk.evaluate"}))


def _reviewer():
    return Principal("reviewer", frozenset({"paper.execute"}))


def test_authenticator_assigns_scopes_server_side():
    auth = StaticTokenAuthenticator({"agent-token": _agent()})
    assert auth.authenticate("agent-token") == _agent()
    assert auth.authenticate("unknown") is None


def test_unauthenticated_call_is_denied():
    decision = ToolGovernor().authorize(
        tool_name="market.get_last_price",
        arguments={"symbol": "DAX"},
        principal=None,
        tool_registry=REGISTRY,
        human_approved=False,
    )
    assert decision.allowed is False
    assert decision.code == "UNAUTHENTICATED"


def test_missing_scope_is_denied():
    decision = ToolGovernor().authorize(
        tool_name="oms.place_order",
        arguments={"symbol": "DAX", "side": "BUY", "qty": 1},
        principal=_agent(),
        tool_registry=REGISTRY,
        human_approved=True,
    )
    assert decision.code == "FORBIDDEN"


def test_unknown_tool_is_denied():
    decision = ToolGovernor().authorize(
        tool_name="shell.exec",
        arguments={},
        principal=_agent(),
        tool_registry=REGISTRY,
        human_approved=False,
    )
    assert decision.code == "TOOL_NOT_ALLOWED"


def test_unknown_argument_is_denied():
    decision = ToolGovernor().authorize(
        tool_name="market.get_last_price",
        arguments={"symbol": "DAX", "command": "rm -rf /"},
        principal=_agent(),
        tool_registry=REGISTRY,
        human_approved=False,
    )
    assert decision.code == "INVALID_ARGUMENTS"


def test_invalid_enum_and_non_positive_qty_are_denied():
    governor = ToolGovernor()
    invalid_side = governor.authorize(
        tool_name="risk.check_trade",
        arguments={"symbol": "DAX", "side": "HOLD", "qty": 1},
        principal=_agent(),
        tool_registry=REGISTRY,
        human_approved=False,
    )
    invalid_qty = governor.authorize(
        tool_name="risk.check_trade",
        arguments={"symbol": "DAX", "side": "BUY", "qty": 0},
        principal=_agent(),
        tool_registry=REGISTRY,
        human_approved=False,
    )
    assert invalid_side.code == "INVALID_ARGUMENTS"
    assert invalid_qty.code == "INVALID_ARGUMENTS"


def test_paper_order_requires_human_approval():
    decision = ToolGovernor().authorize(
        tool_name="oms.place_order",
        arguments={"symbol": "DAX", "side": "BUY", "qty": 1},
        principal=_reviewer(),
        tool_registry=REGISTRY,
        human_approved=False,
    )
    assert decision.code == "HUMAN_APPROVAL_REQUIRED"


def test_reviewer_with_approval_can_reach_paper_tool():
    result = ToolGovernor().execute(
        tool_name="oms.place_order",
        arguments={"symbol": "DAX", "side": "BUY", "qty": 1},
        principal=_reviewer(),
        tool_registry=REGISTRY,
        human_approved=True,
        executor=lambda name, args: {"tool": name, "qty": args["qty"]},
    )
    assert result.allowed is True
    assert result.result["qty"] == 1


def test_rate_limit_is_enforced():
    now = [100.0]
    limiter = SlidingWindowRateLimiter(now_fn=lambda: now[0])
    governor = ToolGovernor(
        policies={
            "market.get_last_price": ToolPolicy(
                frozenset({"market.read"}), max_calls_per_minute=1
            )
        },
        rate_limiter=limiter,
    )
    first = governor.authorize(
        tool_name="market.get_last_price",
        arguments={"symbol": "DAX"},
        principal=_agent(),
        tool_registry=REGISTRY,
        human_approved=False,
    )
    second = governor.authorize(
        tool_name="market.get_last_price",
        arguments={"symbol": "DAX"},
        principal=_agent(),
        tool_registry=REGISTRY,
        human_approved=False,
    )
    assert first.allowed is True
    assert second.code == "RATE_LIMITED"


def test_sensitive_values_are_redacted_recursively():
    payload = {
        "api_key": "secret",
        "nested": {"authorization": "Bearer abc", "safe": "ok"},
    }
    redacted = redact_sensitive(payload)
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["authorization"] == "***REDACTED***"
    assert redacted["nested"]["safe"] == "ok"


def test_timeout_fails_closed():
    governor = ToolGovernor(
        policies={
            "market.get_last_price": ToolPolicy(
                frozenset({"market.read"}), timeout_seconds=0.001
            )
        }
    )

    def slow_executor(name, args):
        time.sleep(0.02)
        return {"name": name, "args": args}

    result = governor.execute(
        tool_name="market.get_last_price",
        arguments={"symbol": "DAX"},
        principal=_agent(),
        tool_registry=REGISTRY,
        human_approved=False,
        executor=slow_executor,
    )
    assert result.allowed is False
    assert result.code == "TIMEOUT"
