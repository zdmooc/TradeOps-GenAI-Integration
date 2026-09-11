from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Mapping

import jwt


@dataclass(frozen=True, slots=True)
class SecurityPrincipal:
    subject: str
    roles: frozenset[str]
    scopes: frozenset[str]
    authn_method: str
    issuer: str = ""

    def has_role(self, role: str) -> bool:
        return role in self.roles


@dataclass(frozen=True, slots=True)
class IdentityConfig:
    mode: str = "static"
    issuer: str = ""
    audience: str = ""
    jwks_json: str = ""
    role_claim: str = "roles"
    scope_claim: str = "scope"

    @classmethod
    def from_env(cls) -> "IdentityConfig":
        return cls(
            mode=os.getenv("TRADEOPS_AUTH_MODE", "static").strip().lower(),
            issuer=os.getenv("OIDC_ISSUER", "").strip(),
            audience=os.getenv("OIDC_AUDIENCE", "").strip(),
            jwks_json=os.getenv("OIDC_JWKS_JSON", "").strip(),
            role_claim=os.getenv("OIDC_ROLE_CLAIM", "roles").strip() or "roles",
            scope_claim=os.getenv("OIDC_SCOPE_CLAIM", "scope").strip() or "scope",
        )


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _claim_set(value) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        return frozenset(part for part in value.replace(",", " ").split() if part)
    if isinstance(value, (list, tuple, set)):
        return frozenset(str(part) for part in value if str(part).strip())
    return frozenset({str(value)})


def _oidc_principal(token: str, config: IdentityConfig) -> SecurityPrincipal | None:
    if not config.issuer or not config.audience or not config.jwks_json:
        return None
    try:
        jwks = json.loads(config.jwks_json)
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            return None
        candidates = [key for key in jwks.get("keys", []) if key.get("kid") == kid]
        if len(candidates) != 1:
            return None
        key = jwt.PyJWK.from_dict(candidates[0]).key
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            issuer=config.issuer,
            audience=config.audience,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except (ValueError, TypeError, KeyError, jwt.PyJWTError):
        return None

    return SecurityPrincipal(
        subject=str(claims["sub"]),
        roles=_claim_set(claims.get(config.role_claim)),
        scopes=_claim_set(claims.get(config.scope_claim)),
        authn_method="oidc-jwt",
        issuer=str(claims.get("iss", "")),
    )


def authenticate_authorization(
    authorization: str | None,
    *,
    static_principals: Mapping[str, SecurityPrincipal],
    required_role: str | None = None,
    config: IdentityConfig | None = None,
) -> SecurityPrincipal | None:
    token = bearer_token(authorization)
    if not token:
        return None
    config = config or IdentityConfig.from_env()
    if config.mode == "static":
        principal = static_principals.get(token)
    elif config.mode == "oidc":
        principal = _oidc_principal(token, config)
    else:
        return None
    if principal is None:
        return None
    if required_role and required_role not in principal.roles:
        return None
    return principal
