"""D099 AA2 in-memory native MCP adapter for one deterministic read-only tool.

No standalone network listener or stdio launch. Identity and scope MUST come
from a trusted host; caller-supplied model arguments never control either.
This is a protocol adapter, not a deployed OpenCode/Keycloak integration.
"""
from __future__ import annotations

from collections.abc import Callable

from mcp.server import MCPServer

from services.security.identity import SecurityPrincipal
from services.solution_architect.authorization import ScopedRequest, TrustedScope
from services.solution_architect.local_evidence_gateway import LocalEvidenceGateway


def build_evidence_mcp(
    *,
    gateway: LocalEvidenceGateway,
    trusted_scope: TrustedScope,
    principal_from_host: Callable[[], SecurityPrincipal | None],
) -> MCPServer:
    """Create in-memory MCP tools; never run a public MCP server."""
    if not trusted_scope.tenant or not trusted_scope.repositories:
        raise ValueError("NO_TRUSTED_SCOPE")
    if not callable(principal_from_host):
        raise ValueError("NO_TRUSTED_IDENTITY_RESOLVER")

    server = MCPServer("Maya D099 Evidence Read Only")

    @server.tool(name="maya.read_evidence")
    def maya_read_evidence(repository: str, file_path: str) -> dict[str, object]:
        """Read one approved UTF-8 source file; no Git, shell or OpenShift."""
        principal = principal_from_host()
        request = ScopedRequest(
            action="repo.read",
            tenant=trusted_scope.tenant,
            repository=repository,
            file_path=file_path,
        )
        result = gateway.read(
            principal=principal, scope=trusted_scope, request=request,
        )
        # Explicit structured results: denied calls include no data. No
        # exception or tool metadata discloses content on denial.
        return {
            "allowed": result.allowed,
            "code": result.code,
            "content": result.content if result.allowed else None,
            "sha256": result.sha256 if result.allowed else None,
            "size_bytes": result.size_bytes if result.allowed else 0,
        }

    return server
