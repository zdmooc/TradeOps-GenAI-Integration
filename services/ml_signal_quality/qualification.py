from __future__ import annotations


def probability_qualification(
    metrics: dict[str, float],
    min_test_records: int = 40,
    max_ece: float = 0.15,
    min_brier_skill: float = 0.0,
) -> tuple[str, tuple[str, ...]]:
    reasons: list[str] = []
    n = int(metrics["n"])
    prevalence = metrics["positive_rate"]
    naive_brier = prevalence * (1.0 - prevalence)
    brier_skill = 0.0 if naive_brier <= 0.0 else 1.0 - metrics["brier"] / naive_brier
    if n < min_test_records:
        reasons.append("INSUFFICIENT_TEST_SAMPLE")
    if metrics["ece"] > max_ece:
        reasons.append("CALIBRATION_ERROR_TOO_HIGH")
    if brier_skill <= min_brier_skill:
        reasons.append("NO_POSITIVE_BRIER_SKILL")
    if metrics["roc_auc"] <= 0.5:
        reasons.append("NO_DISCRIMINATION_ABOVE_RANDOM")
    status = "CALIBRATED_OUT_OF_SAMPLE" if not reasons else "SCORE_ONLY"
    return status, tuple(reasons)
