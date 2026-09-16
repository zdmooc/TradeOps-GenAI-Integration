from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from mcp import Client
from mcp.server.auth.provider import AccessToken

from services.decision_fusion.models import DecisionInput, ExecutionMode, ReviewDecision
from services.decision_fusion.policy import fuse_decision
from services.decision_fusion.store import InMemoryDecisionStore
from services.decision_fusion.workflow import open_case, review_case
from services.mcp_native.auth import NativeMcpAuthConfig, TradeOpsTokenVerifier
from services.mcp_native.governance import NativeMcpGovernor, NativeMcpPolicyError
from services.mcp_native.server import build_mcp, mcp
from services.security.identity import IdentityConfig


def _proposal(now: datetime):
    item = DecisionInput(
        symbol="IX.D.DAX.IFM.IP",
        direction="LONG",
        qty=2.0,
        entry=23500.0,
        stop=23450.0,
        targets=(23620.0,),
        timeframe="M15",
        regime="TREND_UP",
        pattern="BREAKOUT_RETEST",
        assessment_status="SUPPORTED",
        risk_status="ACCEPT",
        event_age_ms=500.0,
        max_freshness_ms=5000.0,
        evidence_quality=0.9,
        rr=2.4,
        historical_expectancy_r=0.2,
        historical_trade_count=80,
        evidence=("risk:accept", "pattern:confirmed"),
    )
    return fuse_decision(
        item,
        ExecutionMode.PAPER,
        now=now,
        proposal_id="r3-approved-workflow",
        correlation_id="r3-correlation",
    )


def _token(subject: str, scopes: list[str]) -> AccessToken:
    return AccessToken(
        token=f"token-{subject}",
        client_id=subject,
        subject=subject,
        scopes=scopes,
        resource="http://mcp-native:8017/mcp",
        claims={"roles": ["reviewer"] if "paper.execute" in scopes else ["agent"]},
    )


def test_static_token_verifier_maps_tradeops_identity(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AGENT_TOKEN", "agent-secret")
    monkeypatch.setenv("MCP_REVIEWER_TOKEN", "reviewer-secret")
    verifier = TradeOpsTokenVerifier(
        auth_config=NativeMcpAuthConfig(
            issuer_url="http://keycloak:8080/realms/tradeops",
            resource_url="http://mcp-native:8017/mcp",
        ),
        identity_config=IdentityConfig(mode="static"),
    )

    async def scenario() -> None:
        agent = await verifier.verify_token("agent-secret")
        assert agent is not None
        assert agent.subject == "agent-controller"
        assert "market.read" in agent.scopes
        assert "paper.execute" not in agent.scopes

        reviewer = await verifier.verify_token("reviewer-secret")
        assert reviewer is not None
        assert reviewer.subject == "human-reviewer"
        assert "paper.execute" in reviewer.scopes

        assert await verifier.verify_token("wrong") is None

    asyncio.run(scenario())


def test_secure_server_exposes_identity_and_hitl_tools_but_learning_server_does_not() -> None:
    async def scenario() -> None:
        async with Client(mcp, raise_exceptions=True) as learning_client:
            learning_names = {tool.name for tool in (await learning_client.list_tools()).tools}
            assert "oms.place_order" not in learning_names

        secure_server = build_mcp(secure=True)
        async with Client(secure_server, raise_exceptions=True) as secure_client:
            secure_names = {tool.name for tool in (await secure_client.list_tools()).tools}
            assert "security.whoami" in secure_names
            assert "oms.place_order" in secure_names

    asyncio.run(scenario())


def test_agent_scope_cannot_execute_approved_order() -> None:
    now = datetime.now(timezone.utc)
    store = InMemoryDecisionStore()
    pending = open_case(_proposal(now))
    store.create(pending)
    approved = review_case(
        pending,
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="approved after evidence review",
        now=now + timedelta(seconds=10),
    )
    store.save(approved)

    governor = NativeMcpGovernor(
        decision_store=store,
        executor=lambda tool, args: {"order_id": "never", **args},
        audit_fn=lambda **kwargs: "audit-test",
    )
    agent = _token("agent-controller", ["market.read", "risk.evaluate", "workflow.read"])

    with pytest.raises(NativeMcpPolicyError) as exc:
        governor.execute_approved_paper_order(
            workflow_id=approved.proposal.proposal_id,
            access_token=agent,
            now=now + timedelta(seconds=20),
        )
    assert exc.value.code == "FORBIDDEN"


def test_hitl_must_be_stored_server_side_and_order_arguments_are_derived() -> None:
    now = datetime.now(timezone.utc)
    store = InMemoryDecisionStore()
    pending = open_case(_proposal(now))
    store.create(pending)
    reviewer = _token(
        "human-reviewer",
        ["market.read", "risk.evaluate", "workflow.read", "audit.read", "paper.execute"],
    )
    calls: list[tuple[str, dict]] = []

    def fake_executor(tool: str, args: dict):
        calls.append((tool, dict(args)))
        return {"order_id": "order-r3", "status": "FILLED", **args}

    governor = NativeMcpGovernor(
        decision_store=store,
        executor=fake_executor,
        audit_fn=lambda **kwargs: "audit-test",
    )

    with pytest.raises(NativeMcpPolicyError) as exc:
        governor.execute_approved_paper_order(
            workflow_id=pending.proposal.proposal_id,
            access_token=reviewer,
            now=now + timedelta(seconds=5),
        )
    assert exc.value.code == "HUMAN_APPROVAL_REQUIRED"
    assert calls == []

    approved = review_case(
        pending,
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="approved after evidence review",
        now=now + timedelta(seconds=10),
    )
    store.save(approved)

    result = governor.execute_approved_paper_order(
        workflow_id=approved.proposal.proposal_id,
        access_token=reviewer,
        now=now + timedelta(seconds=20),
    )
    assert result["order_id"] == "order-r3"
    assert len(calls) == 1
    tool, args = calls[0]
    assert tool == "oms.place_order"
    assert args == {
        "symbol": "IX.D.DAX.IFM.IP",
        "side": "BUY",
        "qty": 2.0,
        "workflow_id": "r3-approved-workflow",
    }
