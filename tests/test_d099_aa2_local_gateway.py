"""AA2 real file access checks using pytest tmp_path, never live Git/CRC."""
import pytest

from services.security.identity import SecurityPrincipal
from services.solution_architect.authorization import (
    MayaPolicyGate, ScopedRequest, TrustedScope
)
from services.solution_architect.local_evidence_gateway import LocalEvidenceGateway


POLICY = {"default_decision": "DENY", "profiles": {
    "maya-architect": {"read": "ALLOW", "edit": "DENY", "git_push": "DENY"},
    "maya-reviewer": {"read": "ALLOW", "edit": "DENY", "git_push": "DENY"},
    "maya-builder": {"read": "ALLOW", "edit": "ASK", "git_push": "DENY"},
    "maya-openshift-reader": {"oc_apply": "DENY", "oc_delete": "DENY"}
}}
REPO = "zdmooc/aa2-ci-fixture"


def principal(role="maya-architect"):
    return SecurityPrincipal("ci-operator", frozenset({role}),
                             frozenset(), "oidc-jwt", "https://issuer.test")


def scope(tenant="a", repos=frozenset({REPO})):
    return TrustedScope(tenant, repos, frozenset({"test"}), frozenset())


def read(path="docs/readme.md", repository=REPO, tenant="a", action="repo.read"):
    return ScopedRequest(action, tenant, repository, path)


@pytest.fixture
def fixture(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("D099 evidence\n", encoding="utf-8")
    events = []
    return LocalEvidenceGateway(policy=MayaPolicyGate(POLICY),
                                repo_roots={REPO: tmp_path}, audit=events), events, tmp_path


def test_scoped_real_read_and_audit(fixture):
    gateway, events, _ = fixture
    res = gateway.read(principal=principal(), scope=scope(), request=read())
    assert res.allowed and res.content == "D099 evidence\n"
    assert res.sha256 and res.size_bytes == len("D099 evidence\n")
    assert events[-1]["content_sha256"] == res.sha256
    assert "content" not in events[-1]


@pytest.mark.parametrize("req,code", [
    (read(tenant="b"), "CROSS_TENANT_DENIED"),
    (read(repository="zdmooc/other"), "REPOSITORY_DENIED"),
    (read("../outside"), "UNSAFE_PATH_DENIED"),
    (read(".env"), "UNSAFE_PATH_DENIED"),
    (read("docs/readme.md", action="repo.edit"), "FILE_SCOPE_DENIED"),
    (read("docs/readme.md", action="shell.exec"), "TOOL_DENIED"),
])
def test_denial_never_returns_content(fixture, req, code):
    gateway, events, _ = fixture
    res = gateway.read(principal=principal(), scope=scope(),
                       request=req)
    assert res.code == code and not res.allowed and res.content is None
    assert events[-1]["allowed"] is False


def test_unknown_root_fails_after_auth(fixture):
    gateway, events, _ = fixture
    res = gateway.read(principal=principal(), scope=scope(repos=frozenset({"other"})),
                       request=read(repository="other"))
    assert res.code == "ROOT_NOT_CONFIGURED" and not res.allowed


def test_symlink_escape_denied(fixture):
    gateway, _, root = fixture
    secret = root.parent / "private.txt"
    secret.write_text("SECRET", encoding="utf-8")
    link = root / "docs" / "leak.md"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable in runner")
    res = gateway.read(principal=principal(), scope=scope(),
                       request=read("docs/leak.md"))
    assert res.code == "SYMLINK_DENIED" and res.content is None


def test_oversized_file_denied(fixture):
    gateway, _, root = fixture
    (root / "docs" / "large.md").write_bytes(b"x" * (128 * 1024 + 1))
    assert gateway.read(principal=principal(), scope=scope(),
                        request=read("docs/large.md")).code == "READ_SIZE_LIMIT"


def test_unapproved_extension_denied(fixture):
    gateway, _, root = fixture
    (root / "docs" / "binary.exe").write_bytes(b"no")
    assert gateway.read(principal=principal(), scope=scope(),
                        request=read("docs/binary.exe")).code == "EXTENSION_NOT_ALLOWED"


def test_no_principal_denied(fixture):
    gateway, _, _ = fixture
    res = gateway.read(principal=None, scope=scope(), request=read())
    assert res.code == "UNAUTHENTICATED"
