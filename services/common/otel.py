from __future__ import annotations

import os
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Mapping, MutableMapping

from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind

_correlation_id: ContextVar[str | None] = ContextVar("tradeops_correlation_id", default=None)
_config_lock = threading.Lock()
_configured = False


def configure_tracing(service_name: str) -> None:
    """Configure one process-wide SDK provider and optional OTLP/HTTP export."""
    global _configured
    if _configured:
        return
    with _config_lock:
        if _configured:
            return
        provider = trace.get_tracer_provider()
        if not hasattr(provider, "add_span_processor"):
            provider = TracerProvider(
                resource=Resource.create(
                    {
                        "service.name": service_name,
                        "service.namespace": os.getenv(
                            "OTEL_SERVICE_NAMESPACE", "tradeops"
                        ),
                        "deployment.environment.name": os.getenv("ENV", "local"),
                    }
                )
            )
            trace.set_tracer_provider(provider)

        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        if endpoint and hasattr(provider, "add_span_processor"):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            trace_endpoint = endpoint.rstrip("/")
            if not trace_endpoint.endswith("/v1/traces"):
                trace_endpoint += "/v1/traces"
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=trace_endpoint))
            )
        _configured = True


def tracer(name: str = "tradeops"):
    return trace.get_tracer(name)


def current_correlation_id() -> str | None:
    return _correlation_id.get()


def ensure_correlation_id(value: str | None = None) -> str:
    cleaned = (value or "").strip()
    return cleaned[:128] if cleaned else str(uuid.uuid4())


@contextmanager
def correlation_scope(value: str | None = None) -> Iterator[str]:
    correlation_id = ensure_correlation_id(value)
    token = _correlation_id.set(correlation_id)
    try:
        yield correlation_id
    finally:
        _correlation_id.reset(token)


def current_trace_id() -> str:
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return ""
    return f"{context.trace_id:032x}"


def current_span_id() -> str:
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return ""
    return f"{context.span_id:016x}"


def extract_context(carrier: Mapping[str, str] | None):
    return propagate.extract(dict(carrier or {}))


def inject_headers(headers: MutableMapping[str, str] | None = None) -> dict[str, str]:
    carrier: dict[str, str] = dict(headers or {})
    propagate.inject(carrier)
    correlation_id = current_correlation_id()
    if correlation_id:
        carrier["X-Correlation-ID"] = correlation_id
    return carrier


def inject_kafka_headers() -> list[tuple[str, bytes]]:
    carrier = inject_headers()
    return [(key, value.encode("utf-8")) for key, value in carrier.items()]


def kafka_carrier(headers: list[tuple[str, bytes]] | None) -> dict[str, str]:
    return {
        key: value.decode("utf-8", errors="replace")
        for key, value in (headers or [])
        if value is not None
    }


@contextmanager
def start_span(
    name: str,
    *,
    attributes: Mapping[str, Any] | None = None,
    carrier: Mapping[str, str] | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Iterator[Any]:
    context = extract_context(carrier) if carrier is not None else None
    with tracer().start_as_current_span(name, context=context, kind=kind) as span:
        for key, value in (attributes or {}).items():
            if value is not None:
                span.set_attribute(key, value)
        correlation_id = current_correlation_id()
        if correlation_id:
            span.set_attribute("tradeops.correlation_id", correlation_id)
        yield span
