"""D099 AA2 MCP protocol tests: in-memory MCP with disposable source files."""
from __future__ import annotations

import asyncio

from mcp import Client

from services.security.identity import SecurityPrincipal
from services.solution_architect.authorization import MayaPolicyGate, TrustedScope
from services.solution_architect.local_evidence_gateway import LocalEvidenceGateway
from services.solution_architect.mcp_evidence import build_evidence_mcp

REPO = "zdmooc/aa2-disposable-fixture"
POLICY = {
    "default_decision": "DENY",
    "profiles": {
        "maya-architect": {"read": "ALLOW", "git_push": "DENY"},
        "maya-reviewer": {"read": "ALLOW", "git_push": "DENY"},
        "maya-builder": {"read": "ALLOW", "git_push": "DENY"},
        "maya-openshift-reader": {"oc_get": "ALLOW_SCOPED",
                                 "oc_apply": "DENY", "oc_delete": "DENY"},
    },
}


def identity():
    return SecurityPrincipal(
        subject="trusted-fixture-principal",
        roles=frozenset({"maya-architect"}),
        scopes=frozenset({"repo.read"}),
        authn_method="oidc-jwt",
        issuer="https://issuer.invalid",
    )


def make_server(tmp_path, *, resolver=identity):
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "mission.md").write_text(
        "Read-only mission evidence\n", encoding="utf-8"
    )
    audit = []
    gateway = LocalEvidenceGateway(
        policy=MayaPolicyGate(POLICY),
        repo_roots={REPO: tmp_path},
        audit=audit,
    )
    scope = TrustedScope(
        tenant="ci-tenant",
        repositories=frozenset({REPO}),
        namespaces=frozenset(),
        editable_files=frozenset(),
    )
    server = build_evidence_mcp(
        gateway=gateway,
        trusted_scope=scope,
        principal_from_host=resolver,
    )
    return server, audit


def test_mcp_discovery_and_real_read_only_protocol(tmp_path):
    server, audit = make_server(tmp_path)

    async def scenario():
        async with Client(server, raise_exceptions=True) as client:
            tools = await client.list_tools()
            assert {t.name for t in tools.tools} == {"maya.read_evidence"}
            result = await client.call_tool(
                "maya.read_evidence",
                {"repository": REPO, "file_path": "docs/mission.md"},
            )
            assert result.is_error is False
            data = result.structured_content
            assert data is not None
            assert data["allowed"] is True
            assert data["code"] == "READ_ALLOWED"
            assert data["content"] == "Read-only mission evidence\n"
            assert len(data["sha256"]) == 64

    asyncio.run(scenario())
    assert len(audit) == 1
    assert audit[0]["allowed"] is True
    assert "content" not in audit[0]


def test_mcp_rejects_unauthenticated_and_repo_escape(tmp_path):
    server, audit = make_server(tmp_path, resolver=lambda: None)

    async def scenario():
        async with Client(server, raise_exceptions=True) as client:
            for repo, path in ((REPO, "docs/mission.md"),
                               (REPO, "../secrets.txt"),
                               ("zdmooc/unapproved", "docs/mission.md")):
                result = await client.call_tool(
                    "maya.read_evidence",
                    {"repository": repo, "file_path": path},
                )
                data = result.structured_content
                assert data is not None
                assert data["allowed"] is False
                assert data["content"] is None

    asyncio.run(scenario())
    assert len(audit) == 3
    assert all(not e["allowed"] for e in audit)


def test_mcp_denies_unapproved_repo_with_authenticated_principal(tmp_path):
    server, audit = make_server(tmp_path)

    async def scenario():
        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool(
                "maya.read_evidence",
                {"repository": "zdmooc/other", "file_path": "docs/mission.md"},
            )
            data = result.structured_content
            assert data is not None
            assert data["allowed"] is False
            assert data["code"] == "REPOSITORY_DENIED"

    asyncio.run(scenario())
    assert audit[-1]["code"] == "REPOSITORY_DENIED"


def test_mcp_does_not_expose_mutating_tools(tmp_path):
    server, _ = make_server(tmp_path)

    async def scenario():
        async with Client(server, raise_exceptions=True) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            assert "bash" not in names
            assert "oc.apply" not in names
            assert "repo.edit" not in names
            assert "oms.place_order" not in names

    asyncio.run(scenario())
