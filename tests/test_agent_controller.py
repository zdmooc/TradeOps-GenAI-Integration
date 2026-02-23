"""Smoke tests for the Agent Controller (unit-level, no Docker needed)."""

from unittest.mock import patch


def test_agent_state_init():
    """AgentState initialises with correct defaults."""
    from services.agent_controller.graph import AgentState

    state = AgentState(
        symbol="AAPL",
        side="BUY",
        qty=100,
        reason="test",
        workflow_id="wf-1",
        correlation_id="corr-1",
    )
    assert state.symbol == "AAPL"
    assert state.decision == "DENY"
    assert state.confidence_score == 0.0


def test_node_plan_creates_plan():
    """node_plan populates state.plan and calls log_audit."""
    from services.agent_controller.graph import AgentState, node_plan

    state = AgentState(
        symbol="MSFT", side="SELL", qty=50, reason="rebalance",
        workflow_id="wf-2", correlation_id="corr-2",
    )
    with patch("services.agent_controller.graph.log_audit") as mock_audit:
        result = node_plan(state)
        assert result.plan["symbol"] == "MSFT"
        assert len(result.plan["steps"]) == 5
        mock_audit.assert_called_once()


def test_node_evaluate_high_confidence():
    """node_evaluate gives high confidence when risk passes."""
    from services.agent_controller.graph import AgentState, node_evaluate

    state = AgentState(
        symbol="AAPL", side="BUY", qty=100, reason="test",
        workflow_id="wf-3", correlation_id="corr-3",
    )
    state.risk_result = {"passed": True, "violations": []}
    state.rag_hits = [{"score": 0.85, "source": "test.md", "text": "rule"}]
    state.price_result = {"last": 150.0}

    with patch("services.agent_controller.graph.log_audit"):
        result = node_evaluate(state)
        assert result.confidence_score >= 0.7


def test_node_evaluate_low_confidence():
    """node_evaluate gives low confidence when risk fails."""
    from services.agent_controller.graph import AgentState, node_evaluate

    state = AgentState(
        symbol="AAPL", side="BUY", qty=50000, reason="test",
        workflow_id="wf-4", correlation_id="corr-4",
    )
    state.risk_result = {"passed": False, "violations": ["qty too high", "notional too high"]}
    state.rag_hits = []
    state.price_result = {"last": 150.0}

    with patch("services.agent_controller.graph.log_audit"):
        result = node_evaluate(state)
        assert result.confidence_score < 0.7


def test_node_decide_approve():
    """node_decide sets APPROVE when confidence >= threshold and risk passed."""
    from services.agent_controller.graph import AgentState, node_decide

    state = AgentState(
        symbol="AAPL", side="BUY", qty=100, reason="test",
        workflow_id="wf-5", correlation_id="corr-5",
    )
    state.confidence_score = 0.85
    state.risk_result = {"passed": True}

    with (
        patch("services.agent_controller.graph.execute"),
        patch("services.agent_controller.graph.log_audit"),
    ):
        result = node_decide(state)
        assert result.decision == "APPROVE"


def test_node_decide_needs_human():
    """node_decide sets NEEDS_HUMAN when confidence < threshold."""
    from services.agent_controller.graph import AgentState, node_decide

    state = AgentState(
        symbol="AAPL", side="BUY", qty=100, reason="test",
        workflow_id="wf-6", correlation_id="corr-6",
    )
    state.confidence_score = 0.5
    state.risk_result = {"passed": True}

    with (
        patch("services.agent_controller.graph.execute"),
        patch("services.agent_controller.graph.log_audit"),
    ):
        result = node_decide(state)
        assert result.decision == "NEEDS_HUMAN"


def test_health_endpoint():
    """GET /health returns 200."""
    from fastapi.testclient import TestClient
    from services.agent_controller.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
