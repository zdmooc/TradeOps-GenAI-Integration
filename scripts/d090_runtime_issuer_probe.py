#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.parse
import urllib.request


def _claim_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("not a JWT")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))


def main() -> int:
    token_url = os.getenv("AI_OIDC_TOKEN_URL", "").strip()
    client_id = os.getenv("AI_OIDC_CLIENT_ID", "").strip()
    client_secret = os.getenv("AI_OIDC_CLIENT_SECRET", "").strip()
    scope = os.getenv("AI_OIDC_SCOPE", "ai.inference").strip() or "ai.inference"

    missing = [
        name
        for name, value in (
            ("AI_OIDC_TOKEN_URL", token_url),
            ("AI_OIDC_CLIENT_ID", client_id),
            ("AI_OIDC_CLIENT_SECRET", client_secret),
        )
        if not value
    ]
    if missing:
        print("D090_RUNTIME_ISSUER_FAIL missing=" + ",".join(missing), file=sys.stderr)
        return 2

    request = urllib.request.Request(
        token_url,
        data=urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    token = str(payload.get("access_token", ""))
    if not token:
        print("D090_RUNTIME_ISSUER_FAIL token=missing", file=sys.stderr)
        return 3

    claims = _claim_payload(token)
    issuer = str(claims.get("iss", "")).strip()
    if not issuer:
        print("D090_RUNTIME_ISSUER_FAIL iss=missing", file=sys.stderr)
        return 4

    print(issuer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
