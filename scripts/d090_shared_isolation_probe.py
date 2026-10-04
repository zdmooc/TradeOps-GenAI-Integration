#!/usr/bin/env python3
"""D-090 G3/G4 shared-consumer runtime evidence probe.

Proves two distinct client-credentials identities use one deployed gateway while
cross-consumer model access is denied. Secrets are never printed or written.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def token(url: str, client_id: str, client_secret: str, scope: str, timeout: float) -> str:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            }
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode())
    value = str(payload.get("access_token", "")).strip()
    if not value:
        raise RuntimeError(f"no access token returned for {client_id}")
    return value


def call(
    gateway_url: str,
    access_token: str,
    model: str,
    timeout: float,
) -> tuple[int, dict, dict[str, str]]:
    request = urllib.request.Request(
        gateway_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": "Return OK."}],
                "temperature": 0,
            }
        ).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            # Spoof attempt: the server must derive identity from the JWT.
            "X-MayaBank-AI-Consumer": "spoofed-client-value",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return (
                response.status,
                json.loads(response.read().decode()),
                {k.lower(): v for k, v in response.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body[:200]}
        return exc.code, payload, {k.lower(): v for k, v in exc.headers.items()}


def denial_code(payload: dict) -> str:
    detail = payload.get("detail") or {}
    return str(detail.get("code", "")) if isinstance(detail, dict) else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-url", default=os.getenv("AI_GATEWAY_BASE_URL", ""))
    parser.add_argument("--token-url", default=os.getenv("AI_OIDC_TOKEN_URL", ""))
    parser.add_argument("--scope", default=os.getenv("AI_OIDC_SCOPE", "ai.inference"))
    parser.add_argument("--tradeops-client-id", default=os.getenv("AI_OIDC_CLIENT_ID", "tradeops-ai"))
    parser.add_argument("--tradeops-secret", default=os.getenv("AI_OIDC_CLIENT_SECRET", ""))
    parser.add_argument("--odm-client-id", default=os.getenv("ODM_AI_CLIENT_ID", "odm-ai"))
    parser.add_argument("--odm-secret", default=os.getenv("ODM_AI_CLIENT_SECRET", ""))
    parser.add_argument("--tradeops-model", default="tradeops-default")
    parser.add_argument("--odm-model", default="odm-extraction")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--evidence-out")
    args = parser.parse_args()

    required = {
        "AI_GATEWAY_BASE_URL": args.gateway_url,
        "AI_OIDC_TOKEN_URL": args.token_url,
        "AI_OIDC_CLIENT_SECRET": args.tradeops_secret,
        "ODM_AI_CLIENT_SECRET": args.odm_secret,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        print("D090_SHARED_PRECHECK=FAIL missing=" + ",".join(missing), file=sys.stderr)
        return 2

    tradeops_token = token(
        args.token_url, args.tradeops_client_id, args.tradeops_secret, args.scope, args.timeout
    )
    odm_token = token(
        args.token_url, args.odm_client_id, args.odm_secret, args.scope, args.timeout
    )

    tradeops_ok = call(args.gateway_url, tradeops_token, args.tradeops_model, args.timeout)
    odm_ok = call(args.gateway_url, odm_token, args.odm_model, args.timeout)
    tradeops_cross = call(args.gateway_url, tradeops_token, args.odm_model, args.timeout)
    odm_cross = call(args.gateway_url, odm_token, args.tradeops_model, args.timeout)

    observations = {
        "tradeops_positive": {
            "status": tradeops_ok[0],
            "consumer": tradeops_ok[2].get("x-mayabank-ai-consumer", ""),
            "provider": tradeops_ok[2].get("x-mayabank-ai-provider", ""),
            "model": str(tradeops_ok[1].get("model", "")),
        },
        "odm_positive": {
            "status": odm_ok[0],
            "consumer": odm_ok[2].get("x-mayabank-ai-consumer", ""),
            "provider": odm_ok[2].get("x-mayabank-ai-provider", ""),
            "model": str(odm_ok[1].get("model", "")),
        },
        "tradeops_to_odm_denial": {
            "status": tradeops_cross[0],
            "code": denial_code(tradeops_cross[1]),
        },
        "odm_to_tradeops_denial": {
            "status": odm_cross[0],
            "code": denial_code(odm_cross[1]),
        },
    }

    checks = [
        observations["tradeops_positive"]["status"] == 200,
        observations["tradeops_positive"]["consumer"] == "tradeops",
        observations["odm_positive"]["status"] == 200,
        observations["odm_positive"]["consumer"] == "odm",
        observations["tradeops_to_odm_denial"] == {"status": 403, "code": "MODEL_DENIED"},
        observations["odm_to_tradeops_denial"] == {"status": 403, "code": "MODEL_DENIED"},
    ]
    if not all(checks):
        print("D090_SHARED_ISOLATION=FAIL", file=sys.stderr)
        print(json.dumps(observations, indent=2), file=sys.stderr)
        return 3

    print("D090_TRADEOPS_CONSUMER=PASS")
    print("D090_ODM_CONSUMER=PASS")
    print("D090_CROSS_MODEL_ISOLATION=PASS")
    print("D090_SHARED_ISOLATION=PASS")

    evidence = {
        "status": "D090_SHARED_ISOLATION_PASS",
        "observations": observations,
        "secrets_recorded": False,
    }
    if args.evidence_out:
        output = Path(args.evidence_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(f"D090_EVIDENCE_WRITTEN={output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
