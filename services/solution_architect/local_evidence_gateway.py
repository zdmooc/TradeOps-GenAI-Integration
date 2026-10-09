"""AA2: narrowly scoped read-only file adapter with a real policy check.

No shell/Git/HTTP/kube commands, no mutating actions. A host-side authenticated
principal and trusted repo-to-root mapping are REQUIRED (never LLM-originated).
Tests use disposable temp directories; this is not yet an OpenCode gateway.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from services.security.identity import SecurityPrincipal
from services.solution_architect.authorization import (
    MayaPolicyGate, ScopedRequest, TrustedScope, _safe_repo_path,
)

MAX_BYTES = 128 * 1024
SUPPORTED_SUFFIXES = frozenset({
    ".md", ".py", ".go", ".json", ".yaml", ".yml", ".toml", ".sh", ".sql", ".txt"
})


@dataclass(frozen=True, slots=True)
class EvidenceResult:
    allowed: bool
    code: str
    content: str | None
    sha256: str | None
    size_bytes: int


class LocalEvidenceGateway:
    """Read an allowlisted repository file after a server-side policy decision."""

    def __init__(self, *, policy: MayaPolicyGate,
                 repo_roots: Mapping[str, Path],
                 audit: list[dict[str, Any]] | None = None) -> None:
        if not repo_roots:
            raise ValueError("NO_TRUSTED_REPOSITORY_ROOTS")
        self._policy = policy
        self._roots = {key: Path(value).resolve(strict=True)
                       for key, value in repo_roots.items()}
        if any(not root.is_dir() for root in self._roots.values()):
            raise ValueError("INVALID_REPOSITORY_ROOT")
        self._audit = audit if audit is not None else []

    def _record(self, *, principal: SecurityPrincipal | None,
                request: ScopedRequest, code: str,
                allowed: bool, sha256: str | None = None) -> None:
        # No raw file contents or secrets. Production requires immutable remote audit.
        self._audit.append({
            "kind": "d099.aa2.local_repo_read",
            "subject": principal.subject if principal else "UNAUTHENTICATED",
            "action": request.action,
            "tenant": request.tenant,
            "repository": request.repository,
            "allowed": allowed,
            "code": code,
            "content_sha256": sha256,
        })

    def read(self, *, principal: SecurityPrincipal | None,
             scope: TrustedScope, request: ScopedRequest) -> EvidenceResult:
        decision = self._policy.evaluate(principal=principal, scope=scope, request=request)
        if not decision.allowed:
            self._record(principal=principal, request=request,
                         code=decision.code, allowed=False)
            return EvidenceResult(False, decision.code, None, None, 0)
        if request.action != "repo.read":
            self._record(principal=principal, request=request,
                         code="ADAPTER_READ_ONLY", allowed=False)
            return EvidenceResult(False, "ADAPTER_READ_ONLY", None, None, 0)
        root = self._roots.get(request.repository)
        if root is None:
            self._record(principal=principal, request=request,
                         code="ROOT_NOT_CONFIGURED", allowed=False)
            return EvidenceResult(False, "ROOT_NOT_CONFIGURED", None, None, 0)
        if not _safe_repo_path(request.file_path):
            self._record(principal=principal, request=request,
                         code="INVALID_PATH", allowed=False)
            return EvidenceResult(False, "INVALID_PATH", None, None, 0)
        try:
            relative = Path(request.file_path)
            candidate = root / relative
            # Refuse symlink components (including directory symlinks). Resolve
            # separately to catch unintended root escape.
            if any(piece.is_symlink() for piece in (root / Path(*relative.parts[:idx])
                    for idx in range(1, len(relative.parts) + 1))):
                raise PermissionError("SYMLINK_DENIED")
            actual = candidate.resolve(strict=True)
            if not actual.is_relative_to(root) or not actual.is_file():
                raise PermissionError("PATH_ESCAPE_OR_NONFILE")
            if actual.suffix.casefold() not in SUPPORTED_SUFFIXES:
                raise PermissionError("EXTENSION_NOT_ALLOWED")
            if actual.stat().st_size > MAX_BYTES:
                raise PermissionError("READ_SIZE_LIMIT")
            # A hostile concurrent filesystem actor could still swap a path
            # between checking and opening; do not claim race-free enforcement.
            data = actual.read_bytes()
            if len(data) > MAX_BYTES:
                raise PermissionError("READ_SIZE_LIMIT")
            content = data.decode("utf-8")
        except (OSError, ValueError, PermissionError, UnicodeError) as exc:
            code = str(exc) if isinstance(exc, PermissionError) else "FILE_UNAVAILABLE"
            self._record(principal=principal, request=request, code=code, allowed=False)
            return EvidenceResult(False, code, None, None, 0)
        digest = hashlib.sha256(data).hexdigest()
        self._record(principal=principal, request=request,
                     code="READ_ALLOWED", allowed=True, sha256=digest)
        return EvidenceResult(True, "READ_ALLOWED", content, digest, len(data))
