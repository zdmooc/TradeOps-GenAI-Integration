#!/usr/bin/env python3
"""D-090 end-to-end real-model evidence probe.

No credentials are printed. The script fails closed when the response cannot prove
an authenticated consumer plus a non-mock executed model/provider.
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


def _post_form(url: str, form: dict[str, str], timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(
    url: str, payload: dict, token: str, timeout: float
) -> tuple[dict, dict[str, str]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
        headers = {k.lower(): v for k, v in response.headers.items()}
        return body, headers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-url", default=os.getenv("AI_GATEWAY_BASE_URL", ""))
    parser.add_argument("--model", default=os.getenv("AI_GATEWAY_MODEL_ALIAS", "tradeops-default"))
    parser.add_argument("--token-url", default=os.getenv("AI_OIDC_TOKEN_URL", ""))
    parser.add_argument("--client-id", default=os.getenv("AI_OIDC_CLIENT_ID", ""))
    parser.add_argument("--client-secret", default=os.getenv("AI_OIDC_CLIENT_SECRET", ""))
    parser.add_argument("--scope", default=os.getenv("AI_OIDC_SCOPE", "ai.inference"))
    parser.add_argument("--expected-consumer", default="tradeops")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--evidence-out")
    args = parser.parse_args()

    required = {
        "AI_GATEWAY_BASE_URL": args.gateway_url,
        "AI_OIDC_TOKEN_URL": args.token_url,
        "AI_OIDC_CLIENT_ID": args.client_id,
        "AI_OIDC_CLIENT_SECRET": args.client_secret,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        print("D090_PROBE_PRECHECK=FAIL missing=" + ",".join(missing), file=sys.stderr)
        return 2

    token_response = _post_form(
        args.token_url,
        {
            "grant_type": "client_credentials",
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "scope": args.scope,
        },
        args.timeout,
    )
    token = str(token_response.get("access_token", ""))
    if not token:
        print("D090_OIDC_TOKEN=FAIL", file=sys.stderr)
        return 3
    print("D090_OIDC_TOKEN=PASS")

    try:
        body, headers = _post_json(
            args.gateway_url.rstrip("/") + "/v1/chat/completions",
            {
                "model": args.model,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Return exactly the short phrase D090_REAL_MODEL_OK. "
                            "Do not include secrets or external data."
                        ),
                    }
                ],
                "temperature": 0,
            },
            token,
            args.timeout,
        )
    except urllib.error.HTTPError as exc:
        raw = exc.read(2048).decode("utf-8", errors="replace")
        safe = " ".join(raw.split())[:512]
        print(
            f"D090_GATEWAY_HTTP_FAIL status={exc.code} body={safe or 'empty'}",
            file=sys.stderr,
        )
        return 8

    consumer = headers.get("x-mayabank-ai-consumer", "")
    provider = headers.get("x-mayabank-ai-provider", "")
    executed_model = str(body.get("model", "")).strip()
    try:
        text = str(body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        print("D090_COMPLETION_CONTRACT=FAIL", file=sys.stderr)
        return 4

    if consumer != args.expected_consumer:
        print(
            f"D090_CONSUMER_IDENTITY=FAIL expected={args.expected_consumer} observed={consumer or 'missing'}",
            file=sys.stderr,
        )
        return 5
    print(f"D090_CONSUMER_IDENTITY=PASS consumer={consumer}")

    bad_markers = {"", "mock", "unknown", "configured"}
    if provider.strip().lower() in bad_markers:
        print("D090_PROVIDER_EVIDENCE=FAIL", file=sys.stderr)
        return 6
    if executed_model.lower() in bad_markers or "mock" in executed_model.lower():
        print("D090_MODEL_EVIDENCE=FAIL", file=sys.stderr)
        return 7

    print(f"D090_PROVIDER_EVIDENCE=PASS provider={provider}")
    print(f"D090_MODEL_EVIDENCE=PASS model={executed_model}")
    print("D090_REAL_MODEL_PATH=PASS")

    evidence = {
        "status": "D090_REAL_MODEL_PATH_PASS",
        "consumer": consumer,
        "provider": provider,
        "executed_model": executed_model,
        "response_preview": text[:120],
        "requested_alias": args.model,
        "secrets_recorded": False,
    }
    if args.evidence_out:
        path = Path(args.evidence_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(f"D090_EVIDENCE_WRITTEN={path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
