"""D099 AA2: fail-closed canonical policy loading by independently pinned SHA-256.

The caller MUST supply the trusted expected hash from an approved hub revision.
No network, no agent-controlled path/hash, no tools executed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from services.solution_architect.authorization import MayaPolicyGate


def load_policy(path: Path, *, expected_sha256: str,
                expected_version: str = "D099-AA2-v1") -> MayaPolicyGate:
    """Load a trusted policy document; prevent unpinned or modified profiles."""
    if (len(expected_sha256) != 64
            or any(char not in "0123456789abcdef" for char in expected_sha256)):
        raise ValueError("MISSING_TRUSTED_POLICY_DIGEST")
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("UNTRUSTED_POLICY_FILE")
    try:
        if candidate.stat().st_size > 65536:
            raise ValueError("POLICY_TOO_LARGE")
        source = candidate.read_bytes()
        if len(source) > 65536:
            raise ValueError("POLICY_TOO_LARGE")
        observed = hashlib.sha256(source).hexdigest()
        if not hmac.compare_digest(observed, expected_sha256):
            raise ValueError("POLICY_DIGEST_MISMATCH")
        document = json.loads(source.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("POLICY_UNREADABLE") from exc
    if (not isinstance(document, dict)
            or document.get("version") != expected_version
            or document.get("default_decision") != "DENY"):
        raise ValueError("POLICY_VERSION_OR_DENY_MISMATCH")
    # The declared stage is DESIGNED_NOT_ENFORCED in the architecture hub.
    # Loading it doesn't magically turn it into production enforcement.
    return MayaPolicyGate(document)
