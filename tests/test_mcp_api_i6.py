from unittest.mock import patch

from fastapi.testclient import TestClient

from services.mcp_server.main import app


def test_mcp_call_requires_authentication():
    client = TestClient(app)
    with patch("services.mcp_server.main.log_audit", return_value="hash"):
        response = client.post(
            "/call",
            json={
                "tool": "market.get_last_price",
                "arguments": {"symbol": "DAX"},
            },
        )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


def test_agent_token_can_use_read_tool(monkeypatch):
    monkeypatch.setenv("MCP_AGENT_TOKEN", "agent-secret")
    client = TestClient(app)
    with (
        patch("services.mcp_server.main.log_audit", return_value="hash"),
        patch(
            "services.mcp_server.main.execute_tool",
            return_value={"symbol": "DAX", "last": 100.0},
        ),
    ):
        response = client.post(
            "/call",
            headers={"Authorization": "Bearer agent-secret"},
            json={
                "tool": "market.get_last_price",
                "arguments": {"symbol": "DAX"},
                "purpose": "market assessment",
            },
        )
    assert response.status_code == 200
    assert response.json()["result"]["last"] == 100.0


def test_agent_token_cannot_execute_paper_order(monkeypatch):
    monkeypatch.setenv("MCP_AGENT_TOKEN", "agent-secret")
    client = TestClient(app)
    with patch("services.mcp_server.main.log_audit", return_value="hash"):
        response = client.post(
            "/call",
            headers={"Authorization": "Bearer agent-secret"},
            json={
                "tool": "oms.place_order",
                "arguments": {"symbol": "DAX", "side": "BUY", "qty": 1},
                "purpose": "attempted execution",
                "human_approved": True,
            },
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_reviewer_still_needs_explicit_human_approval(monkeypatch):
    monkeypatch.setenv("MCP_REVIEWER_TOKEN", "reviewer-secret")
    client = TestClient(app)
    with patch("services.mcp_server.main.log_audit", return_value="hash"):
        response = client.post(
            "/call",
            headers={"Authorization": "Bearer reviewer-secret"},
            json={
                "tool": "oms.place_order",
                "arguments": {"symbol": "DAX", "side": "BUY", "qty": 1},
                "purpose": "paper review",
                "human_approved": False,
            },
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "HUMAN_APPROVAL_REQUIRED"
