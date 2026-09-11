from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNKNOWN = "UNKNOWN"
    DATA_STALE = "DATA_STALE"
    CONFLICT = "CONFLICT"
    VETO = "VETO"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class AgentFinding:
    agent: str
    status: AgentStatus
    direction: Direction = Direction.UNKNOWN
    evidence_quality: float = 0.0
    reasons: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.evidence_quality <= 1.0:
            raise ValueError("evidence_quality must be within [0, 1]")
        if not self.agent.strip():
            raise ValueError("agent is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "status": self.status.value,
            "direction": self.direction.value,
            "evidence_quality": self.evidence_quality,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class AgentContext:
    symbol: str
    event_age_ms: float | None = None
    max_freshness_ms: float = 5_000.0
    market_direction: Direction = Direction.UNKNOWN
    technical_structure: str = "UNKNOWN"
    pattern_directions: tuple[Direction, ...] = ()
    macro_state: str = "UNKNOWN"
    event_risk: bool = False
    risk_status: str = "UNKNOWN"
    risk_reasons: tuple[str, ...] = ()
    rag_status: AgentStatus = AgentStatus.UNKNOWN
    rag_evidence: tuple[str, ...] = ()
    ml_score: float | None = None
    ml_probability_status: str = "SCORE_ONLY"

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.event_age_ms is not None and self.event_age_ms < 0:
            raise ValueError("event_age_ms cannot be negative")
        if self.max_freshness_ms <= 0:
            raise ValueError("max_freshness_ms must be positive")
        if self.ml_score is not None and not 0.0 <= self.ml_score <= 1.0:
            raise ValueError("ml_score must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class AgenticAssessment:
    symbol: str
    status: AgentStatus
    direction: Direction
    findings: tuple[AgentFinding, ...]
    unresolved: tuple[str, ...] = ()
    execution_allowed: bool = field(default=False, init=False)
    decision_scope: str = field(default="ANALYSIS_ONLY", init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "status": self.status.value,
            "direction": self.direction.value,
            "findings": [finding.to_dict() for finding in self.findings],
            "unresolved": list(self.unresolved),
            "execution_allowed": self.execution_allowed,
            "decision_scope": self.decision_scope,
        }
