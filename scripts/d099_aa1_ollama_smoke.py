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
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:11434"
MODEL_ID = re.compile(r"^[A-Za-z0-9._:/-]{1,120}$")


def local_request(path: str, data: dict | None = None) -> dict:
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = Request(
        f"{BASE}{path}", data=payload,
        headers={"Content-Type": "application/json"} if payload else {},
        method="POST" if payload else "GET",
    )
    with urlopen(req, timeout=120 if payload else 10) as response:
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
        "prompt": (
            'Return only a JSON object with exact keys "ok": true '
            'and "purpose": "local-smoke". No other keys.'
        ),
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
    parser.add_argument("--model", required=True,
                        help="Exact installed local model name from 'ollama list'")
    args = parser.parse_args(argv)
    try:
        result = smoke(args.model, consent=os.environ.get("D099_ALLOW_LOCAL_INFERENCE", ""))
    except (ValueError, HTTPError, URLError, TimeoutError) as exc:
        # Intentionally omit server content, request headers, and raw output.
        print(f"D099_AA1_OLLAMA_SMOKE_FAILED={type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "LOCAL_JSON_SMOKE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
