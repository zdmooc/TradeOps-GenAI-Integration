from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mcp.server.auth.provider import AccessToken

from services.decision_fusion.models import CaseStatus, ExecutionMode, ReviewDecision
from services.decision_fusion.store import DecisionStore, PostgresDecisionStore
from services.mcp_server.governance import Principal, ToolGovernor
from services.mcp_server.tools import TOOL_REGISTRY, execute_tool


class NativeMcpPolicyError(PermissionError):
    def __init__(self, code: str, reason: str):
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


def principal_from_access_token(token: AccessToken | None) -> Principal | None:
    if token is None:
        return None
    return Principal(
        name=token.subject or token.client_id,
        scopes=frozenset(token.scopes),
    )


class NativeMcpGovernor:
    """Apply the existing deterministic ToolGovernor to native MCP calls."""

    def __init__(
        self,
        *,
        governor: ToolGovernor | None = None,
        decision_store: DecisionStore | None = None,
    ) -> None:
        self.governor = governor or ToolGovernor()
        self.decision_store = decision_store or PostgresDecisionStore()

    def execute_read(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        access_token: AccessToken | None,
    ) -> Any:
        execution = self.governor.execute(
            tool_name=tool_name,
            arguments=arguments,
            principal=principal_from_access_token(access_token),
            tool_registry=TOOL_REGISTRY,
            human_approved=False,
            executor=execute_tool,
        )
        if not execution.allowed:
            raise NativeMcpPolicyError(execution.code, execution.reason)
        return execution.result

    def execute_approved_paper_order(
        self,
        *,
        workflow_id: str,
        access_token: AccessToken | None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute only from a server-side APPROVED decision case.

        The MCP caller supplies only the workflow id. Symbol, side and quantity are
        derived from the stored approved proposal, so the model cannot alter the
        approved order parameters after HITL review.
        """
        principal = principal_from_access_token(access_token)
        case = self.decision_store.get(workflow_id)
        if case is None:
            raise NativeMcpPolicyError("WORKFLOW_NOT_FOUND", "approved workflow was not found")

        now = now or datetime.now(timezone.utc)
        approved = (
            case.status is CaseStatus.APPROVED
            and case.review is not None
            and case.review.decision is ReviewDecision.APPROVE
            and case.proposal.execution_mode is ExecutionMode.PAPER
            and case.proposal.input.risk_status.upper() == "ACCEPT"
            and now <= case.proposal.expires_at
        )

        item = case.proposal.input
        arguments = {
            "symbol": item.symbol,
            "side": "BUY" if item.direction.upper() == "LONG" else "SELL",
            "qty": item.qty,
            "workflow_id": workflow_id,
        }
        execution = self.governor.execute(
            tool_name="oms.place_order",
            arguments=arguments,
            principal=principal,
            tool_registry=TOOL_REGISTRY,
            human_approved=approved,
            executor=execute_tool,
        )
        if not execution.allowed:
            raise NativeMcpPolicyError(execution.code, execution.reason)
        if not isinstance(execution.result, dict):
            raise NativeMcpPolicyError("INVALID_RESULT", "paper OMS returned invalid result")
        return execution.result
