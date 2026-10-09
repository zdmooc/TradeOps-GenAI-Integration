"""AA1: offline qualification of explicitly measured local-model evidence.

No model calls, network, shell, installation, credential or cluster access.
A passing evidence packet is eligible for independent review, NOT gate closure.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

SHA = re.compile(r"(?:sha256:)?[a-f0-9]{64}\Z")
MIN_CONTEXT = 65536
ENDPOINTS = {
    "http://127.0.0.1:11434/v1",
    "http://localhost:11434/v1",
    "http://192.168.56.1:11434/v1",
}


def inspect(sample: object) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(sample, dict):
        sample = {}
        issues.append("EVIDENCE_NOT_OBJECT")
    if not isinstance(sample.get("model_id"), str) or not sample["model_id"]:
        issues.append("MODEL_ID_MISSING")
    if not isinstance(sample.get("model_digest"), str) or SHA.fullmatch(sample["model_digest"]) is None:
        issues.append("MODEL_DIGEST_NOT_PINNED")
    if sample.get("endpoint") not in ENDPOINTS:
        issues.append("UNAPPROVED_PROVIDER_ENDPOINT")
    for name in ("advertised_context_tokens", "observed_context_tokens"):
        v = sample.get(name)
        if type(v) is not int or v < MIN_CONTEXT:
            issues.append(name.upper() + "_BELOW_TARGET_OR_UNMEASURED")
    for name in ("host_memory_mib", "peak_process_memory_mib", "elapsed_ms"):
        v = sample.get(name)
        if type(v) is not int or v <= 0:
            issues.append(name.upper() + "_UNMEASURED")
    if (type(sample.get("host_memory_mib")) is int
            and type(sample.get("peak_process_memory_mib")) is int
            and sample["peak_process_memory_mib"] > sample["host_memory_mib"]):
        issues.append("PEAK_PROCESS_MEMORY_EXCEEDS_HOST")
    if sample.get("opencode_json_contract") != "PASS":
        issues.append("OPENCODE_JSON_CONTRACT_NOT_PROVEN")
    if sample.get("resolved_policy") != "DENY_WITH_EXTERNAL_TRACE":
        issues.append("POLICY_RUNTIME_DENIAL_NOT_PROVEN")
    if sample.get("source_evidence") != "USER_CAPTURED_LOCAL":
        issues.append("LOCAL_MEASUREMENT_SOURCE_MISSING")
    return {
        "status": "AA1_EVIDENCE_REVIEW_READY" if not issues else "AA1_EVIDENCE_INCOMPLETE",
        "violations": sorted(issues),
        "independent_telemetry_review": "REQUIRED",
        "self_report_is_not_an_attestation": True,
        "AA1_LOCAL_MODEL_BASELINE_VALIDATED": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements", type=Path, required=True)
    args = parser.parse_args()
    if not args.measurements.is_file() or args.measurements.stat().st_size > 16384:
        raise SystemExit("INVALID_OR_OVERSIZE_MEASUREMENTS")
    result = inspect(json.loads(args.measurements.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "AA1_EVIDENCE_REVIEW_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
