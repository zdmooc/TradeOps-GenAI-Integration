"""D099 test policy SHA-pin and tamper rejection with synthetic docs only."""
import hashlib
import json

import pytest

from services.solution_architect.policy_loader import load_policy


def sample():
    return {
        "version": "D099-AA2-v1",
        "default_decision": "DENY",
        "profiles": {
            "maya-architect": {"read": "ALLOW", "git_push": "DENY"},
            "maya-reviewer": {"git_push": "DENY"},
            "maya-builder": {"git_push": "DENY"},
            "maya-openshift-reader": {"oc_apply": "DENY", "oc_delete": "DENY"},
        },
    }


def fixture(tmp_path, doc=None):
    path = tmp_path / "role-profiles.json"
    path.write_text(json.dumps(doc if doc is not None else sample()),
                    encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


def test_load_pinned_policy_offline(tmp_path):
    path, digest = fixture(tmp_path)
    assert load_policy(path, expected_sha256=digest) is not None


def test_tampered_policy_denied(tmp_path):
    path, digest = fixture(tmp_path)
    path.write_text(json.dumps({"version": "D099-AA2-v1", "profiles": {}}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="POLICY_DIGEST_MISMATCH"):
        load_policy(path, expected_sha256=digest)


def test_missing_expected_digest_denied(tmp_path):
    path, _ = fixture(tmp_path)
    with pytest.raises(ValueError, match="MISSING_TRUSTED_POLICY_DIGEST"):
        load_policy(path, expected_sha256="")


def test_policy_version_mismatch_denied(tmp_path):
    doc = sample()
    doc["version"] = "D099-AA2-v2"
    path, digest = fixture(tmp_path, doc)
    with pytest.raises(ValueError, match="POLICY_VERSION_OR_DENY_MISMATCH"):
        load_policy(path, expected_sha256=digest)


def test_invalid_role_even_with_matching_hash_denied(tmp_path):
    doc = sample()
    doc["profiles"]["maya-builder"]["git_push"] = "ALLOW"
    path, digest = fixture(tmp_path, doc)
    with pytest.raises(ValueError, match="WEAKENED_PUSH_POLICY"):
        load_policy(path, expected_sha256=digest)


def test_symlinked_policy_denied(tmp_path):
    origin, digest = fixture(tmp_path)
    link = tmp_path / "link.json"
    try:
        link.symlink_to(origin)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError, match="UNTRUSTED_POLICY_FILE"):
        load_policy(link, expected_sha256=digest)
