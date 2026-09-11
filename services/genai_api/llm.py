from __future__ import annotations

import math
import os
import time

from opentelemetry.trace import Status, StatusCode

from services.common.config import settings
from services.common.observability_metrics import (
    LLM_DURATION,
    LLM_ESTIMATED_COST_USD,
    LLM_REQUESTS,
    LLM_TOKENS_ESTIMATED,
)
from services.common.otel import start_span


class LLM:
    async def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class MockLLM(LLM):
    async def complete(self, system: str, user: str) -> str:
        return (
            "MOCK_LLM_RESPONSE\n"
            "System: " + system[:120] + "\n"
            "User: " + user[:500] + "\n"
            "Conclusion: Revue générée en mode dégradé (mock)."
        )


def estimate_tokens(text: str) -> int:
    """Portable estimate only; never reported as provider-billed token usage."""
    return 0 if not text else max(1, math.ceil(len(text) / 4.0))


class ObservedLLM(LLM):
    def __init__(self, delegate: LLM, provider: str, model: str):
        self.delegate = delegate
        self.provider = provider
        self.model = model

    async def complete(self, system: str, user: str) -> str:
        input_tokens = estimate_tokens(system) + estimate_tokens(user)
        started = time.perf_counter()
        with start_span(
            "llm.complete",
            attributes={
                "gen_ai.provider.name": self.provider,
                "gen_ai.request.model": self.model,
                "tradeops.llm.input_tokens_estimated": input_tokens,
            },
        ) as span:
            try:
                output = await self.delegate.complete(system=system, user=user)
            except Exception as exc:
                LLM_REQUESTS.labels(provider=self.provider, status="error").inc()
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            finally:
                LLM_DURATION.labels(provider=self.provider).observe(
                    time.perf_counter() - started
                )

            output_tokens = estimate_tokens(output)
            LLM_REQUESTS.labels(provider=self.provider, status="ok").inc()
            LLM_TOKENS_ESTIMATED.labels(provider=self.provider, direction="input").inc(
                input_tokens
            )
            LLM_TOKENS_ESTIMATED.labels(provider=self.provider, direction="output").inc(
                output_tokens
            )
            input_cost = float(os.getenv("LLM_INPUT_COST_USD_PER_1K", "0") or 0)
            output_cost = float(os.getenv("LLM_OUTPUT_COST_USD_PER_1K", "0") or 0)
            estimated_cost = (
                input_tokens / 1000.0 * input_cost
                + output_tokens / 1000.0 * output_cost
            )
            if estimated_cost > 0:
                LLM_ESTIMATED_COST_USD.labels(provider=self.provider).inc(
                    estimated_cost
                )
            span.set_attribute("tradeops.llm.output_tokens_estimated", output_tokens)
            span.set_attribute("tradeops.llm.estimated_cost_usd", estimated_cost)
            return output


def get_llm() -> LLM:
    provider = (settings.LLM_PROVIDER or "mock").lower()
    model = settings.OPENAI_MODEL or "unknown"
    delegate: LLM = MockLLM()
    return ObservedLLM(delegate, provider=provider, model=model)
