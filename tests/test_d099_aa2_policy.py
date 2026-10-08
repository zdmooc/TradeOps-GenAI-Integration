"""D-099 policy-gate safety tests on synthetic identities and memory ledger."""
import pytest

from services.security.identity import SecurityPrincipal
from services.solution_architect.authorization import (
    ApprovalRegistry, MayaPolicyGate, ScopedRequest, TrustedScope
)

POLICY = {
    "default_decision": "DENY",
    "profiles": {
        "maya-architect": {"read": "ALLOW", "search": "ALLOW", "git_push": "DENY",
                           "edit": "DENY"},
        "maya-reviewer": {"read": "ALLOW", "git_diff": "ALLOW", "tests": "ASK",
                          "edit": "DENY", "git_push": "DENY"},
        "maya-builder": {"read": "ALLOW", "edit": "ASK", "tests": "ALLOW",
                         "commit": "ASK", "git_push": "DENY"},
        "maya-openshift-reader": {"oc_get": "ALLOW_SCOPED",
                                 "oc_describe": "ALLOW_SCOPED",
                                 "oc_logs": "ALLOW_SCOPED", "oc_apply": "DENY",
                                 "oc_delete": "DENY"},
    },
}
SCOPE = TrustedScope(
    tenant="bank-a", repositories=frozenset({"zdmooc/test-sandbox"}),
    namespaces=frozenset({"d099-read"}), editable_files=frozenset({"docs/adr.md"}),
)


def principal(role="maya-architect", subject="agent", method="oidc-jwt"):
    return SecurityPrincipal(subject, frozenset({role}), frozenset(),
                             method, "https://issuer.example")


def request(action, *, tenant="bank-a", repository="zdmooc/test-sandbox",
            file_path="", namespace=""):
    return ScopedRequest(action, tenant, repository, file_path, namespace)


def test_scoped_read_allowed():
    gate = MayaPolicyGate(POLICY)
    assert gate.evaluate(principal=principal(), scope=SCOPE,
                         request=request("repo.read")).code == "ALLOWED"
    assert gate.evaluate(principal=principal("maya-openshift-reader"),
                         scope=SCOPE, request=request("oc.get", namespace="d099-read")).allowed


@pytest.mark.parametrize("act", ["git push", "oc apply", "kubectl delete",
                                 "argocd app sync", "shell.exec", "git.reset"])
def test_unknown_or_sensitive_actions_are_denied(act):
    assert MayaPolicyGate(POLICY).evaluate(
        principal=principal("maya-builder"), scope=SCOPE,
        request=request(act)).code == "TOOL_DENIED"


def test_unauthenticated_or_multi_role_denied():
    gate = MayaPolicyGate(POLICY)
    req = request("repo.read")
    assert gate.evaluate(principal=None, scope=SCOPE, request=req).code == "UNAUTHENTICATED"
    both = SecurityPrincipal("agent", frozenset({"maya-builder", "maya-architect"}),
                             frozenset(), "oidc-jwt")
    assert gate.evaluate(principal=both, scope=SCOPE, request=req).code == "AMBIGUOUS_ROLE"


def test_cross_tenant_and_namespace_denied():
    gate = MayaPolicyGate(POLICY)
    assert gate.evaluate(principal=principal(), scope=SCOPE,
                         request=request("repo.read", tenant="bank-b")).code == "CROSS_TENANT_DENIED"
    assert gate.evaluate(principal=principal("maya-openshift-reader"),
                         scope=SCOPE, request=request("oc.logs", namespace="tradeops")).code == "NAMESPACE_DENIED"


@pytest.mark.parametrize("file_path", ["../credentials", "/etc/passwd", ".env",
                                        "config/../../a", ".aws/credentials",
                                        "docs\\..\\danger"])
def test_unsafe_path_refused(file_path):
    gate = MayaPolicyGate(POLICY)
    assert gate.evaluate(principal=principal("maya-builder"), scope=SCOPE,
                         request=request("repo.edit", file_path=file_path)).code == "UNSAFE_PATH_DENIED"


def test_file_scope_and_missing_approval():
    gate = MayaPolicyGate(POLICY)
    assert gate.evaluate(principal=principal("maya-builder"), scope=SCOPE,
                         request=request("repo.edit", file_path="other.md")).code == "FILE_SCOPE_DENIED"
    assert gate.evaluate(principal=principal("maya-builder"), scope=SCOPE,
                         request=request("repo.edit", file_path="docs/adr.md")).code == "HUMAN_APPROVAL_REQUIRED"


def test_human_approval_is_action_bound_expiring_and_single_use():
    registry = ApprovalRegistry()
    gate = MayaPolicyGate(POLICY, registry)
    builder = principal("maya-builder", "builder")
    approver = principal("human-approver", "human")
    req = request("repo.edit", file_path="docs/adr.md")
    ticket = registry.issue(approver=approver, approver_scope=SCOPE, target=builder,
                            req=req, ttl_seconds=30, now=100.0)
    altered = request("repo.commit", file_path="docs/adr.md")
    assert not gate.evaluate(principal=builder, scope=SCOPE,
                             request=altered, approval_token=ticket, now=101).allowed
    allowed = gate.evaluate(principal=builder, scope=SCOPE, request=req,
                            approval_token=ticket, now=101)
    assert allowed.code == "ALLOWED"
    assert gate.evaluate(principal=builder, scope=SCOPE, request=req,
                         approval_token=ticket, now=102).code == "HUMAN_APPROVAL_REQUIRED"
    expired = registry.issue(approver=approver, approver_scope=SCOPE, target=builder,
                             req=req, ttl_seconds=1, now=100)
    assert gate.evaluate(principal=builder, scope=SCOPE, request=req,
                         approval_token=expired, now=102).code == "HUMAN_APPROVAL_REQUIRED"


def test_model_cannot_self_approve():
    registry = ApprovalRegistry()
    req = request("repo.edit", file_path="docs/adr.md")
    with pytest.raises(PermissionError, match="INDEPENDENT_APPROVAL_REQUIRED"):
        registry.issue(approver=principal("maya-builder", "builder"), approver_scope=SCOPE,
                       target=principal("maya-builder", "builder"), req=req)


def test_policy_config_fail_closed():
    weak = {"default_decision": "DENY", "profiles": {
        **POLICY["profiles"],
        "maya-builder": {**POLICY["profiles"]["maya-builder"], "git_push": "ALLOW"},
    }}
    with pytest.raises(ValueError, match="WEAKENED_PUSH_POLICY"):
        MayaPolicyGate(weak)
