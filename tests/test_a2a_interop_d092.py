import asyncio

import pytest
from starlette.testclient import TestClient

from services.a2a_ops_agent.main import (
    A2APolicyError,
    OperationsAgentService,
    build_agent_card,
    build_app,
)


def test_agent_card_exposes_two_governed_payment_operations_skills():
    card = build_agent_card("http://a2a.example")
    assert card.supported_interfaces[0].protocol_binding == "JSONRPC"
    assert card.supported_interfaces[0].protocol_version == "1.0"
    assert {skill.id for skill in card.skills} == {
        "payment_mq_health",
        "payment_mq_queue_status",
    }


def test_allowed_investigation_agent_delegates_to_downstream_mcp_health():
    calls = {"count": 0}

    async def fake_health():
        calls["count"] += 1
        return {"status": "HEALTHY", "queueDepth": 0}

    async def fake_queue(_queue: str):
        raise AssertionError("queue provider should not be called")

    service = OperationsAgentService(
        allowed_peers=frozenset({"investigation-agent"}),
        health_provider=fake_health,
        queue_provider=fake_queue,
    )
    result = asyncio.run(
        service.execute(
            peer_id="investigation-agent",
            skill_id="payment_mq_health",
            query="check payments",
        )
    )

    assert calls["count"] == 1
    assert result["agent_id"] == "operations-agent"
    assert result["peer_id"] == "investigation-agent"
    assert result["source"] == "native-mcp"
    assert result["result"]["status"] == "HEALTHY"


def test_unknown_peer_is_denied_before_downstream_mcp():
    calls = {"count": 0}

    async def fake_health():
        calls["count"] += 1
        return {"status": "HEALTHY"}

    async def fake_queue(_queue: str):
        calls["count"] += 1
        return {"queue": _queue}

    service = OperationsAgentService(
        allowed_peers=frozenset({"investigation-agent"}),
        health_provider=fake_health,
        queue_provider=fake_queue,
    )

    with pytest.raises(A2APolicyError, match="A2A_PEER_DENIED"):
        asyncio.run(
            service.execute(
                peer_id="rogue-agent",
                skill_id="payment_mq_health",
                query="check payments",
            )
        )
    assert calls["count"] == 0


def test_unapproved_skill_is_denied():
    async def fake_health():
        return {"status": "HEALTHY"}

    async def fake_queue(_queue: str):
        return {"queue": _queue}

    service = OperationsAgentService(
        allowed_peers=frozenset({"investigation-agent"}),
        health_provider=fake_health,
        queue_provider=fake_queue,
    )

    with pytest.raises(A2APolicyError, match="A2A_SKILL_DENIED"):
        asyncio.run(
            service.execute(
                peer_id="investigation-agent",
                skill_id="restart_cluster",
                query="restart it",
            )
        )


def test_a2a_http_app_exposes_health_and_agent_card():
    app = build_app(public_url="http://a2a.example")
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["sdk_baseline"] == "a2a-sdk==1.1.5"
    assert health.json()["runtime_evidence"] == "PENDING"

    card = client.get("/.well-known/agent-card.json")
    assert card.status_code == 200
    payload = card.json()
    assert payload["name"] == "MayaBank Payment Operations Agent"
