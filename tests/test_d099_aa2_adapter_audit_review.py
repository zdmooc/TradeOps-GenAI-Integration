"""Adapter-side AA2 event validation; all identities and files synthetic."""
from services.solution_architect.adapter_audit_review import review_events


def event(**kw):
    data = {
        "kind": "d099.aa2.local_repo_read", "subject": "host-subject",
        "action": "repo.read", "tenant": "t1",
        "repository": "lab/repo", "allowed": True,
        "code": "READ_ALLOWED", "content_sha256": "a" * 64,
    }
    data.update(kw)
    return data


def inspect(events):
    return review_events(events, trusted_subject="host-subject",
                         trusted_tenant="t1",
                         allowed_repositories=frozenset({"lab/repo"}))


def test_host_generated_allow_and_deny_can_be_reviewed_but_not_attested():
    e = [event(),
         event(allowed=False, code="REPOSITORY_DENIED",
               repository="lab/other", content_sha256=None)]
    r = inspect(e)
    assert r["status"] == "AA2_ADAPTER_AUDIT_IN_MEMORY_PASS"
    assert r["read_count"] == 1
    assert r["denial_count"] == 1
    assert r["independent_durable_audit"] is False
    assert r["AA2_RUNTIME_ENFORCEMENT_VALIDATED"] is False


def test_cross_tenant_or_unapproved_read_cannot_pass():
    e = [event(tenant="other", repository="lab/other")]
    v = inspect(e)["violations"]
    assert "CROSS_TENANT_EVENT" in v
    assert "UNSCOPED_OR_UNVERIFIED_ALLOWED_READ" in v


def test_no_events_and_model_supplied_fields_fail_closed():
    assert "NO_HOST_EVENTS" in inspect([])["violations"]
    e = [event(raw_content="SECRET", model_decision="allow")]
    assert "UNEXPECTED_AUDIT_EVENT_FIELDS" in inspect(e)["violations"]


def test_denial_must_have_no_content_hash():
    e = [event(allowed=False, code="REPOSITORY_DENIED")]
    assert "INVALID_DENIAL_RECORD" in inspect(e)["violations"]


def test_malicious_tool_name_and_subject_denied():
    e = [event(action="oc.apply", subject="model")]
    v = inspect(e)["violations"]
    assert "FORBIDDEN_ACTION_ALLOWED" in v
    assert "UNTRUSTED_SUBJECT_EVENT" in v


def test_boolean_coercion_is_not_trusted():
    e = [event(allowed="true")]
    assert "NON_BOOLEAN_AUDIT_DECISION" in inspect(e)["violations"]


def test_actual_local_gateway_events_are_reviewed(tmp_path):
    """Exercise the host adapter itself, not manually invented event objects."""
    from services.security.identity import SecurityPrincipal
    from services.solution_architect.authorization import (
        MayaPolicyGate, ScopedRequest, TrustedScope,
    )
    from services.solution_architect.local_evidence_gateway import LocalEvidenceGateway
    repo = "lab/repo"
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "mission.md").write_text(
        "Fictional offline evidence", encoding="utf-8")
    policy = {"default_decision": "DENY", "profiles": {
        "maya-architect": {"read": "ALLOW", "git_push": "DENY"},
        "maya-reviewer": {"git_push": "DENY"},
        "maya-builder": {"git_push": "DENY"},
        "maya-openshift-reader": {"oc_apply": "DENY", "oc_delete": "DENY"},
    }}
    identity = SecurityPrincipal("host-subject", frozenset({"maya-architect"}),
                                 frozenset(), "oidc-jwt", "https://issuer.invalid")
    scope = TrustedScope("t1", frozenset({repo}), frozenset(), frozenset())
    audit = []
    gateway = LocalEvidenceGateway(policy=MayaPolicyGate(policy),
                                   repo_roots={repo: tmp_path}, audit=audit)
    assert gateway.read(
        principal=identity, scope=scope,
        request=ScopedRequest("repo.read", "t1", repo, "docs/mission.md")
    ).allowed
    assert not gateway.read(
        principal=identity, scope=scope,
        request=ScopedRequest("repo.read", "t2", repo, "docs/mission.md")
    ).allowed
    assert not gateway.read(
        principal=identity, scope=scope,
        request=ScopedRequest("oc.apply", "t1", repo, namespace="production")
    ).allowed
    result = inspect(audit)
    assert result["status"] == "AA2_ADAPTER_AUDIT_IN_MEMORY_PASS"
    assert result["read_count"] == 1
    assert result["denial_count"] == 2
    assert result["independent_durable_audit"] is False
