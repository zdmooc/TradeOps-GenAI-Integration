from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

import httpx
import jwt
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True, slots=True)
class ConsumerPolicy:
    client_id: str
    consumer_id: str
    allowed_models: frozenset[str]
    requests_per_minute: int
    budget_usd: float
    input_cost_usd_per_1k: float = 0.0
    output_cost_usd_per_1k: float = 0.0


class PolicyError(PermissionError):
    def __init__(self, code: str, status_code: int = 403):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def parse_consumer_policies(raw: str) -> dict[str, ConsumerPolicy]:
    if not raw.strip():
        return {}
    payload = json.loads(raw)
    policies: dict[str, ConsumerPolicy] = {}
    for client_id, item in payload.items():
        policies[client_id] = ConsumerPolicy(
            client_id=client_id,
            consumer_id=str(item["consumer"]),
            allowed_models=frozenset(str(v) for v in item.get("models", [])),
            requests_per_minute=max(1, int(item.get("rpm", 60))),
            budget_usd=max(0.0, float(item.get("budget_usd", 0.0))),
            input_cost_usd_per_1k=max(
                0.0, float(item.get("input_cost_usd_per_1k", 0.0))
            ),
            output_cost_usd_per_1k=max(
                0.0, float(item.get("output_cost_usd_per_1k", 0.0))
            ),
        )
    return policies


class OidcConsumerVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_json: str,
        required_scope: str,
        policies: dict[str, ConsumerPolicy],
    ):
        self.issuer = issuer.strip()
        self.audience = audience.strip()
        self.required_scope = required_scope.strip()
        self.policies = policies
        try:
            self.jwks = json.loads(jwks_json) if jwks_json.strip() else {}
        except json.JSONDecodeError as exc:
            raise ValueError("AI_ACCESS_OIDC_JWKS_JSON must be valid JSON") from exc

    def verify(self, authorization: str | None) -> ConsumerPolicy:
        if not authorization:
            raise PolicyError("MISSING_TOKEN", 401)
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise PolicyError("INVALID_AUTHORIZATION", 401)
        if not self.issuer or not self.audience or not self.jwks:
            raise PolicyError("OIDC_CONFIGURATION_INCOMPLETE", 503)

        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise PolicyError("JWT_KID_MISSING", 401)
            candidates = [k for k in self.jwks.get("keys", []) if k.get("kid") == kid]
            if len(candidates) != 1:
                raise PolicyError("JWT_KEY_NOT_FOUND", 401)
            key = jwt.PyJWK.from_dict(candidates[0]).key
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except PolicyError:
            raise
        except (ValueError, TypeError, KeyError, jwt.PyJWTError) as exc:
            raise PolicyError("JWT_INVALID", 401) from exc

        scopes = frozenset(str(claims.get("scope", "")).split())
        if self.required_scope and self.required_scope not in scopes:
            raise PolicyError("SCOPE_DENIED", 403)

        client_id = str(claims.get("azp") or claims.get("client_id") or "").strip()
        policy = self.policies.get(client_id)
        if policy is None:
            raise PolicyError("UNKNOWN_CONSUMER", 403)
        return policy


class InMemoryConsumerLimits:
    """Bounded lab-only RPM/budget guard. Not a distributed production quota store."""

    def __init__(self):
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._spent_usd: dict[str, float] = defaultdict(float)

    def before_request(self, policy: ConsumerPolicy) -> None:
        now = time.monotonic()
        window = self._requests[policy.consumer_id]
        while window and window[0] <= now - 60.0:
            window.popleft()
        if len(window) >= policy.requests_per_minute:
            raise PolicyError("QUOTA_EXCEEDED", 429)
        if (
            policy.budget_usd > 0
            and self._spent_usd[policy.consumer_id] >= policy.budget_usd
        ):
            raise PolicyError("BUDGET_EXCEEDED", 429)
        window.append(now)

    def record_usage(
        self,
        policy: ConsumerPolicy,
        *,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        cost = (
            prompt_tokens / 1000.0 * policy.input_cost_usd_per_1k
            + completion_tokens / 1000.0 * policy.output_cost_usd_per_1k
        )
        self._spent_usd[policy.consumer_id] += cost
        return cost

    def spent_usd(self, consumer_id: str) -> float:
        return self._spent_usd[consumer_id]


class LiteLLMForwarder:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def forward(self, payload: dict) -> httpx.Response:
        if not self.base_url:
            raise RuntimeError("LITELLM_BASE_URL is required")
        if not self.api_key:
            raise RuntimeError("LITELLM_API_KEY is required")
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self.transport
        ) as client:
            return await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )


def _usage_tokens(payload: dict) -> tuple[int, int]:
    usage = payload.get("usage") or {}
    try:
        prompt = max(0, int(usage.get("prompt_tokens", 0)))
    except (TypeError, ValueError):
        prompt = 0
    try:
        completion = max(0, int(usage.get("completion_tokens", 0)))
    except (TypeError, ValueError):
        completion = 0
    return prompt, completion


def create_app(
    *,
    verifier: OidcConsumerVerifier,
    forwarder: LiteLLMForwarder,
    limits: InMemoryConsumerLimits | None = None,
) -> FastAPI:
    app = FastAPI(title="MayaBank D-090 AI Access Policy", version="0.1")
    limiter = limits or InMemoryConsumerLimits()

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "mode": "D090_LAB",
            "quota_store": "in-memory-single-replica",
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        try:
            policy = verifier.verify(authorization)
            payload = await request.json()
            requested_model = str(payload.get("model", "")).strip()
            if not requested_model:
                raise PolicyError("MODEL_REQUIRED", 400)
            if requested_model not in policy.allowed_models:
                raise PolicyError("MODEL_DENIED", 403)

            limiter.before_request(policy)
            upstream = await forwarder.forward(payload)
            body = upstream.json()
            if upstream.status_code >= 400:
                return JSONResponse(
                    status_code=upstream.status_code,
                    content=body,
                    headers={
                        "X-MayaBank-AI-Consumer": policy.consumer_id,
                        "X-MayaBank-AI-Provider": "litellm",
                    },
                )

            prompt_tokens, completion_tokens = _usage_tokens(body)
            cost = limiter.record_usage(
                policy,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            provider = (
                upstream.headers.get("x-mayabank-ai-provider")
                or upstream.headers.get("x-litellm-provider")
                or "litellm"
            )
            return JSONResponse(
                status_code=upstream.status_code,
                content=body,
                headers={
                    "X-MayaBank-AI-Consumer": policy.consumer_id,
                    "X-MayaBank-AI-Provider": provider,
                    "X-MayaBank-AI-Cost-USD": f"{cost:.8f}",
                },
            )
        except PolicyError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code},
            ) from exc

    return app


def app_from_env() -> FastAPI:
    policies = parse_consumer_policies(os.getenv("AI_ACCESS_CONSUMERS_JSON", ""))
    verifier = OidcConsumerVerifier(
        issuer=os.getenv("OIDC_ISSUER", ""),
        audience=os.getenv("AI_ACCESS_OIDC_AUDIENCE", "ai-gateway"),
        jwks_json=os.getenv("OIDC_JWKS_JSON", ""),
        required_scope=os.getenv("AI_ACCESS_REQUIRED_SCOPE", "ai.inference"),
        policies=policies,
    )
    forwarder = LiteLLMForwarder(
        base_url=os.getenv("LITELLM_BASE_URL", ""),
        api_key=os.getenv("LITELLM_API_KEY", ""),
        timeout_seconds=float(os.getenv("AI_ACCESS_UPSTREAM_TIMEOUT_SECONDS", "30")),
    )
    return create_app(verifier=verifier, forwarder=forwarder)


app = app_from_env()
