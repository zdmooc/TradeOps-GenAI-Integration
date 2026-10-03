from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

import httpx
from opentelemetry.trace import Status, StatusCode

from services.common.config import settings
from services.common.observability_metrics import (
    LLM_DURATION,
    LLM_ESTIMATED_COST_USD,
    LLM_REQUESTS,
    LLM_TOKENS_ESTIMATED,
)
from services.common.otel import start_span

from .ai_access import ClientCredentialsTokenProvider, StaticAccessTokenProvider


@dataclass(frozen=True, slots=True)
class LLMResult:
    text: str
    provider: str
    model: str
    consumer_id: str = "unknown"
    input_tokens: int | None = None
    output_tokens: int | None = None
    token_source: str = "estimated"


class LLM:
    async def complete_result(self, system: str, user: str) -> LLMResult:
        raise NotImplementedError

    async def complete(self, system: str, user: str) -> str:
        return (await self.complete_result(system=system, user=user)).text


class MockLLM(LLM):
    async def complete_result(self, system: str, user: str) -> LLMResult:
        text = (
            "MOCK_LLM_RESPONSE\n"
            "System: " + system[:120] + "\n"
            "User: " + user[:500] + "\n"
            "Conclusion: Revue générée en mode dégradé (mock)."
        )
        return LLMResult(
            text=text,
            provider="mock",
            model="mock",
            consumer_id="local-test",
            input_tokens=estimate_tokens(system) + estimate_tokens(user),
            output_tokens=estimate_tokens(text),
            token_source="estimated",
        )


class GatewayLLM(LLM):
    """OpenAI-compatible client for the governed AI gateway.

    The client never sends a consumer-id header. Consumer identity must be derived
    by the trusted gateway from authenticated workload identity.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model_alias: str,
        token_provider,
        timeout_seconds: float = 30.0,
        allowed_model_aliases: frozenset[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_alias = model_alias.strip()
        self.token_provider = token_provider
        self.timeout_seconds = timeout_seconds
        self.allowed_model_aliases = allowed_model_aliases or frozenset()
        self.transport = transport

    def _validate(self) -> None:
        if not self.base_url:
            raise RuntimeError("AI_GATEWAY_BASE_URL is required for gateway mode")
        if not self.model_alias:
            raise RuntimeError("AI_GATEWAY_MODEL_ALIAS is required for gateway mode")
        if (
            self.allowed_model_aliases
            and self.model_alias not in self.allowed_model_aliases
        ):
            raise PermissionError(
                f"AI_MODEL_NOT_ALLOWED: requested alias {self.model_alias!r}"
            )

    async def complete_result(self, system: str, user: str) -> LLMResult:
        self._validate()
        access_token = await self.token_provider.token()
        request_payload = {
            "model": self.model_alias,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self.transport
        ) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=request_payload,
                headers=headers,
            )
        response.raise_for_status()
        payload = response.json()

        try:
            text = str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("AI gateway returned an invalid chat completion") from exc

        usage = payload.get("usage") or {}
        input_tokens = _optional_int(usage.get("prompt_tokens"))
        output_tokens = _optional_int(usage.get("completion_tokens"))
        token_source = (
            "provider"
            if input_tokens is not None and output_tokens is not None
            else "estimated"
        )

        if input_tokens is None:
            input_tokens = estimate_tokens(system) + estimate_tokens(user)
        if output_tokens is None:
            output_tokens = estimate_tokens(text)

        # These response headers are optional lab-contract metadata emitted by the
        # trusted gateway. They are never accepted from the application request.
        provider = (
            response.headers.get("x-mayabank-ai-provider")
            or response.headers.get("x-litellm-provider")
            or "ai-gateway"
        ).strip()
        consumer_id = (
            response.headers.get("x-mayabank-ai-consumer") or "unknown"
        ).strip()
        executed_model = str(payload.get("model") or self.model_alias).strip()

        return LLMResult(
            text=text,
            provider=provider,
            model=executed_model,
            consumer_id=consumer_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            token_source=token_source,
        )


def _optional_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def estimate_tokens(text: str) -> int:
    """Portable estimate only; never reported as provider-billed token usage."""
    return 0 if not text else max(1, math.ceil(len(text) / 4.0))


class ObservedLLM(LLM):
    def __init__(
        self,
        delegate: LLM,
        provider: str = "configured",
        model: str = "unknown",
        workload_id: str = "tradeops",
    ):
        self.delegate = delegate
        self.requested_provider = provider
        self.requested_model = model
        self.workload_id = workload_id

    async def complete_result(self, system: str, user: str) -> LLMResult:
        estimated_input_tokens = estimate_tokens(system) + estimate_tokens(user)
        started = time.perf_counter()
        with start_span(
            "llm.complete",
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": self.requested_model,
                "tradeops.llm.requested_provider": self.requested_provider,
                "tradeops.llm.workload_id": self.workload_id,
                "tradeops.llm.input_tokens_estimated": estimated_input_tokens,
            },
        ) as span:
            try:
                result = await self.delegate.complete_result(system=system, user=user)
            except Exception as exc:
                LLM_REQUESTS.labels(
                    provider=self.requested_provider, status="error"
                ).inc()
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            finally:
                LLM_DURATION.labels(provider=self.requested_provider).observe(
                    time.perf_counter() - started
                )

            actual_provider = result.provider or "unknown"
            actual_model = result.model or "unknown"
            input_tokens = result.input_tokens or estimated_input_tokens
            output_tokens = result.output_tokens or estimate_tokens(result.text)

            LLM_REQUESTS.labels(provider=actual_provider, status="ok").inc()
            LLM_TOKENS_ESTIMATED.labels(
                provider=actual_provider, direction="input"
            ).inc(input_tokens)
            LLM_TOKENS_ESTIMATED.labels(
                provider=actual_provider, direction="output"
            ).inc(output_tokens)

            input_cost = float(os.getenv("LLM_INPUT_COST_USD_PER_1K", "0") or 0)
            output_cost = float(os.getenv("LLM_OUTPUT_COST_USD_PER_1K", "0") or 0)
            estimated_cost = (
                input_tokens / 1000.0 * input_cost
                + output_tokens / 1000.0 * output_cost
            )
            if estimated_cost > 0:
                LLM_ESTIMATED_COST_USD.labels(provider=actual_provider).inc(
                    estimated_cost
                )

            span.set_attribute("gen_ai.provider.name", actual_provider)
            span.set_attribute("gen_ai.response.model", actual_model)
            span.set_attribute("tradeops.llm.gateway_consumer_id", result.consumer_id)
            span.set_attribute("tradeops.llm.input_tokens", input_tokens)
            span.set_attribute("tradeops.llm.output_tokens", output_tokens)
            span.set_attribute("tradeops.llm.token_source", result.token_source)
            span.set_attribute("tradeops.llm.estimated_cost_usd", estimated_cost)
            return result


def _allowed_model_aliases(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _gateway_token_provider():
    mode = (settings.AI_GATEWAY_AUTH_MODE or "static").strip().lower()
    if mode == "static":
        return StaticAccessTokenProvider(settings.AI_GATEWAY_ACCESS_TOKEN)
    if mode == "client_credentials":
        return ClientCredentialsTokenProvider(
            token_url=settings.AI_OIDC_TOKEN_URL,
            client_id=settings.AI_OIDC_CLIENT_ID,
            client_secret=settings.AI_OIDC_CLIENT_SECRET,
            scope=settings.AI_OIDC_SCOPE,
            audience=settings.AI_OIDC_AUDIENCE,
        )
    raise RuntimeError(
        "AI_GATEWAY_AUTH_MODE must be 'static' or 'client_credentials'"
    )


def get_llm() -> LLM:
    provider = (settings.LLM_PROVIDER or "mock").strip().lower()
    if provider == "mock":
        return ObservedLLM(MockLLM(), provider="mock", model="mock")

    if provider in {"gateway", "litellm"}:
        model_alias = settings.AI_GATEWAY_MODEL_ALIAS or "tradeops-default"
        delegate: LLM = GatewayLLM(
            base_url=settings.AI_GATEWAY_BASE_URL,
            model_alias=model_alias,
            token_provider=_gateway_token_provider(),
            timeout_seconds=settings.AI_GATEWAY_TIMEOUT_SECONDS,
            allowed_model_aliases=_allowed_model_aliases(
                settings.AI_ALLOWED_MODEL_ALIASES
            ),
        )
        return ObservedLLM(
            delegate,
            provider="ai-gateway",
            model=model_alias,
            workload_id="tradeops",
        )

    raise RuntimeError(
        f"unsupported LLM_PROVIDER={provider!r}; use mock or gateway"
    )
