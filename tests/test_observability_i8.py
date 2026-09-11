import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.common.metrics import install
from services.common.otel import (
    configure_tracing,
    correlation_scope,
    current_trace_id,
    inject_headers,
    inject_kafka_headers,
    kafka_carrier,
    start_span,
)
from services.decision_fusion.models import DecisionInput, ExecutionMode
from services.decision_fusion.policy import fuse_decision
from services.genai_api.llm import MockLLM, ObservedLLM, estimate_tokens


def _decision_input() -> DecisionInput:
    return DecisionInput(
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
        ml_score=0.7,
        ml_probability_status="CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC",
        evidence=("risk:accept", "pattern:confirmed"),
    )


def test_http_middleware_preserves_correlation_and_exposes_trace_id():
    app = FastAPI()
    install(app, "i8-test")

    @app.get("/ping")
    def ping():
        return {"ok": True}

    response = TestClient(app).get(
        "/ping", headers={"X-Correlation-ID": "corr-i8-http"}
    )
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "corr-i8-http"
    assert len(response.headers["X-Trace-ID"]) == 32


def test_w3c_trace_context_and_correlation_are_injected_into_headers():
    configure_tracing("i8-test")
    with correlation_scope("corr-i8-propagation"):
        with start_span("parent"):
            headers = inject_headers()
            assert headers["X-Correlation-ID"] == "corr-i8-propagation"
            assert headers["traceparent"].startswith("00-")
            assert len(current_trace_id()) == 32


def test_kafka_headers_preserve_traceparent_and_correlation():
    configure_tracing("i8-test")
    with correlation_scope("corr-i8-kafka"):
        with start_span("producer"):
            carrier = kafka_carrier(inject_kafka_headers())
    assert carrier["X-Correlation-ID"] == "corr-i8-kafka"
    assert carrier["traceparent"].startswith("00-")


def test_fusion_reuses_active_correlation_id():
    with correlation_scope("corr-i8-fusion"):
        proposal = fuse_decision(_decision_input(), ExecutionMode.SHADOW)
    assert proposal.correlation_id == "corr-i8-fusion"
    assert proposal.decision.value == "REVIEW_REQUIRED"


def test_llm_token_accounting_is_explicitly_estimated_and_deterministic():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2

    observed = ObservedLLM(MockLLM(), provider="mock", model="mock-model")
    output = asyncio.run(observed.complete("system", "user"))
    assert output.startswith("MOCK_LLM_RESPONSE")
