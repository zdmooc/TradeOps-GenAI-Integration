from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable

from .models import (
    CaseStatus,
    DecisionCase,
    ExecutionMode,
    FusionDecision,
    ReviewDecision,
    ReviewRecord,
)


class WorkflowError(ValueError):
    pass


def open_case(proposal) -> DecisionCase:
    status = CaseStatus.PENDING_REVIEW if proposal.decision is FusionDecision.REVIEW_REQUIRED else CaseStatus.NO_TRADE
    return DecisionCase(proposal=proposal, status=status)


def review_case(
    case: DecisionCase,
    *,
    reviewer: str,
    decision: ReviewDecision,
    rationale: str,
    now: datetime | None = None,
) -> DecisionCase:
    now = now or datetime.now(timezone.utc)
    if not reviewer.strip():
        raise WorkflowError("reviewer is required")
    if len(rationale.strip()) < 3:
        raise WorkflowError("review rationale is required")
    if case.status is not CaseStatus.PENDING_REVIEW:
        raise WorkflowError(f"case is not reviewable from status {case.status.value}")
    if now > case.proposal.expires_at:
        return replace(case, status=CaseStatus.EXPIRED)
    if case.proposal.input.risk_status.upper() != "ACCEPT":
        raise WorkflowError("deterministic risk must remain ACCEPT at review")
    record = ReviewRecord(
        reviewer=reviewer,
        decision=decision,
        rationale=rationale.strip(),
        reviewed_at=now,
    )
    status = CaseStatus.APPROVED if decision is ReviewDecision.APPROVE else CaseStatus.REJECTED
    return replace(case, status=status, review=record)


def execute_approved_case(
    case: DecisionCase,
    *,
    now: datetime | None = None,
    paper_executor: Callable[[DecisionCase], dict[str, Any]] | None = None,
) -> DecisionCase:
    now = now or datetime.now(timezone.utc)
    if case.status is not CaseStatus.APPROVED:
        raise WorkflowError(f"case is not executable from status {case.status.value}")
    if case.review is None or case.review.decision is not ReviewDecision.APPROVE:
        raise WorkflowError("explicit human approval is required")
    if now > case.proposal.expires_at:
        return replace(case, status=CaseStatus.EXPIRED)
    if case.proposal.input.risk_status.upper() != "ACCEPT":
        raise WorkflowError("deterministic risk veto/uncertainty blocks execution")

    if case.proposal.execution_mode is ExecutionMode.SHADOW:
        result = {
            "mode": "SHADOW",
            "status": "RECORDED",
            "symbol": case.proposal.input.symbol,
            "direction": case.proposal.input.direction.upper(),
            "qty": case.proposal.input.qty,
        }
        return replace(case, status=CaseStatus.EXECUTED_SHADOW, execution_result=result)

    if paper_executor is None:
        raise WorkflowError("paper executor is required for PAPER mode")
    result = paper_executor(case)
    if not isinstance(result, dict) or not result.get("order_id"):
        raise WorkflowError("paper execution did not return an order_id")
    return replace(case, status=CaseStatus.EXECUTED_PAPER, execution_result=result)
