"""D-099 AA1 opt-in local Ollama JSON smoke. No shell, Git or OpenShift."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

MODEL_ID = re.compile(r"^[A-Za-z0-9._:/-]{1,120}$")
# Conservative loopback/known Windows host-only addresses. Unknown LAN,
# public, cloud, credentials, paths and redirects are not trusted.
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "192.168.56.1"})


class _NoRedirectHandler:
    """Use urllib's standard redirect handler but reject all redirects."""

    @staticmethod
    def handler():
        from urllib.request import HTTPRedirectHandler

        class DenyRedirect(HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, msg, headers, newurl):
                raise ValueError("Ollama API redirect denied")

        return DenyRedirect()


def ollama_base() -> str:
    """Honor Ollama CLI's OLLAMA_HOST without allowing arbitrary destinations."""
    value = os.environ.get("OLLAMA_HOST", "").strip() or "127.0.0.1:11434"
    if "://" not in value:
        value = "http://" + value
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise ValueError("unsupported Ollama address: use local localhost or approved host-only IP")
    port = parsed.port or 11434
    if not 1 <= port <= 65535:
        raise ValueError("invalid Ollama port")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"http://{host}:{port}"


def local_request(path: str, data: dict | None = None) -> dict:
    if path not in {"/api/tags", "/api/generate", "/api/version"}:
        raise ValueError("unsupported Ollama API path")
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = Request(
        f"{ollama_base()}{path}",
        data=payload,
        headers={"Content-Type": "application/json"} if payload else {},
        method="POST" if payload else "GET",
    )
    # Python may inherit HTTP_PROXY in Git Bash; Ollama CLI doesn't.
    # Bypass proxy ONLY for the validated local/host-only endpoint.
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler.handler())
    with opener.open(req, timeout=120 if payload else 10) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError("invalid Ollama object response")
    return result


def smoke(model: str, *, consent: str) -> dict:
    if consent != "YES":
        raise ValueError("D099_ALLOW_LOCAL_INFERENCE=YES required")
    if not MODEL_ID.fullmatch(model) or model.endswith(":cloud"):
        raise ValueError("invalid or remote/cloud model identifier")
    tags = local_request("/api/tags")
    installed = {item.get("name"): item for item in tags.get("models", [])
                 if isinstance(item, dict)}
    if model not in installed:
        raise ValueError("selected model is not installed locally")
    started = time.monotonic()
    result = local_request("/api/generate", {
        "model": model,
        "stream": False,
        "format": "json",
        "prompt": ('Return only a JSON object with exact keys "ok": true '
                   'and "purpose": "local-smoke". No other keys.'),
        "options": {"temperature": 0, "num_predict": 80},
        "keep_alive": "0",
    })
    duration = round((time.monotonic() - started) * 1000)
    raw = result.get("response", "")
    if not isinstance(raw, str):
        raise ValueError("non-text local Ollama response")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("local Ollama did not return valid JSON") from exc
    accepted = isinstance(obj, dict) and obj == {"ok": True, "purpose": "local-smoke"}
    return {
        "gate": "D099_AA1_OLLAMA_ONLY",
        "status": "LOCAL_JSON_SMOKE_PASS" if accepted else "LOCAL_JSON_SMOKE_FAIL",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "ollama_endpoint": ollama_base(),
        "model_digest": installed[model].get("digest", "NOT_MEASURED"),
        "model_size_bytes": installed[model].get("size", "NOT_MEASURED"),
        "latency_ms": duration,
        "ollama_total_duration_ns": result.get("total_duration", "NOT_MEASURED"),
        "eval_count": result.get("eval_count", "NOT_MEASURED"),
        "response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "host_cpu_ram": "NOT_MEASURED",
        "opencode_run": "NOT_TESTED",
        "permissions_enforced": "NOT_TESTED",
        "AA1_LOCAL_MODEL_BASELINE_VALIDATED": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="Read only Ollama API version")
    parser.add_argument("--model", help="Exact installed local model from 'ollama list'")
    args = parser.parse_args(argv)
    if not args.probe and not args.model:
        parser.error("--model is required unless --probe is set")
    try:
        if args.probe:
            local_request("/api/version")
            print(f"D099_AA1_OLLAMA_API_PROBE_PASS endpoint={ollama_base()}")
            return 0
        result = smoke(args.model, consent=os.environ.get("D099_ALLOW_LOCAL_INFERENCE", ""))
    except (ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
        # Intentionally omit raw server content, headers, tokens and prompts.
        print(f"D099_AA1_OLLAMA_SMOKE_FAILED={type(exc).__name__}", file=sys.stderr)
        print("D099_AA1_DIAGNOSIS=check OLLAMA_HOST, local API and proxy settings",
              file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "LOCAL_JSON_SMOKE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
