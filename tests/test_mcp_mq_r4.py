from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AccessToken

from services.agent_controller.run import app
from services.mcp_native.auth import static_principals
from services.mcp_native.governance import NativeMcpGovernor, NativeMcpPolicyError
from services.mcp_native.mq_client import (
    MQ_TOOL_REGISTRY,
    MqOpsError,
    classify_payment_mq_health,
    execute_mq_tool,
    get_queue_status,
)


def _payload(*, request=0, response=0, dlq=0, backout=0, consumers=1):
    return {
        "qmgr": "QM.MAYABANK",
        "observed_at": "2026-09-16T10:00:00Z",
        "queues": [
            {
                "queue": "PAYMENT.REQUEST.Q",
                "current_depth": request,
                "maximum_depth": 1000,
                "depth_percent": request / 10,
                "open_input_count": consumers,
                "open_output_count": 1,
            },
            {
                "queue": "PAYMENT.RESPONSE.Q",
                "current_depth": response,
                "maximum_depth": 1000,
                "depth_percent": response / 10,
                "open_input_count": 0,
                "open_output_count": 1,
            },
            {
                "queue": "PAYMENT.DLQ",
                "current_depth": dlq,
                "maximum_depth": 1000,
                "depth_percent": dlq / 10,
                "open_input_count": 0,
                "open_output_count": 0,
            },
            {
                "queue": "PAYMENT.BACKOUT.Q",
                "current_depth": backout,
                "maximum_depth": 1000,
                "depth_percent": backout / 10,
                "open_input_count": 0,
                "open_output_count": 0,
            },
        ],
    }


def _token(*scopes: str) -> AccessToken:
    return AccessToken(
        token="test-token",
        client_id="agent-controller",
        scopes=list(scopes),
        subject="agent-controller",
    )


def test_healthy_payment_mq_flow() -> None:
    health = classify_payment_mq_health(_payload())
    assert health["status"] == "HEALTHY"
    assert health["summary"]["dlq_depth"] == 0
    assert health["reasons"] == []


def test_dlq_or_backout_is_degraded() -> None:
    health = classify_payment_mq_health(_payload(dlq=2, backout=1))
    assert health["status"] == "DEGRADED"
    assert "PAYMENT.DLQ contains messages" in health["reasons"]
    assert "PAYMENT.BACKOUT.Q contains messages" in health["reasons"]


def test_request_backlog_without_consumer_is_warning() -> None:
    health = classify_payment_mq_health(_payload(request=7, consumers=0))
    assert health["status"] == "WARNING"
    assert "PAYMENT.REQUEST.Q has messages but no open input consumer" in health["reasons"]


def test_request_queue_near_capacity_is_degraded() -> None:
    health = classify_payment_mq_health(_payload(request=850, consumers=1))
    assert health["status"] == "DEGRADED"
    assert health["summary"]["request_depth_percent"] == 85.0


def test_unknown_queue_fails_before_network_call() -> None:
    with pytest.raises(MqOpsError, match="queue is not allowed"):
        get_queue_status("SYSTEM.ADMIN.COMMAND.QUEUE")


def test_agent_static_identity_has_mq_read(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AGENT_TOKEN", "agent-token")
    principal = static_principals()["agent-token"]
    assert "mq.read" in principal.scopes
    assert "paper.execute" not in principal.scopes


def test_mq_tool_requires_mq_read_scope() -> None:
    governor = NativeMcpGovernor(audit_fn=lambda **_: "audit")
    with pytest.raises(NativeMcpPolicyError, match="FORBIDDEN"):
        governor.execute_read(
            tool_name="mq.get_queue_status",
            arguments={"queue": "PAYMENT.REQUEST.Q"},
            access_token=_token("market.read"),
            tool_registry=MQ_TOOL_REGISTRY,
            executor=lambda _name, _args: {"current_depth": 3},
        )


def test_mq_read_scope_can_invoke_governed_adapter() -> None:
    governor = NativeMcpGovernor(audit_fn=lambda **_: "audit")
    result = governor.execute_read(
        tool_name="mq.get_queue_status",
        arguments={"queue": "PAYMENT.REQUEST.Q"},
        access_token=_token("mq.read"),
        tool_registry=MQ_TOOL_REGISTRY,
        executor=lambda _name, args: {"queue": args["queue"], "current_depth": 3},
    )
    assert result == {"queue": "PAYMENT.REQUEST.Q", "current_depth": 3}


def test_health_tool_has_no_mutating_arguments() -> None:
    assert MQ_TOOL_REGISTRY["payments.get_mq_health"]["parameters"] == {}
    assert MQ_TOOL_REGISTRY["mq.get_queue_status"]["parameters"] == {
        "queue": {"type": "string", "required": True}
    }
    assert callable(execute_mq_tool)


def test_agent_controller_exposes_mq_health_via_mcp_host(monkeypatch) -> None:
    import services.agent_controller.mcp_routes as routes

    monkeypatch.setattr(
        routes,
        "get_payment_mq_health_sync",
        lambda: {
            "source": "ibm-mq",
            "qmgr": "QM.MAYABANK",
            "status": "HEALTHY",
            "reasons": [],
            "summary": {"request_depth": 0, "dlq_depth": 0},
        },
    )
    response = TestClient(app).get("/agent/mcp/mq/health")
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["source"] == "ibm-mq"
    assert payload["status"] == "HEALTHY"


def test_agent_controller_exposes_allowlisted_queue_via_mcp_host(monkeypatch) -> None:
    import services.agent_controller.mcp_routes as routes

    monkeypatch.setattr(
        routes,
        "get_mq_queue_status_sync",
        lambda queue: {
            "qmgr": "QM.MAYABANK",
            "queue": queue,
            "current_depth": 3,
            "maximum_depth": 1000,
        },
    )
    response = TestClient(app).get("/agent/mcp/mq/queues/PAYMENT.REQUEST.Q")
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["queue"] == "PAYMENT.REQUEST.Q"
    assert payload["current_depth"] == 3


def test_agent_controller_rejects_forbidden_queue_before_mcp(monkeypatch) -> None:
    import services.agent_controller.mcp_routes as routes

    def forbidden_rpc_call(queue):
        raise AssertionError("MCP must not be called for forbidden queues")

    monkeypatch.setattr(
        routes, "get_mq_queue_status_sync", forbidden_rpc_call
    )

    response = TestClient(app).get(
        "/agent/mcp/mq/queues/SYSTEM.ADMIN.COMMAND.QUEUE"
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "queue is not allowed"
