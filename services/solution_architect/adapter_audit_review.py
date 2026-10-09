"""D099 AA2 adapter-origin audit review, in-memory test scope ONLY.

Not a durable audit, cryptographic signature, or identity attestation.
No model receives this list or controls the expected host identity/scope.
"""
from __future__ import annotations
import re
from typing import Any

SHA256 = re.compile(r"[a-f0-9]{64}\Z")
SAFE_CODES = {
    "READ_ALLOWED", "UNAUTHENTICATED", "AMBIGUOUS_ROLE", "STRONG_AUTH_REQUIRED",
    "TOOL_DENIED", "CROSS_TENANT_DENIED", "REPOSITORY_DENIED",
    "UNSAFE_PATH_DENIED", "ROLE_DENIED", "INVALID_POLICY",
    "ROOT_NOT_CONFIGURED", "INVALID_PATH", "FILE_UNAVAILABLE",
    "SYMLINK_DENIED", "PATH_ESCAPE_OR_NONFILE", "EXTENSION_NOT_ALLOWED",
    "READ_SIZE_LIMIT", "ADAPTER_READ_ONLY",
}


def review_events(events: object, *, trusted_subject: str,
                  trusted_tenant: str,
                  allowed_repositories: frozenset[str]) -> dict[str, Any]:
    violations: list[str] = []
    passed = 0
    denied = 0
    if not isinstance(trusted_subject, str) or not trusted_subject or (
        not isinstance(trusted_tenant, str) or not trusted_tenant or
        not isinstance(allowed_repositories, frozenset) or
        not allowed_repositories
    ):
        violations.append("HOST_EXPECTATIONS_REQUIRED")
    if not isinstance(events, list) or not events:
        return {
            "status": "AA2_ADAPTER_AUDIT_INCOMPLETE",
            "violations": ["NO_HOST_EVENTS"] + violations,
            "read_count": 0, "denial_count": 0,
            "source": "HOST_ADAPTER_IN_MEMORY_UNATTESTED",
            "independent_durable_audit": False,
            "AA2_RUNTIME_ENFORCEMENT_VALIDATED": False,
        }
    for entry in events:
        if not isinstance(entry, dict):
            violations.append("MALFORMED_HOST_EVENT")
            continue
        if set(entry) != {
            "kind", "subject", "action", "tenant", "repository",
            "allowed", "code", "content_sha256",
        }:
            violations.append("UNEXPECTED_AUDIT_EVENT_FIELDS")
        if entry.get("kind") != "d099.aa2.local_repo_read" or (
            entry.get("action") != "repo.read"
        ):
            violations.append("UNEXPECTED_TOOL_ACTION")
        if entry.get("subject") != trusted_subject and entry.get(
            "subject"
        ) != "UNAUTHENTICATED":
            violations.append("UNTRUSTED_SUBJECT_EVENT")
        if entry.get("tenant") != trusted_tenant:
            violations.append("CROSS_TENANT_EVENT")
        if type(entry.get("allowed")) is not bool:
            violations.append("NON_BOOLEAN_AUDIT_DECISION")
        elif entry["allowed"]:
            passed += 1
            if entry.get("subject") != trusted_subject or (
                entry.get("repository") not in allowed_repositories
            ) or entry.get("code") != "READ_ALLOWED" or not (
                isinstance(entry.get("content_sha256"), str) and
                SHA256.fullmatch(entry["content_sha256"])
            ):
                violations.append("UNSCOPED_OR_UNVERIFIED_ALLOWED_READ")
        else:
            denied += 1
            if entry.get("code") not in SAFE_CODES - {"READ_ALLOWED"} or (
                entry.get("content_sha256") is not None
            ):
                violations.append("INVALID_DENIAL_RECORD")
    return {
        "status": ("AA2_ADAPTER_AUDIT_IN_MEMORY_PASS" if not violations
                   else "AA2_ADAPTER_AUDIT_INCOMPLETE"),
        "violations": sorted(set(violations)),
        "read_count": passed,
        "denial_count": denied,
        "source": "HOST_ADAPTER_IN_MEMORY_UNATTESTED",
        "independent_durable_audit": False,
        "AA2_RUNTIME_ENFORCEMENT_VALIDATED": False,
    }
