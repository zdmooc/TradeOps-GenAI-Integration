from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from services.decision_fusion.models import (
    CaseStatus,
    DecisionInput,
    ExecutionMode,
    ReviewDecision,
)
from services.decision_fusion.policy import fuse_decision
from services.decision_fusion.store import InMemoryDecisionStore
from services.decision_fusion.workflow import (
    WorkflowError,
    execute_approved_case,
    open_case,
    review_case,
)

NOW = datetime(2026, 9, 11, 21, 30, tzinfo=timezone.utc)


def _proposal(mode=ExecutionMode.SHADOW, **overrides):
    payload = {
        "symbol": "IX.D.DAX.IFM.IP",
        "direction": "LONG",
        "qty": 2.0,
        "entry": 23500.0,
        "stop": 23450.0,
        "targets": (23620.0,),
        "timeframe": "M15",
        "regime": "TREND_UP",
        "pattern": "BREAKOUT_RETEST",
        "assessment_status": "SUPPORTED",
        "risk_status": "ACCEPT",
        "event_age_ms": 500.0,
        "max_freshness_ms": 5000.0,
        "evidence_quality": 0.9,
        "rr": 2.4,
        "historical_expectancy_r": 0.2,
        "historical_trade_count": 80,
        "ml_score": 0.7,
        "ml_probability_status": "SCORE_ONLY",
        "evidence": ("risk:accept", "pattern:confirmed"),
    }
    payload.update(overrides)
    return fuse_decision(
        DecisionInput(**payload),
        mode,
        now=NOW,
        proposal_id="11111111-1111-1111-1111-111111111111",
        correlation_id="22222222-2222-2222-2222-222222222222",
    )


def test_review_required_case_opens_pending():
    assert open_case(_proposal()).status is CaseStatus.PENDING_REVIEW


def test_no_trade_case_is_not_reviewable():
    case = open_case(_proposal(risk_status="VETO"))
    assert case.status is CaseStatus.NO_TRADE
    with pytest.raises(WorkflowError):
        review_case(case, reviewer="human-reviewer", decision=ReviewDecision.APPROVE, rationale="approve", now=NOW)


def test_human_can_approve():
    reviewed = review_case(
        open_case(_proposal()),
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="evidence checked",
        now=NOW + timedelta(minutes=1),
    )
    assert reviewed.status is CaseStatus.APPROVED
    assert reviewed.review is not None
    assert reviewed.review.reviewer == "human-reviewer"


def test_human_can_reject():
    reviewed = review_case(
        open_case(_proposal()),
        reviewer="human-reviewer",
        decision=ReviewDecision.REJECT,
        rationale="market context changed",
        now=NOW + timedelta(minutes=1),
    )
    assert reviewed.status is CaseStatus.REJECTED


def test_expired_case_cannot_be_approved():
    reviewed = review_case(
        open_case(_proposal()),
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="too late",
        now=NOW + timedelta(minutes=20),
    )
    assert reviewed.status is CaseStatus.EXPIRED


def test_execute_before_review_is_blocked():
    with pytest.raises(WorkflowError):
        execute_approved_case(open_case(_proposal()), now=NOW + timedelta(minutes=1))


def test_shadow_execution_requires_approval_and_does_not_call_executor():
    reviewed = review_case(
        open_case(_proposal(ExecutionMode.SHADOW)),
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="approved for shadow",
        now=NOW + timedelta(minutes=1),
    )
    called = False

    def paper_executor(_):
        nonlocal called
        called = True
        return {"order_id": "should-not-run"}

    executed = execute_approved_case(reviewed, now=NOW + timedelta(minutes=2), paper_executor=paper_executor)
    assert executed.status is CaseStatus.EXECUTED_SHADOW
    assert executed.execution_result["status"] == "RECORDED"
    assert called is False


def test_paper_execution_calls_governed_executor_after_approval():
    reviewed = review_case(
        open_case(_proposal(ExecutionMode.PAPER)),
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="approved for paper",
        now=NOW + timedelta(minutes=1),
    )

    def paper_executor(current):
        return {
            "order_id": "order-1",
            "workflow_id": current.proposal.proposal_id,
            "status": "FILLED",
        }

    executed = execute_approved_case(reviewed, now=NOW + timedelta(minutes=2), paper_executor=paper_executor)
    assert executed.status is CaseStatus.EXECUTED_PAPER
    assert executed.execution_result["workflow_id"] == reviewed.proposal.proposal_id


def test_paper_execution_without_order_id_fails_closed():
    reviewed = review_case(
        open_case(_proposal(ExecutionMode.PAPER)),
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="approved",
        now=NOW + timedelta(minutes=1),
    )
    with pytest.raises(WorkflowError):
        execute_approved_case(
            reviewed,
            now=NOW + timedelta(minutes=2),
            paper_executor=lambda _: {"status": "FILLED"},
        )


def test_execution_after_ttl_expires():
    reviewed = review_case(
        open_case(_proposal(ExecutionMode.PAPER)),
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="approved",
        now=NOW + timedelta(minutes=1),
    )
    expired = execute_approved_case(
        reviewed,
        now=NOW + timedelta(minutes=20),
        paper_executor=lambda _: {"order_id": "not-used"},
    )
    assert expired.status is CaseStatus.EXPIRED


def test_risk_must_still_be_accept_at_execution():
    reviewed = review_case(
        open_case(_proposal(ExecutionMode.PAPER)),
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="approved",
        now=NOW + timedelta(minutes=1),
    )
    unsafe_input = replace(reviewed.proposal.input, risk_status="VETO")
    unsafe_case = replace(reviewed, proposal=replace(reviewed.proposal, input=unsafe_input))
    with pytest.raises(WorkflowError):
        execute_approved_case(
            unsafe_case,
            now=NOW + timedelta(minutes=2),
            paper_executor=lambda _: {"order_id": "never"},
        )


def test_duplicate_execution_is_blocked():
    reviewed = review_case(
        open_case(_proposal(ExecutionMode.SHADOW)),
        reviewer="human-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="approved",
        now=NOW + timedelta(minutes=1),
    )
    executed = execute_approved_case(reviewed, now=NOW + timedelta(minutes=2))
    with pytest.raises(WorkflowError):
        execute_approved_case(executed, now=NOW + timedelta(minutes=3))


def test_in_memory_store_round_trip_and_update():
    store = InMemoryDecisionStore()
    case = open_case(_proposal())
    store.create(case)
    assert store.get(case.proposal.proposal_id) == case
    reviewed = review_case(
        case,
        reviewer="human-reviewer",
        decision=ReviewDecision.REJECT,
        rationale="reject",
        now=NOW + timedelta(minutes=1),
    )
    store.save(reviewed)
    assert store.get(case.proposal.proposal_id).status is CaseStatus.REJECTED


def test_in_memory_store_rejects_duplicate_create():
    store = InMemoryDecisionStore()
    case = open_case(_proposal())
    store.create(case)
    with pytest.raises(ValueError):
        store.create(case)
