from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import DecisionInput, DecisionProposal, ExecutionMode, FusionDecision


@dataclass(frozen=True, slots=True)
class FusionPolicy:
    version: str = "i7-v1"
    min_evidence_quality: float = 0.70
    max_freshness_ms: float = 5_000.0
    min_rr: float = 2.0
    min_historical_expectancy_r: float = 0.05
    min_historical_trades: int = 30
    min_calibrated_probability: float = 0.55
    review_ttl_minutes: int = 15
    allowed_regimes: frozenset[str] = frozenset({
        "TREND_UP", "TREND_DOWN", "RANGE", "BREAKOUT", "LOW_VOLATILITY",
        "HIGH_VOLATILITY", "RISK_ON", "RISK_OFF",
    })

    def __post_init__(self) -> None:
        if not 0 <= self.min_evidence_quality <= 1:
            raise ValueError("min_evidence_quality must be within [0, 1]")
        if self.max_freshness_ms <= 0 or self.min_rr <= 0:
            raise ValueError("freshness and R/R thresholds must be positive")
        if self.min_historical_trades < 0:
            raise ValueError("min_historical_trades cannot be negative")
        if not 0 <= self.min_calibrated_probability <= 1:
            raise ValueError("min_calibrated_probability must be within [0, 1]")
        if self.review_ttl_minutes <= 0:
            raise ValueError("review_ttl_minutes must be positive")


def _directional_price_gate(item: DecisionInput) -> tuple[bool, str]:
    if item.direction.upper() == "LONG":
        valid = item.stop < item.entry and all(target > item.entry for target in item.targets)
        return valid, "LONG requires stop < entry < every target"
    valid = item.stop > item.entry and all(target < item.entry for target in item.targets)
    return valid, "SHORT requires stop > entry > every target"


def _ml_gate(item: DecisionInput, policy: FusionPolicy) -> tuple[bool, str, bool]:
    status = item.ml_probability_status.upper()
    calibrated_real = status in {
        "CALIBRATED_REAL_MARKET", "CALIBRATED_OUT_OF_SAMPLE_REAL_MARKET"
    }
    if not calibrated_real:
        return True, "ML output is score-only/non-real-market calibrated and is non-decisive", False
    if item.ml_score is None:
        return False, "qualified calibrated probability status requires ml_score", True
    return (
        item.ml_score >= policy.min_calibrated_probability,
        f"calibrated probability must be >= {policy.min_calibrated_probability:.2f}",
        True,
    )


def _evidence_score(item: DecisionInput, ml_used: bool) -> float:
    freshness_quality = max(0.0, 1.0 - item.event_age_ms / item.max_freshness_ms)
    rr_quality = min(item.rr / 5.0, 1.0)
    expectancy_quality = max(0.0, min((item.historical_expectancy_r + 0.2) / 0.7, 1.0))
    weighted = [
        (item.evidence_quality, 0.40),
        (freshness_quality, 0.20),
        (rr_quality, 0.20),
        (expectancy_quality, 0.20),
    ]
    if ml_used and item.ml_score is not None:
        weighted = [
            (item.evidence_quality, 0.35),
            (freshness_quality, 0.15),
            (rr_quality, 0.20),
            (expectancy_quality, 0.15),
            (item.ml_score, 0.15),
        ]
    return round(sum(value * weight for value, weight in weighted), 4)


def fuse_decision(
    item: DecisionInput,
    execution_mode: ExecutionMode,
    policy: FusionPolicy | None = None,
    *,
    now: datetime | None = None,
    proposal_id: str | None = None,
    correlation_id: str | None = None,
) -> DecisionProposal:
    policy = policy or FusionPolicy()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    price_ok, price_reason = _directional_price_gate(item)
    ml_ok, ml_reason, ml_used = _ml_gate(item, policy)
    freshness_limit = min(item.max_freshness_ms, policy.max_freshness_ms)
    gates = (
        ("assessment", item.assessment_status.upper() == "SUPPORTED", "I6 assessment must be SUPPORTED"),
        ("risk", item.risk_status.upper() == "ACCEPT", "I3 deterministic risk gate must be ACCEPT"),
        ("freshness", item.event_age_ms <= freshness_limit, f"event age must be <= {freshness_limit:.0f}ms"),
        ("evidence_quality", item.evidence_quality >= policy.min_evidence_quality, f"evidence quality must be >= {policy.min_evidence_quality:.2f}"),
        ("regime", item.regime.upper() in policy.allowed_regimes, "regime must be explicitly allowed by fusion policy"),
        ("rr", item.rr >= policy.min_rr, f"R/R must be >= {policy.min_rr:.2f}"),
        ("historical_sample", item.historical_trade_count >= policy.min_historical_trades, f"historical trade count must be >= {policy.min_historical_trades}"),
        ("historical_expectancy", item.historical_expectancy_r >= policy.min_historical_expectancy_r, f"historical expectancy R must be >= {policy.min_historical_expectancy_r:.3f}"),
        ("price_geometry", price_ok, price_reason),
        ("ml_qualification", ml_ok, ml_reason),
    )
    failed = [f"{name}: {reason}" for name, passed, reason in gates if not passed]
    decision = FusionDecision.NO_TRADE if failed else FusionDecision.REVIEW_REQUIRED
    rationale = tuple(failed) if failed else (
        "all deterministic fusion gates passed",
        "human approval is mandatory before SHADOW or PAPER execution",
        ml_reason,
    )
    return DecisionProposal(
        proposal_id=proposal_id or str(uuid.uuid4()),
        correlation_id=correlation_id or str(uuid.uuid4()),
        created_at=now,
        expires_at=now + timedelta(minutes=policy.review_ttl_minutes),
        execution_mode=execution_mode,
        decision=decision,
        input=item,
        policy_version=policy.version,
        gate_results=gates,
        rationale=rationale,
        evidence_score=_evidence_score(item, ml_used),
        ml_contribution_used=ml_used,
    )
