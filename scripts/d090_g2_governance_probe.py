#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _token() -> str:
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
        raise RuntimeError("missing " + ",".join(missing))

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
        raise RuntimeError("access token missing")
    return token


def _request(model: str, token: str) -> tuple[int, dict, dict[str, str]]:
    base_url = os.getenv("AI_GATEWAY_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("AI_GATEWAY_BASE_URL missing")
    request = urllib.request.Request(
        base_url + "/v1/chat/completions",
        data=json.dumps(
            {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Return exactly D090_G2_OK.",
                    }
                ],
                "temperature": 0,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return (
                response.status,
                json.loads(response.read().decode("utf-8")),
                {k.lower(): v for k, v in response.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": " ".join(raw.split())[:512]}
        return exc.code, payload, {k.lower(): v for k, v in exc.headers.items()}


def _code(payload: dict) -> str:
    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("code", ""))
    return ""


def _expect_success(token: str, model: str = "tradeops-default") -> None:
    status, payload, headers = _request(model, token)
    if status != 200:
        raise RuntimeError(f"expected HTTP 200, observed {status}: {payload}")
    consumer = headers.get("x-mayabank-ai-consumer", "")
    provider = headers.get("x-mayabank-ai-provider", "")
    if consumer != "tradeops":
        raise RuntimeError(f"consumer mismatch: {consumer or 'missing'}")
    if not provider:
        raise RuntimeError("provider header missing")
    print("D090_G2_SUCCESS=PASS consumer=tradeops provider=" + provider)


def _expect_denial(token: str, model: str, status_expected: int, code_expected: str) -> None:
    status, payload, _ = _request(model, token)
    observed = _code(payload)
    if status != status_expected or observed != code_expected:
        raise RuntimeError(
            f"expected HTTP {status_expected}/{code_expected}, "
            f"observed HTTP {status}/{observed or payload}"
        )
    print(f"D090_G2_{code_expected}=PASS http={status}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=("baseline", "quota", "budget"),
    )
    args = parser.parse_args()

    try:
        token = _token()
        print("D090_G2_OIDC_TOKEN=PASS")

        if args.mode == "baseline":
            _expect_success(token)
            _expect_denial(token, "odm-extraction", 403, "MODEL_DENIED")
            print("D090_G2_BASELINE=PASS")
            return 0

        if args.mode == "quota":
            _expect_success(token)
            _expect_denial(token, "tradeops-default", 429, "QUOTA_EXCEEDED")
            print("D090_G2_QUOTA=PASS")
            return 0

        if args.mode == "budget":
            _expect_success(token)
            _expect_denial(token, "tradeops-default", 429, "BUDGET_EXCEEDED")
            print("D090_G2_BUDGET=PASS")
            return 0

    except Exception as exc:
        print(f"D090_G2_PROBE_FAIL mode={args.mode} error={exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
