from datetime import datetime, timezone

import pytest

from services.decision_fusion.models import DecisionInput, ExecutionMode, FusionDecision
from services.decision_fusion.policy import FusionPolicy, fuse_decision

NOW = datetime(2026, 9, 11, 21, 30, tzinfo=timezone.utc)


def _safe_input(**overrides):
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
        "event_age_ms": 800.0,
        "max_freshness_ms": 5000.0,
        "evidence_quality": 0.88,
        "rr": 2.4,
        "historical_expectancy_r": 0.18,
        "historical_trade_count": 64,
        "ml_score": 0.74,
        "ml_probability_status": "CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC",
        "evidence": ("pattern:breakout_retest", "risk:i3-accept"),
    }
    payload.update(overrides)
    return DecisionInput(**payload)


def test_safe_setup_requires_human_review():
    proposal = fuse_decision(
        _safe_input(), ExecutionMode.SHADOW, now=NOW, proposal_id="p-1", correlation_id="c-1"
    )
    assert proposal.decision is FusionDecision.REVIEW_REQUIRED
    assert proposal.execution_allowed is False
    assert proposal.human_approval_required is True


@pytest.mark.parametrize(
    ("field", "value", "failed_gate"),
    [
        ("assessment_status", "CONFLICT", "assessment"),
        ("risk_status", "VETO", "risk"),
        ("event_age_ms", 6000.0, "freshness"),
        ("evidence_quality", 0.4, "evidence_quality"),
        ("regime", "POST_EVENT", "regime"),
        ("rr", 1.2, "rr"),
        ("historical_trade_count", 10, "historical_sample"),
        ("historical_expectancy_r", -0.1, "historical_expectancy"),
    ],
)
def test_hard_gate_failures_produce_no_trade(field, value, failed_gate):
    proposal = fuse_decision(_safe_input(**{field: value}), ExecutionMode.PAPER, now=NOW)
    assert proposal.decision is FusionDecision.NO_TRADE
    failed = {name for name, passed, _ in proposal.gate_results if not passed}
    assert failed_gate in failed


def test_invalid_long_price_geometry_is_rejected():
    proposal = fuse_decision(_safe_input(stop=23520.0), ExecutionMode.SHADOW, now=NOW)
    assert proposal.decision is FusionDecision.NO_TRADE
    assert any(name == "price_geometry" and not passed for name, passed, _ in proposal.gate_results)


def test_invalid_short_price_geometry_is_rejected():
    item = _safe_input(direction="SHORT", stop=23400.0, targets=(23300.0,), regime="TREND_DOWN")
    assert fuse_decision(item, ExecutionMode.SHADOW, now=NOW).decision is FusionDecision.NO_TRADE


def test_valid_short_price_geometry_can_reach_review():
    item = _safe_input(direction="SHORT", stop=23550.0, targets=(23380.0,), regime="TREND_DOWN")
    assert fuse_decision(item, ExecutionMode.SHADOW, now=NOW).decision is FusionDecision.REVIEW_REQUIRED


def test_synthetic_ml_calibration_is_non_decisive():
    proposal = fuse_decision(
        _safe_input(ml_score=0.01, ml_probability_status="CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC"),
        ExecutionMode.SHADOW,
        now=NOW,
    )
    assert proposal.decision is FusionDecision.REVIEW_REQUIRED
    assert proposal.ml_contribution_used is False
    assert "non-real-market calibrated" in proposal.rationale[-1]


def test_low_real_market_calibrated_probability_blocks_review():
    proposal = fuse_decision(
        _safe_input(ml_score=0.51, ml_probability_status="CALIBRATED_REAL_MARKET"),
        ExecutionMode.SHADOW,
        now=NOW,
    )
    assert proposal.decision is FusionDecision.NO_TRADE
    assert proposal.ml_contribution_used is True
    assert any(name == "ml_qualification" and not passed for name, passed, _ in proposal.gate_results)


def test_qualified_real_market_ml_contributes_to_score():
    proposal = fuse_decision(
        _safe_input(ml_score=0.72, ml_probability_status="CALIBRATED_REAL_MARKET"),
        ExecutionMode.SHADOW,
        now=NOW,
    )
    assert proposal.decision is FusionDecision.REVIEW_REQUIRED
    assert proposal.ml_contribution_used is True


def test_evidence_score_is_deterministic_and_not_the_decision_gate():
    item = _safe_input()
    first = fuse_decision(item, ExecutionMode.SHADOW, now=NOW)
    second = fuse_decision(item, ExecutionMode.SHADOW, now=NOW)
    assert first.evidence_score == second.evidence_score
    assert 0.0 <= first.evidence_score <= 1.0


def test_policy_validates_thresholds():
    with pytest.raises(ValueError):
        FusionPolicy(min_rr=0)
