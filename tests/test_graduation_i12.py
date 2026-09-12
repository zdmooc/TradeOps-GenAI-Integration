from __future__ import annotations

import copy
import json
from pathlib import Path

from services.graduation.gate import REQUIRED_CRITERIA, evaluate_manifest, load_manifest

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "data" / "graduation" / "i12_graduation_manifest.json"


def _record(index: int, source: str = "LIVE_MARKET") -> dict[str, object]:
    return {
        "signal_id": f"signal-{index:03d}",
        "mode": "SHADOW" if index % 2 else "PAPER",
        "source": source,
        "state": "CLOSED",
        "observed_at": "2026-09-12T08:00:00Z",
        "closed_at": "2026-09-12T08:05:00Z",
        "realized_r": 1.0 if index % 3 else -1.0,
        "evidence_ref": f"evidence://signal-{index:03d}",
    }


def _write_records(path: Path, count: int, source: str = "LIVE_MARKET") -> None:
    path.write_text(
        "".join(json.dumps(_record(index, source=source)) + "\n" for index in range(count)),
        encoding="utf-8",
    )


def _complete_manifest(tmp_path: Path, paper_count: int = 100) -> dict[str, object]:
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["probabilistic_production_claim"] = False
    for criterion in manifest["criteria"]:
        criterion["status"] = "SATISFIED"
        criterion["evidence_refs"] = ["ci:test"]
        if criterion["id"] in {
            "LIVE_MULTI_SOURCE_REPLAY",
            "OBSERVABILITY_SECURITY_LIVE",
            "OPENSHIFT_AZURE_DEPLOYMENT",
            "RESILIENCE_FINOPS_GREENOPS_VERIFIED",
        }:
            criterion["evidence_class"] = "LIVE"
            criterion["verified_at"] = "2026-09-12T08:00:00Z"
    ml_criterion = next(
        criterion
        for criterion in manifest["criteria"]
        if criterion["id"] == "ML_CALIBRATION_IF_PROBABILISTIC"
    )
    ml_criterion["status"] = "NOT_APPLICABLE"
    paper_path = tmp_path / "paper.jsonl"
    _write_records(paper_path, paper_count)
    manifest["paper_shadow"]["records_path"] = paper_path.name
    return manifest


def test_current_manifest_is_deliberately_not_graduated():
    report = evaluate_manifest(load_manifest(MANIFEST), repo_root=ROOT)
    assert report.status == "NOT_GRADUATED"
    assert report.errors == ()
    assert report.paper_shadow_valid_outcomes == 100
    assert "LIVE_MULTI_SOURCE_REPLAY" in report.satisfied
    assert "PAPER_SHADOW_100_OUTCOMES" in report.satisfied
    assert "OBSERVABILITY_SECURITY_LIVE" in report.satisfied
    assert report.blockers == (
        "OPENSHIFT_AZURE_DEPLOYMENT",
        "RESILIENCE_FINOPS_GREENOPS_VERIFIED",
    )


def test_manifest_contains_exact_graduation_criteria():
    manifest = load_manifest(MANIFEST)
    ids = tuple(criterion["id"] for criterion in manifest["criteria"])
    assert ids == REQUIRED_CRITERIA


def test_missing_criterion_fails_closed():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["criteria"] = manifest["criteria"][:-1]
    report = evaluate_manifest(manifest, repo_root=ROOT)
    assert report.status == "NOT_GRADUATED"
    assert any(error.startswith("missing criterion") for error in report.errors)


def test_duplicate_criterion_fails_closed():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["criteria"].append(copy.deepcopy(manifest["criteria"][0]))
    report = evaluate_manifest(manifest, repo_root=ROOT)
    assert any(error.startswith("duplicate criterion") for error in report.errors)


def test_live_criterion_cannot_be_satisfied_with_ci_only_evidence():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    criterion = manifest["criteria"][0]
    criterion["status"] = "SATISFIED"
    criterion["evidence_class"] = "CI"
    criterion["verified_at"] = "2026-09-12T08:00:00Z"
    report = evaluate_manifest(manifest, repo_root=ROOT)
    assert any("requires LIVE/OPERATIONAL evidence" in error for error in report.errors)


def test_live_criterion_requires_timezone_aware_verification_time():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    criterion = manifest["criteria"][0]
    criterion["status"] = "SATISFIED"
    criterion["evidence_class"] = "LIVE"
    criterion["verified_at"] = "2026-09-12T08:00:00"
    report = evaluate_manifest(manifest, repo_root=ROOT)
    assert any("timezone-aware verified_at" in error for error in report.errors)


def test_ml_not_applicable_is_allowed_without_probability_claim():
    report = evaluate_manifest(load_manifest(MANIFEST), repo_root=ROOT)
    assert "ML_CALIBRATION_IF_PROBABILISTIC" in report.not_applicable
    assert "ML_CALIBRATION_IF_PROBABILISTIC" not in report.blockers


def test_ml_becomes_blocker_when_production_probability_is_claimed():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    manifest["probabilistic_production_claim"] = True
    report = evaluate_manifest(manifest, repo_root=ROOT)
    assert "ML_CALIBRATION_IF_PROBABILISTIC" in report.blockers


def test_ninety_nine_paper_shadow_outcomes_do_not_graduate(tmp_path):
    manifest = _complete_manifest(tmp_path, paper_count=99)
    report = evaluate_manifest(manifest, repo_root=tmp_path)
    assert report.status == "NOT_GRADUATED"
    assert report.paper_shadow_valid_outcomes == 99
    assert report.blockers == ("PAPER_SHADOW_100_OUTCOMES",)


def test_one_hundred_valid_outcomes_can_satisfy_quantity_gate(tmp_path):
    manifest = _complete_manifest(tmp_path, paper_count=100)
    report = evaluate_manifest(manifest, repo_root=tmp_path)
    assert report.status == "GRADUATED"
    assert report.paper_shadow_valid_outcomes == 100
    assert report.blockers == ()
    assert report.errors == ()


def test_synthetic_records_never_count_as_graduation_evidence(tmp_path):
    manifest = _complete_manifest(tmp_path, paper_count=100)
    paper_path = tmp_path / manifest["paper_shadow"]["records_path"]
    _write_records(paper_path, 100, source="SYNTHETIC")
    report = evaluate_manifest(manifest, repo_root=tmp_path)
    assert report.paper_shadow_valid_outcomes == 0
    assert report.status == "NOT_GRADUATED"


def test_duplicate_signal_ids_count_once(tmp_path):
    manifest = _complete_manifest(tmp_path, paper_count=100)
    paper_path = tmp_path / manifest["paper_shadow"]["records_path"]
    with paper_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_record(0)) + "\n")
    report = evaluate_manifest(manifest, repo_root=tmp_path)
    assert report.paper_shadow_valid_outcomes == 100


def test_missing_repo_evidence_fails_closed():
    manifest = copy.deepcopy(load_manifest(MANIFEST))
    criterion = next(
        criterion for criterion in manifest["criteria"] if criterion["id"] == "DATA_QUALITY_ENGINE"
    )
    criterion["evidence_refs"] = ["repo:does/not/exist.md"]
    report = evaluate_manifest(manifest, repo_root=ROOT)
    assert any("missing repository evidence" in error for error in report.errors)


def test_report_serializes_to_stable_shape():
    report = evaluate_manifest(load_manifest(MANIFEST), repo_root=ROOT)
    payload = report.to_dict()
    assert payload["status"] == "NOT_GRADUATED"
    assert payload["required_paper_shadow_outcomes"] == 100
    assert isinstance(payload["satisfied"], list)
    assert isinstance(payload["blockers"], list)
