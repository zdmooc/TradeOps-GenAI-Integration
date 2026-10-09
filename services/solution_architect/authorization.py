"""D-099 AA2 isolated policy-gateway prototype. NO external tool execution.

Trusted adapters must supply authenticated principal and verified scope. The
runtime must fetch the versioned canonical role-profiles.json from the method
owner and pass its validated profiles; this module cannot validate IAM itself.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping

from services.security.identity import SecurityPrincipal

# The fail-closed operations are invariant even when a supplied role file is
# accidentally relaxed. This is an allowlist of abstract operations, NEVER
# an unrestricted shell or Kubernetes client interface.
READ_ACTIONS = frozenset({"repo.read", "repo.diff", "oc.get", "oc.describe", "oc.logs"})
OTHER_ACTIONS = frozenset({"repo.edit", "repo.tests", "repo.commit"})
SUPPORTED_ACTIONS = READ_ACTIONS | OTHER_ACTIONS
HARD_DENY = frozenset({
    "git push", "git reset --hard", "git clean -fdx", "rm -rf",
    "oc apply", "oc delete", "kubectl apply", "kubectl delete",
    "argocd app sync", "helm upgrade", "docker system prune",
})
VALID_ROLES = frozenset({
    "maya-architect", "maya-reviewer", "maya-builder", "maya-openshift-reader"
})
ACTION_TO_PROFILE = {
    "repo.read": "read", "repo.diff": "git_diff",
    "repo.edit": "edit", "repo.tests": "tests", "repo.commit": "commit",
    "oc.get": "oc_get", "oc.describe": "oc_describe", "oc.logs": "oc_logs",
}


@dataclass(frozen=True, slots=True)
class ScopedRequest:
    action: str
    tenant: str
    repository: str = ""
    file_path: str = ""
    namespace: str = ""


@dataclass(frozen=True, slots=True)
class TrustedScope:
    """This must be supplied by trusted authz config, NEVER model output."""

    tenant: str
    repositories: frozenset[str]
    namespaces: frozenset[str]
    editable_files: frozenset[str]


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    code: str


@dataclass(slots=True)
class _Ticket:
    subject: str
    request_hash: str
    approver: str
    expires_at: float
    consumed: bool = False


class ApprovalRegistry:
    """In-memory demo ledger only. Production requires durable atomic storage."""

    def __init__(self) -> None:
        self._tickets: dict[str, _Ticket] = {}
        self._lock = threading.Lock()

    @staticmethod
    def fingerprint(subject: str, req: ScopedRequest) -> str:
        data = {
            "subject": subject, "action": req.action, "tenant": req.tenant,
            "repository": req.repository, "file_path": req.file_path,
            "namespace": req.namespace,
        }
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def issue(
        self, *, approver: SecurityPrincipal, approver_scope: TrustedScope,
        target: SecurityPrincipal, req: ScopedRequest, ttl_seconds: int = 60,
        now: float | None = None,
    ) -> str:
        if (approver.authn_method != "oidc-jwt"
                or "human-approver" not in approver.roles
                or not approver.subject or approver.subject == target.subject
                or not target.subject or req.tenant != approver_scope.tenant
                or ttl_seconds < 1 or ttl_seconds > 900
                or req.action not in {"repo.edit", "repo.tests", "repo.commit"}
                or req.repository not in approver_scope.repositories
                or (req.action == "repo.edit" and
                    (not _safe_repo_path(req.file_path)
                     or req.file_path not in approver_scope.editable_files))):
            raise PermissionError("INDEPENDENT_APPROVAL_REQUIRED")
        # Do not allow a credential-bearing model to issue its own approval.
        # The caller must not expose this method as an agent tool.
        now = time.time() if now is None else now
        ticket_id = secrets.token_urlsafe(32)
        with self._lock:
            self._tickets[ticket_id] = _Ticket(
                target.subject, self.fingerprint(target.subject, req),
                approver.subject, now + ttl_seconds
            )
        return ticket_id

    def consume(self, token: str | None, subject: str, req: ScopedRequest,
                now: float | None = None) -> bool:
        if not token:
            return False
        now = time.time() if now is None else now
        with self._lock:
            item = self._tickets.get(token)
            if (item is None or item.consumed or now >= item.expires_at
                    or item.subject != subject
                    or item.request_hash != self.fingerprint(subject, req)):
                return False
            item.consumed = True
            return True


def _safe_repo_path(path: str) -> bool:
    if not path or path.startswith(("/", "\\")) or "\\" in path or "\x00" in path:
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} or ":" in part for part in parts):
        return False
    lowered = [part.casefold() for part in parts]
    sensitive = {".git", ".ssh", ".aws", ".kube", "secrets", "secret",
                 "credentials", "id_rsa", "id_ed25519"}
    if any(part.startswith(".env") or "kubeconfig" in part
           or part in sensitive for part in lowered):
        return False
    name = lowered[-1]
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".kdbx")):
        return False
    return True


class MayaPolicyGate:
    """Policy evaluation only. Does not run Git, shell or Kubernetes actions."""

    def __init__(self, profile_document: Mapping[str, Any],
                 registry: ApprovalRegistry | None = None) -> None:
        self._profiles = profile_document.get("profiles", {})
        self._registry = registry or ApprovalRegistry()
        if (profile_document.get("default_decision") != "DENY"
                or not VALID_ROLES.issubset(self._profiles)):
            raise ValueError("INVALID_CANONICAL_ROLE_POLICY")
        for role, rules in self._profiles.items():
            if role not in VALID_ROLES or not isinstance(rules, dict):
                raise ValueError("UNKNOWN_ROLE_OR_RULES")
            if any(value not in {"ALLOW", "ASK", "DENY", "ALLOW_SCOPED"}
                   for key, value in rules.items() if key not in {"workspace"}):
                raise ValueError("INVALID_ROLE_PERMISSION")
        if any(self._profiles.get(role, {}).get("git_push") != "DENY"
               for role in ("maya-architect", "maya-reviewer", "maya-builder")):
            raise ValueError("WEAKENED_PUSH_POLICY")
        if (self._profiles["maya-openshift-reader"].get("oc_apply") != "DENY"
                or self._profiles["maya-openshift-reader"].get("oc_delete") != "DENY"):
            raise ValueError("WEAKENED_CLUSTER_POLICY")

    def evaluate(
        self, *, principal: SecurityPrincipal | None,
        scope: TrustedScope, request: ScopedRequest,
        approval_token: str | None = None, now: float | None = None,
    ) -> PolicyDecision:
        if principal is None or not principal.subject or principal.authn_method not in {
            "oidc-jwt", "static"
        }:
            return PolicyDecision(False, "UNAUTHENTICATED")
        active_roles = set(principal.roles) & VALID_ROLES
        if len(active_roles) != 1:
            return PolicyDecision(False, "AMBIGUOUS_ROLE")
        role = next(iter(active_roles))
        # Strong identity is needed before any potentially mutating action;
        # static principals remain limited to read-only prototyping.
        if (request.action in {"repo.edit", "repo.commit"}
                and principal.authn_method != "oidc-jwt"):
            return PolicyDecision(False, "STRONG_AUTH_REQUIRED")
        if request.action in HARD_DENY or request.action not in SUPPORTED_ACTIONS:
            return PolicyDecision(False, "TOOL_DENIED")
        if not scope.tenant or request.tenant != scope.tenant:
            return PolicyDecision(False, "CROSS_TENANT_DENIED")
        if request.action.startswith("repo."):
            if request.repository not in scope.repositories:
                return PolicyDecision(False, "REPOSITORY_DENIED")
            if request.file_path and not _safe_repo_path(request.file_path):
                return PolicyDecision(False, "UNSAFE_PATH_DENIED")
            if request.action == "repo.edit":
                if not request.file_path or request.file_path not in scope.editable_files:
                    return PolicyDecision(False, "FILE_SCOPE_DENIED")
        if request.action.startswith("oc."):
            if not request.namespace or request.namespace not in scope.namespaces:
                return PolicyDecision(False, "NAMESPACE_DENIED")
        decision = self._profiles[role].get(ACTION_TO_PROFILE[request.action], "DENY")
        if decision == "DENY":
            return PolicyDecision(False, "ROLE_DENIED")
        if decision == "ASK":
            if not self._registry.consume(approval_token, principal.subject, request, now):
                return PolicyDecision(False, "HUMAN_APPROVAL_REQUIRED")
        elif decision not in {"ALLOW", "ALLOW_SCOPED"}:
            return PolicyDecision(False, "INVALID_POLICY")
        return PolicyDecision(True, "ALLOWED")
