from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class FusionDecision(str, Enum):
    NO_TRADE = "NO_TRADE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ExecutionMode(str, Enum):
    SHADOW = "SHADOW"
    PAPER = "PAPER"


class ReviewDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class CaseStatus(str, Enum):
    NO_TRADE = "NO_TRADE"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED_SHADOW = "EXECUTED_SHADOW"
    EXECUTED_PAPER = "EXECUTED_PAPER"


@dataclass(frozen=True, slots=True)
class DecisionInput:
    symbol: str
    direction: str
    qty: float
    entry: float
    stop: float
    targets: tuple[float, ...]
    timeframe: str
    regime: str
    pattern: str
    assessment_status: str
    risk_status: str
    event_age_ms: float
    max_freshness_ms: float
    evidence_quality: float
    rr: float
    historical_expectancy_r: float
    historical_trade_count: int
    ml_score: float | None = None
    ml_probability_status: str = "SCORE_ONLY"
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.direction.upper() not in {"LONG", "SHORT"}:
            raise ValueError("direction must be LONG or SHORT")
        if self.qty <= 0:
            raise ValueError("qty must be positive")
        if self.entry <= 0 or self.stop <= 0:
            raise ValueError("entry and stop must be positive")
        if not self.targets or any(value <= 0 for value in self.targets):
            raise ValueError("at least one positive target is required")
        if self.event_age_ms < 0 or self.max_freshness_ms <= 0:
            raise ValueError("freshness values are invalid")
        if not 0.0 <= self.evidence_quality <= 1.0:
            raise ValueError("evidence_quality must be within [0, 1]")
        if self.rr <= 0:
            raise ValueError("rr must be positive")
        if self.historical_trade_count < 0:
            raise ValueError("historical_trade_count cannot be negative")
        if self.ml_score is not None and not 0.0 <= self.ml_score <= 1.0:
            raise ValueError("ml_score must be within [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction.upper(),
            "qty": self.qty,
            "entry": self.entry,
            "stop": self.stop,
            "targets": list(self.targets),
            "timeframe": self.timeframe,
            "regime": self.regime,
            "pattern": self.pattern,
            "assessment_status": self.assessment_status,
            "risk_status": self.risk_status,
            "event_age_ms": self.event_age_ms,
            "max_freshness_ms": self.max_freshness_ms,
            "evidence_quality": self.evidence_quality,
            "rr": self.rr,
            "historical_expectancy_r": self.historical_expectancy_r,
            "historical_trade_count": self.historical_trade_count,
            "ml_score": self.ml_score,
            "ml_probability_status": self.ml_probability_status,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionInput":
        data = dict(payload)
        data["targets"] = tuple(data.get("targets", ()))
        data["evidence"] = tuple(data.get("evidence", ()))
        return cls(**data)


@dataclass(frozen=True, slots=True)
class DecisionProposal:
    proposal_id: str
    correlation_id: str
    created_at: datetime
    expires_at: datetime
    execution_mode: ExecutionMode
    decision: FusionDecision
    input: DecisionInput
    policy_version: str
    gate_results: tuple[tuple[str, bool, str], ...]
    rationale: tuple[str, ...]
    evidence_score: float
    ml_contribution_used: bool
    human_approval_required: bool = field(default=True, init=False)
    execution_allowed: bool = field(default=False, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "execution_mode": self.execution_mode.value,
            "decision": self.decision.value,
            "input": self.input.to_dict(),
            "policy_version": self.policy_version,
            "gate_results": [
                {"gate": name, "passed": passed, "reason": reason}
                for name, passed, reason in self.gate_results
            ],
            "rationale": list(self.rationale),
            "evidence_score": self.evidence_score,
            "ml_contribution_used": self.ml_contribution_used,
            "human_approval_required": self.human_approval_required,
            "execution_allowed": self.execution_allowed,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionProposal":
        return cls(
            proposal_id=str(payload["proposal_id"]),
            correlation_id=str(payload["correlation_id"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            execution_mode=ExecutionMode(str(payload["execution_mode"])),
            decision=FusionDecision(str(payload["decision"])),
            input=DecisionInput.from_dict(dict(payload["input"])),
            policy_version=str(payload["policy_version"]),
            gate_results=tuple(
                (str(item["gate"]), bool(item["passed"]), str(item["reason"]))
                for item in payload.get("gate_results", [])
            ),
            rationale=tuple(str(item) for item in payload.get("rationale", [])),
            evidence_score=float(payload["evidence_score"]),
            ml_contribution_used=bool(payload.get("ml_contribution_used", False)),
        )


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    reviewer: str
    decision: ReviewDecision
    rationale: str
    reviewed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "decision": self.decision.value,
            "rationale": self.rationale,
            "reviewed_at": self.reviewed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewRecord":
        return cls(
            reviewer=str(payload["reviewer"]),
            decision=ReviewDecision(str(payload["decision"])),
            rationale=str(payload["rationale"]),
            reviewed_at=datetime.fromisoformat(str(payload["reviewed_at"])),
        )


@dataclass(frozen=True, slots=True)
class DecisionCase:
    proposal: DecisionProposal
    status: CaseStatus
    review: ReviewRecord | None = None
    execution_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal.to_dict(),
            "status": self.status.value,
            "review": self.review.to_dict() if self.review else None,
            "execution_result": self.execution_result,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DecisionCase":
        review = payload.get("review")
        return cls(
            proposal=DecisionProposal.from_dict(dict(payload["proposal"])),
            status=CaseStatus(str(payload["status"])),
            review=ReviewRecord.from_dict(dict(review)) if review else None,
            execution_result=payload.get("execution_result"),
        )
