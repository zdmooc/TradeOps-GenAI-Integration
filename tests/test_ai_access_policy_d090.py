import json
import time

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from services.ai_access_policy.main import (
    InMemoryConsumerLimits,
    LiteLLMForwarder,
    OidcConsumerVerifier,
    create_app,
    parse_consumer_policies,
)


def _identity_material(*, client_id="tradeops-ai", audience="ai-gateway", scope="ai.inference"):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk["kid"] = "d090-key"
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://issuer.test/realms/mayabank",
            "aud": audience,
            "sub": f"service-account-{client_id}",
            "azp": client_id,
            "scope": scope,
            "iat": now - 5,
            "exp": now + 300,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "d090-key"},
    )
    return token, json.dumps({"keys": [jwk]})


def _policies(rpm=60):
    return parse_consumer_policies(
        json.dumps(
            {
                "tradeops-ai": {
                    "consumer": "tradeops",
                    "models": ["tradeops-default"],
                    "rpm": rpm,
                    "budget_usd": 1.0,
                    "input_cost_usd_per_1k": 0.01,
                    "output_cost_usd_per_1k": 0.02,
                },
                "odm-ai": {
                    "consumer": "odm",
                    "models": ["odm-extraction"],
                    "rpm": 30,
                    "budget_usd": 1.0,
                },
            }
        )
    )


def _client(*, client_id="tradeops-ai", audience="ai-gateway", scope="ai.inference", rpm=60):
    token, jwks = _identity_material(
        client_id=client_id, audience=audience, scope=scope
    )
    verifier = OidcConsumerVerifier(
        issuer="https://issuer.test/realms/mayabank",
        audience="ai-gateway",
        jwks_json=jwks,
        required_scope="ai.inference",
        policies=_policies(rpm=rpm),
    )

    def upstream(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer litellm-server-key"
        payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            headers={"x-mayabank-ai-provider": "test-provider"},
            json={
                "model": payload["model"] + "-resolved",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    forwarder = LiteLLMForwarder(
        base_url="https://litellm.internal",
        api_key="litellm-server-key",
        transport=httpx.MockTransport(upstream),
    )
    app = create_app(
        verifier=verifier,
        forwarder=forwarder,
        limits=InMemoryConsumerLimits(),
    )
    return TestClient(app), token


def test_tradeops_valid_identity_is_mapped_server_side_and_forwarded():
    client, token = _client()
    response = client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {token}",
            # Attempted spoof must not influence the server-derived consumer.
            "X-MayaBank-AI-Consumer": "odm",
        },
        json={
            "model": "tradeops-default",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200
    assert response.headers["x-mayabank-ai-consumer"] == "tradeops"
    assert response.headers["x-mayabank-ai-provider"] == "test-provider"
    assert response.json()["model"] == "tradeops-default-resolved"


def test_wrong_audience_is_denied():
    client, token = _client(audience="wrong-audience")
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "tradeops-default", "messages": []},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "JWT_INVALID"


def test_wrong_scope_is_denied():
    client, token = _client(scope="market.read")
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "tradeops-default", "messages": []},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "SCOPE_DENIED"


def test_unknown_consumer_is_denied():
    client, token = _client(client_id="unknown-ai")
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "tradeops-default", "messages": []},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "UNKNOWN_CONSUMER"


def test_cross_consumer_model_access_is_denied():
    client, token = _client(client_id="tradeops-ai")
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "odm-extraction", "messages": []},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "MODEL_DENIED"


def test_quota_is_enforced_per_consumer():
    client, token = _client(rpm=1)
    first = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "tradeops-default", "messages": []},
    )
    second = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "tradeops-default", "messages": []},
    )
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "QUOTA_EXCEEDED"


def test_odm_valid_identity_uses_only_odm_model():
    client, token = _client(client_id="odm-ai")
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model": "odm-extraction",
            "messages": [{"role": "user", "content": "extract"}],
        },
    )
    assert response.status_code == 200
    assert response.headers["x-mayabank-ai-consumer"] == "odm"
    assert response.json()["model"] == "odm-extraction-resolved"


def test_odm_cannot_use_tradeops_model():
    client, token = _client(client_id="odm-ai")
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "tradeops-default", "messages": []},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "MODEL_DENIED"


def test_tradeops_quota_exhaustion_does_not_consume_odm_quota():
    policies = _policies(rpm=1)
    limits = InMemoryConsumerLimits()

    limits.before_request(policies["tradeops-ai"])
    try:
        limits.before_request(policies["tradeops-ai"])
    except Exception as exc:
        assert getattr(exc, "code", "") == "QUOTA_EXCEEDED"
    else:
        raise AssertionError("TradeOps quota should be exhausted")

    # Limits are keyed by the trusted server-side consumer identity. Exhausting
    # TradeOps therefore does not consume ODM's distinct bucket.
    limits.before_request(policies["odm-ai"])


def test_missing_token_is_denied():
    client, _token = _client()
    response = client.post(
        "/v1/chat/completions",
        json={"model": "tradeops-default", "messages": []},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "MISSING_TOKEN"


def test_budget_is_enforced_on_following_request():
    policies = parse_consumer_policies(
        json.dumps(
            {
                "tradeops-ai": {
                    "consumer": "tradeops",
                    "models": ["tradeops-default"],
                    "rpm": 60,
                    "budget_usd": 0.001,
                    "input_cost_usd_per_1k": 0.01,
                    "output_cost_usd_per_1k": 0.02,
                }
            }
        )
    )
    limits = InMemoryConsumerLimits()
    policy = policies["tradeops-ai"]
    limits.record_usage(policy, prompt_tokens=100, completion_tokens=50)

    try:
        limits.before_request(policy)
    except Exception as exc:
        assert getattr(exc, "code", "") == "BUDGET_EXCEEDED"
    else:
        raise AssertionError("consumer budget should be exhausted")


def test_metrics_expose_trusted_consumer_usage_and_denials():
    client, token = _client()

    ok = client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={"model": "tradeops-default", "messages": []},
    )
    denied = client.post(
        "/v1/chat/completions",
        json={"model": "tradeops-default", "messages": []},
    )
    metrics = client.get("/metrics")

    assert ok.status_code == 200
    assert denied.status_code == 401
    assert metrics.status_code == 200
    body = metrics.text
    assert 'mayabank_ai_access_requests_total{consumer="tradeops",status="ok"}' in body
    assert 'mayabank_ai_access_denials_total{code="MISSING_TOKEN"}' in body
    assert 'mayabank_ai_access_tokens_total{consumer="tradeops",direction="input"}' in body
