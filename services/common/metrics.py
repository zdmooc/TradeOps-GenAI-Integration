from __future__ import annotations

import re
import time

from fastapi import Request
from opentelemetry.trace import SpanKind, Status, StatusCode
from prometheus_client import Counter, Histogram

from .otel import configure_tracing, correlation_scope, current_trace_id, start_span

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["service", "method", "path", "status"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

_UUIDISH = re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}(?=/|$)")


def _metric_path(path: str) -> str:
    return _UUIDISH.sub("/{id}", path)


def install(app, service_name: str):
    configure_tracing(service_name)

    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next):
        started = time.perf_counter()
        path = _metric_path(request.url.path)
        inbound_correlation = request.headers.get("X-Correlation-ID")
        carrier = {key: value for key, value in request.headers.items()}
        status_code = 500
        with correlation_scope(inbound_correlation) as correlation_id:
            with start_span(
                f"{request.method} {path}",
                carrier=carrier,
                kind=SpanKind.SERVER,
                attributes={
                    "http.request.method": request.method,
                    "url.path": path,
                    "server.address": service_name,
                },
            ) as span:
                try:
                    response = await call_next(request)
                    status_code = response.status_code
                    span.set_attribute("http.response.status_code", status_code)
                    if status_code >= 500:
                        span.set_status(Status(StatusCode.ERROR))
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise
                finally:
                    elapsed = time.perf_counter() - started
                    http_requests_total.labels(
                        service=service_name,
                        method=request.method,
                        path=path,
                        status=str(status_code),
                    ).inc()
                    http_request_duration_seconds.labels(
                        service=service_name, method=request.method, path=path
                    ).observe(elapsed)
                response.headers["X-Correlation-ID"] = correlation_id
                trace_id = current_trace_id()
                if trace_id:
                    response.headers["X-Trace-ID"] = trace_id
                return response
