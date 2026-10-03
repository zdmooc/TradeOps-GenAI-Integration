import asyncio
import json
from contextlib import contextmanager
from unittest.mock import patch

import httpx
import pytest

from services.genai_api.ai_access import (
    ClientCredentialsTokenProvider,
    StaticAccessTokenProvider,
)
from services.genai_api.llm import GatewayLLM, MockLLM, ObservedLLM


def test_gateway_uses_openai_contract_without_client_controlled_consumer_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        assert request.url.path == "/ai/v1/chat/completions"
        return httpx.Response(
            200,
            headers={
                "x-mayabank-ai-provider": "openai",
                "x-mayabank-ai-consumer": "tradeops",
            },
            json={
                "id": "chatcmpl-test",
                "model": "openai/gpt-4o-mini",
                "choices": [
                    {"message": {"role": "assistant", "content": "approved for review"}}
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            },
        )

    gateway = GatewayLLM(
        base_url="https://gateway.example/ai",
        model_alias="tradeops-default",
        token_provider=StaticAccessTokenProvider("jwt-for-test"),
        allowed_model_aliases=frozenset({"tradeops-default"}),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(gateway.complete_result("system", "user"))

    assert seen["headers"]["authorization"] == "Bearer jwt-for-test"
    assert "x-consumer-id" not in seen["headers"]
    assert "x-mayabank-ai-consumer" not in seen["headers"]
    assert seen["payload"]["model"] == "tradeops-default"
    assert result.provider == "openai"
    assert result.model == "openai/gpt-4o-mini"
    assert result.consumer_id == "tradeops"
    assert result.input_tokens == 12
    assert result.output_tokens == 4
    assert result.token_source == "provider"


def test_gateway_model_alias_allowlist_fails_closed_before_network():
    gateway = GatewayLLM(
        base_url="https://gateway.example/ai",
        model_alias="forbidden-model",
        token_provider=StaticAccessTokenProvider("jwt-for-test"),
        allowed_model_aliases=frozenset({"tradeops-default"}),
    )

    with pytest.raises(PermissionError, match="AI_MODEL_NOT_ALLOWED"):
        asyncio.run(gateway.complete("system", "user"))


def test_client_credentials_provider_fetches_and_caches_token():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.url.path == "/realms/mayabank/protocol/openid-connect/token"
        body = request.content.decode("utf-8")
        assert "grant_type=client_credentials" in body
        assert "client_id=tradeops-ai" in body
        assert "scope=ai.inference" in body
        return httpx.Response(
            200,
            json={"access_token": "oidc-token", "expires_in": 120},
        )

    provider = ClientCredentialsTokenProvider(
        token_url=(
            "https://keycloak.example/realms/mayabank/"
            "protocol/openid-connect/token"
        ),
        client_id="tradeops-ai",
        client_secret="test-secret",
        scope="ai.inference",
        audience="ai-gateway",
        transport=httpx.MockTransport(handler),
    )

    first = asyncio.run(provider.token())
    second = asyncio.run(provider.token())
    assert first == second == "oidc-token"
    assert calls["count"] == 1


class _FakeSpan:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def record_exception(self, _exc):
        pass

    def set_status(self, _status):
        pass


def test_observed_llm_telemetry_uses_executed_metadata_not_config_labels():
    span = _FakeSpan()

    @contextmanager
    def fake_start_span(_name, attributes=None):
        span.attributes.update(attributes or {})
        yield span

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "x-mayabank-ai-provider": "azure-openai",
                "x-mayabank-ai-consumer": "tradeops",
            },
            json={
                "model": "gpt-4.1-mini-deployment",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            },
        )

    gateway = GatewayLLM(
        base_url="https://gateway.example/ai",
        model_alias="tradeops-default",
        token_provider=StaticAccessTokenProvider("token"),
        allowed_model_aliases=frozenset({"tradeops-default"}),
        transport=httpx.MockTransport(handler),
    )
    observed = ObservedLLM(
        gateway,
        provider="configured-provider-that-was-not-called",
        model="configured-model-that-was-not-called",
    )

    with patch("services.genai_api.llm.start_span", fake_start_span):
        result = asyncio.run(observed.complete_result("system", "user"))

    assert result.provider == "azure-openai"
    assert result.model == "gpt-4.1-mini-deployment"
    assert span.attributes["gen_ai.provider.name"] == "azure-openai"
    assert span.attributes["gen_ai.response.model"] == "gpt-4.1-mini-deployment"
    assert span.attributes["tradeops.llm.gateway_consumer_id"] == "tradeops"
    assert span.attributes["gen_ai.request.model"] == "configured-model-that-was-not-called"


def test_mock_remains_explicit_and_truthful():
    result = asyncio.run(MockLLM().complete_result("system", "user"))
    assert result.provider == "mock"
    assert result.model == "mock"
    assert result.text.startswith("MOCK_LLM_RESPONSE")
