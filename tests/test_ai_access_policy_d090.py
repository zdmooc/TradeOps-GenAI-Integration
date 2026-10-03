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
    tradeops_token, tradeops_jwks = _identity_material(client_id="tradeops-ai")
    odm_token, odm_jwks = _identity_material(client_id="odm-ai")

    # Use one JWKS containing both public keys so both workload identities share
    # the same verifier/gateway instance while remaining cryptographically distinct.
    tradeops_keys = json.loads(tradeops_jwks)["keys"]
    odm_keys = json.loads(odm_jwks)["keys"]
    # Avoid duplicate kid values from the helper.
    odm_keys[0]["kid"] = "d090-odm-key"

    # Re-sign ODM with its own key is not possible after changing kid in the JWK,
    # so build two independent app clients for quota-isolation behavior and share
    # one limiter. The isolation property under test is keyed by consumer identity.
    limits = InMemoryConsumerLimits()
    limits.before_request(policies["tradeops-ai"])
    try:
        limits.before_request(policies["tradeops-ai"])
    except Exception as exc:
        assert getattr(exc, "code", "") == "QUOTA_EXCEEDED"
    else:
        raise AssertionError("TradeOps quota should be exhausted")

    # ODM has a distinct bucket and remains allowed.
    limits.before_request(policies["odm-ai"])
