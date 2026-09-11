from fastapi.testclient import TestClient

from services.agent_controller.main import app


def test_health_endpoint_reports_analysis_plus_hitl_langgraph():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode"] == "ANALYSIS_PLUS_HITL"
    assert payload["framework"] == "LangGraph"
    assert payload["execution"] == "SHADOW_OR_PAPER_AFTER_HUMAN_APPROVAL"


def test_autonomous_trade_endpoint_is_disabled():
    client = TestClient(app)
    response = client.post("/agent/trade")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AUTONOMOUS_EXECUTION_DISABLED"


def test_assessment_endpoint_returns_structured_analysis():
    client = TestClient(app)
    response = client.post(
        "/agent/assessment",
        json={
            "symbol": "DAX",
            "event_age_ms": 100,
            "market_direction": "LONG",
            "technical_structure": "BULLISH",
            "pattern_directions": ["LONG"],
            "macro_state": "RISK_ON",
            "risk_status": "ACCEPT",
            "rag_hits": [
                {
                    "source": "risk-policy.md",
                    "text": "Risk veto is terminal and cannot be overridden by agents.",
                    "score": 0.9,
                }
            ],
            "ml_score": 0.72,
            "ml_probability_status": "CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC",
        },
    )
    assert response.status_code == 200
    assessment = response.json()["assessment"]
    assert assessment["status"] == "SUPPORTED"
    assert assessment["direction"] == "LONG"
    assert assessment["execution_allowed"] is False
    assert assessment["decision_scope"] == "ANALYSIS_ONLY"


def test_assessment_endpoint_surfaces_conflict():
    client = TestClient(app)
    response = client.post(
        "/agent/assessment",
        json={
            "symbol": "DAX",
            "event_age_ms": 100,
            "market_direction": "LONG",
            "technical_structure": "BULLISH",
            "pattern_directions": ["SHORT"],
            "macro_state": "RISK_ON",
            "risk_status": "ACCEPT",
            "rag_hits": [],
        },
    )
    assert response.status_code == 200
    assert response.json()["assessment"]["status"] == "CONFLICT"
