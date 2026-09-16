from __future__ import annotations

import os
from dataclasses import dataclass

from mcp.server.auth.provider import AccessToken, TokenVerifier

from services.security.identity import IdentityConfig, SecurityPrincipal, authenticate_authorization


_DEFAULT_ISSUER = "http://keycloak:8080/realms/tradeops"
_DEFAULT_RESOURCE = "http://mcp-native:8017/mcp"


@dataclass(frozen=True, slots=True)
class NativeMcpAuthConfig:
    issuer_url: str
    resource_url: str

    @classmethod
    def from_env(cls) -> "NativeMcpAuthConfig":
        # `.env` commonly contains empty optional OIDC values in local/static mode.
        # AuthSettings still requires valid metadata URLs, so empty values fall back
        # to explicit local demonstrator identifiers instead of crashing startup.
        resource_url = os.getenv("MCP_NATIVE_RESOURCE_URL", "").strip() or _DEFAULT_RESOURCE
        issuer_url = os.getenv("OIDC_ISSUER", "").strip() or _DEFAULT_ISSUER
        return cls(issuer_url=issuer_url, resource_url=resource_url)


def static_principals() -> dict[str, SecurityPrincipal]:
    return {
        os.getenv("MCP_AGENT_TOKEN", ""): SecurityPrincipal(
            subject="agent-controller",
            roles=frozenset({"agent"}),
            scopes=frozenset({"market.read", "risk.evaluate", "workflow.read", "mq.read"}),
            authn_method="static",
        ),
        os.getenv("MCP_REVIEWER_TOKEN", ""): SecurityPrincipal(
            subject="human-reviewer",
            roles=frozenset({"reviewer"}),
            scopes=frozenset(
                {
                    "market.read",
                    "risk.evaluate",
                    "workflow.read",
                    "mq.read",
                    "audit.read",
                    "paper.execute",
                }
            ),
            authn_method="static",
        ),
    }


class TradeOpsTokenVerifier(TokenVerifier):
    """Bridge existing TradeOps static/OIDC identity verification into MCP v2."""

    def __init__(
        self,
        *,
        auth_config: NativeMcpAuthConfig | None = None,
        identity_config: IdentityConfig | None = None,
    ) -> None:
        self.auth_config = auth_config or NativeMcpAuthConfig.from_env()
        self.identity_config = identity_config or IdentityConfig.from_env()

    async def verify_token(self, token: str) -> AccessToken | None:
        principal = authenticate_authorization(
            f"Bearer {token}",
            static_principals=static_principals(),
            config=self.identity_config,
        )
        if principal is None:
            return None

        issuer = principal.issuer or self.auth_config.issuer_url
        return AccessToken(
            token=token,
            client_id=principal.subject,
            scopes=sorted(principal.scopes),
            resource=self.auth_config.resource_url,
            subject=principal.subject,
            claims={
                "iss": issuer,
                "roles": sorted(principal.roles),
                "authn_method": principal.authn_method,
            },
        )
