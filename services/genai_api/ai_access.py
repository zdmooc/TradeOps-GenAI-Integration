from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx


class AccessTokenProvider(Protocol):
    async def token(self) -> str:
        """Return a bearer token for the AI gateway."""


@dataclass(frozen=True, slots=True)
class StaticAccessTokenProvider:
    access_token: str

    async def token(self) -> str:
        token = self.access_token.strip()
        if not token:
            raise RuntimeError("AI_GATEWAY_ACCESS_TOKEN is required for static auth mode")
        return token


class ClientCredentialsTokenProvider:
    """OAuth2 client-credentials provider with a short in-memory token cache."""

    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str = "",
        audience: str = "",
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.token_url = token_url.strip()
        self.client_id = client_id.strip()
        self.client_secret = client_secret
        self.scope = scope.strip()
        self.audience = audience.strip()
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self._cached_token = ""
        self._expires_at_monotonic = 0.0

    def _validate(self) -> None:
        missing = []
        if not self.token_url:
            missing.append("AI_OIDC_TOKEN_URL")
        if not self.client_id:
            missing.append("AI_OIDC_CLIENT_ID")
        if not self.client_secret:
            missing.append("AI_OIDC_CLIENT_SECRET")
        if missing:
            raise RuntimeError("missing client-credentials settings: " + ",".join(missing))

    async def token(self) -> str:
        now = time.monotonic()
        if self._cached_token and now < self._expires_at_monotonic:
            return self._cached_token

        self._validate()
        form = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope:
            form["scope"] = self.scope
        if self.audience:
            form["audience"] = self.audience

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self.transport
        ) as client:
            response = await client.post(self.token_url, data=form)
        response.raise_for_status()
        payload = response.json()

        token = str(payload.get("access_token", "")).strip()
        if not token:
            raise RuntimeError("OIDC token response did not contain access_token")

        try:
            expires_in = max(1, int(payload.get("expires_in", 60)))
        except (TypeError, ValueError):
            expires_in = 60

        # Refresh before expiry; for very short lab tokens retain at least 1 second.
        refresh_after = max(1, expires_in - min(30, expires_in // 2))
        self._cached_token = token
        self._expires_at_monotonic = time.monotonic() + refresh_after
        return token
