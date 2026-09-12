from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from starlette.responses import PlainTextResponse

from .signal_quality import SignalQualityServingService, load_service_from_environment


class PredictRequest(BaseModel):
    instances: list[dict[str, float]] = Field(min_length=1, max_length=1024)


def create_app(service: SignalQualityServingService | None = None) -> FastAPI:
    registry = CollectorRegistry()
    requests = Counter(
        "tradeops_model_requests_total",
        "Model-serving requests",
        ["status"],
        registry=registry,
    )
    latency = Histogram(
        "tradeops_model_request_seconds",
        "Model-serving request latency",
        registry=registry,
    )
    state: dict[str, Any] = {"service": service, "error": None}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if state["service"] is None:
            try:
                state["service"] = load_service_from_environment()
            except (RuntimeError, TypeError, ValueError) as exc:
                state["error"] = str(exc)
        yield

    app = FastAPI(
        title="TradeOps Signal Quality Model Serving",
        version="i10-v1",
        lifespan=lifespan,
    )

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "UP"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        loaded = state["service"]
        if loaded is None:
            raise HTTPException(status_code=503, detail=state["error"] or "model not loaded")
        return {
            "status": "READY",
            "model": loaded.identity.model_name,
            "qualification": loaded.identity.qualification,
            "mode": loaded.identity.mode,
        }

    @app.post("/v1/models/{model_name}:predict")
    def predict(model_name: str, request: PredictRequest) -> dict[str, Any]:
        loaded = state["service"]
        if loaded is None:
            requests.labels(status="unavailable").inc()
            raise HTTPException(status_code=503, detail=state["error"] or "model not loaded")
        if model_name != loaded.identity.model_name:
            requests.labels(status="not_found").inc()
            raise HTTPException(status_code=404, detail="unknown model")
        started = perf_counter()
        try:
            predictions = loaded.predict(request.instances)
        except (TypeError, ValueError) as exc:
            requests.labels(status="invalid").inc()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        latency.observe(perf_counter() - started)
        requests.labels(status="ok").inc()
        return {
            "model_name": loaded.identity.model_name,
            "model_uri": loaded.identity.model_uri,
            "predictions": predictions,
        }

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(registry).decode("utf-8"))

    return app


app = create_app()
