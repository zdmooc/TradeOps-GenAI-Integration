from fastapi.testclient import TestClient

import services.agent_controller.main as controller
from services.decision_fusion.store import InMemoryDecisionStore


def _proposal_payload(execution_mode: str = "SHADOW") -> dict:
    return {
        "symbol": "IX.D.DAX.IFM.IP",
        "direction": "LONG",
        "qty": 2.0,
        "entry": 23500.0,
        "stop": 23450.0,
        "targets": [23620.0],
        "timeframe": "M15",
        "regime": "TREND_UP",
        "pattern": "BREAKOUT_RETEST",
        "assessment_status": "SUPPORTED",
        "risk_status": "ACCEPT",
        "event_age_ms": 500.0,
        "max_freshness_ms": 5000.0,
        "evidence_quality": 0.9,
        "rr": 2.4,
        "historical_expectancy_r": 0.2,
        "historical_trade_count": 80,
        "ml_score": 0.7,
        "ml_probability_status": "CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC",
        "evidence": ["risk:accept", "pattern:confirmed"],
        "execution_mode": execution_mode,
    }


def _configure(monkeypatch):
    monkeypatch.setenv("MCP_AGENT_TOKEN", "agent-test-token")
    monkeypatch.setenv("MCP_REVIEWER_TOKEN", "reviewer-test-token")
    monkeypatch.setattr(controller, "_decision_store", InMemoryDecisionStore())
    monkeypatch.setattr(controller, "_audit", lambda *args, **kwargs: "audit-hash")
    return TestClient(controller.app)


def test_propose_requires_agent_identity(monkeypatch):
    client = _configure(monkeypatch)
    response = client.post("/decision/propose", json=_proposal_payload())
    assert response.status_code == 401


def test_shadow_hitl_api_requires_reviewer_and_executes_without_order(monkeypatch):
    client = _configure(monkeypatch)
    proposal_response = client.post(
        "/decision/propose",
        json=_proposal_payload("SHADOW"),
        headers={"Authorization": "Bearer agent-test-token"},
    )
    assert proposal_response.status_code == 200
    case = proposal_response.json()["case"]
    assert case["status"] == "PENDING_REVIEW"
    assert case["proposal"]["decision"] == "REVIEW_REQUIRED"
    proposal_id = case["proposal"]["proposal_id"]

    agent_review = client.post(
        f"/decision/{proposal_id}/review",
        json={"decision": "APPROVE", "rationale": "evidence checked"},
        headers={"Authorization": "Bearer agent-test-token"},
    )
    assert agent_review.status_code == 401

    review_response = client.post(
        f"/decision/{proposal_id}/review",
        json={"decision": "APPROVE", "rationale": "evidence checked"},
        headers={"Authorization": "Bearer reviewer-test-token"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["case"]["status"] == "APPROVED"

    execute_response = client.post(
        f"/decision/{proposal_id}/execute",
        headers={"Authorization": "Bearer reviewer-test-token"},
    )
    assert execute_response.status_code == 200
    executed = execute_response.json()["case"]
    assert executed["status"] == "EXECUTED_SHADOW"
    assert executed["execution_result"]["status"] == "RECORDED"

    duplicate = client.post(
        f"/decision/{proposal_id}/execute",
        headers={"Authorization": "Bearer reviewer-test-token"},
    )
    assert duplicate.status_code == 409


def test_paper_hitl_api_preserves_proposal_to_order_lineage(monkeypatch):
    client = _configure(monkeypatch)

    def fake_paper(case):
        return {
            "order_id": "paper-order-1",
            "workflow_id": case.proposal.proposal_id,
            "status": "FILLED",
        }

    monkeypatch.setattr(controller, "_execute_paper", fake_paper)
    proposal_response = client.post(
        "/decision/propose",
        json=_proposal_payload("PAPER"),
        headers={"Authorization": "Bearer agent-test-token"},
    )
    assert proposal_response.status_code == 200
    proposal_id = proposal_response.json()["case"]["proposal"]["proposal_id"]

    review_response = client.post(
        f"/decision/{proposal_id}/review",
        json={"decision": "APPROVE", "rationale": "paper execution approved"},
        headers={"Authorization": "Bearer reviewer-test-token"},
    )
    assert review_response.status_code == 200

    execute_response = client.post(
        f"/decision/{proposal_id}/execute",
        headers={"Authorization": "Bearer reviewer-test-token"},
    )
    assert execute_response.status_code == 200
    executed = execute_response.json()["case"]
    assert executed["status"] == "EXECUTED_PAPER"
    assert executed["execution_result"]["order_id"] == "paper-order-1"
    assert executed["execution_result"]["workflow_id"] == proposal_id
