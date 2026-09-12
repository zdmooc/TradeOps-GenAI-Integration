from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from services.ml_signal_quality.contract import DEFAULT_FEATURE_NAMES
from services.model_serving.main import create_app
from services.model_serving.signal_quality import (
    PRODUCTION_QUALIFICATION,
    ServingIdentity,
    SignalQualityServingService,
)


class DummyModel:
    def predict_proba(self, matrix):
        values = np.asarray(matrix, dtype=float)
        score = np.clip(0.5 + values[:, 0] * 0.01, 0.0, 1.0)
        return np.column_stack([1.0 - score, score])


def instance(value: float = 1.0) -> dict[str, float]:
    return {name: value for name in DEFAULT_FEATURE_NAMES}


def service(mode: str = "LAB", qualification: str = "SCORE_ONLY"):
    return SignalQualityServingService(
        DummyModel(),
        ServingIdentity(
            model_name="tradeops-signal-quality",
            model_uri="models:/test/1",
            qualification=qualification,
            mode=mode,
        ),
    )


def test_feature_contract_is_served_in_canonical_order():
    result = service().predict([instance(1.0)])
    assert result[0]["quality_score"] == 0.51
    assert result[0]["probability_status"] == "SCORE_ONLY"


def test_missing_feature_fails_closed():
    row = instance()
    row.pop(DEFAULT_FEATURE_NAMES[0])
    try:
        service().predict([row])
    except ValueError as exc:
        assert "feature contract mismatch" in str(exc)
    else:
        raise AssertionError("missing feature must be rejected")


def test_extra_feature_fails_closed():
    row = instance()
    row["future_return"] = 1.0
    try:
        service().predict([row])
    except ValueError as exc:
        assert "feature contract mismatch" in str(exc)
    else:
        raise AssertionError("extra feature must be rejected")


def test_non_finite_feature_fails_closed():
    row = instance()
    row[DEFAULT_FEATURE_NAMES[0]] = float("nan")
    try:
        service().predict([row])
    except ValueError as exc:
        assert "non-finite" in str(exc)
    else:
        raise AssertionError("non-finite input must be rejected")


def test_production_rejects_synthetic_or_score_only_qualification():
    try:
        service(mode="PRODUCTION", qualification="CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC")
    except ValueError as exc:
        assert "real-market" in str(exc)
    else:
        raise AssertionError("synthetic calibration must not qualify for production")


def test_production_accepts_explicit_real_market_qualification():
    serving = service(mode="PRODUCTION", qualification=PRODUCTION_QUALIFICATION)
    assert serving.identity.mode == "PRODUCTION"


def test_api_readiness_and_predict_contract():
    app = create_app(service())
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        response = client.post(
            "/v1/models/tradeops-signal-quality:predict",
            json={"instances": [instance()]},
        )
        assert response.status_code == 200
        assert response.json()["predictions"][0]["quality_score"] == 0.51


def test_api_unknown_model_is_rejected():
    app = create_app(service())
    with TestClient(app) as client:
        response = client.post(
            "/v1/models/not-tradeops:predict",
            json={"instances": [instance()]},
        )
        assert response.status_code == 404


def test_api_metrics_are_exposed():
    app = create_app(service())
    with TestClient(app) as client:
        client.post(
            "/v1/models/tradeops-signal-quality:predict",
            json={"instances": [instance()]},
        )
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "tradeops_model_requests_total" in metrics.text
