import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "o5_crc_resilience_live.sh"
MANIFEST = ROOT / "data" / "graduation" / "i12_graduation_manifest.json"
BASELINE_SUMMARY = (
    ROOT / "evidence" / "graduation" / "live" / "resilience" / "20260912T202019Z" / "00-summary.txt"
)
RTO_SUMMARY = (
    ROOT / "evidence" / "graduation" / "live" / "resilience" / "20260912T202740Z" / "00-summary.txt"
)


def _summary(path: Path) -> dict[str, str]:
    return {
        key: value
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }


def test_o5_resilience_drill_is_fail_closed_and_local_only():
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'ALLOW_CONTROLLED_POD_DELETE:-0' in text
    assert 'failure_action=DELETE_SINGLE_POD' in text
    assert 'scope=LOCAL_CRC_CONTROLLED_FAILURE' in text
    assert 'full_resilience_finops_greenops_gate_claim=false' in text
    assert 'provider_cost_claim=NOT_MEASURED_ON_LOCAL_CRC' in text
    assert 'carbon_claim=NOT_MEASURED' in text
    assert 'rpo_applicable=false' in text


def test_o5_resilience_drill_measures_recovery_without_inventing_rto():
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'observed_recovery_seconds=' in text
    assert 'LAB_RTO_TARGET_SECONDS' in text
    assert 'lab_rto_target_seconds=${LAB_RTO_TARGET_SECONDS:-NOT_SET}' in text
    assert 'lab_rto_target_result=${TARGET_RESULT}' in text
    assert 'CRC_RESILIENCE_DRILL_PASS' in text


def test_o5_resilience_drill_captures_operational_evidence():
    text = SCRIPT.read_text(encoding="utf-8")

    required = (
        "deployment-before",
        "pods-before",
        "health-before",
        "node-metrics-before",
        "pod-metrics-before",
        "failure-injection",
        "recovery-probes",
        "deployment-after",
        "pods-after",
        "events-after",
        "health-after",
        "node-metrics-after",
        "pod-metrics-after",
        "secret-scan",
    )
    for token in required:
        assert token in text

    assert "oc -n \"$NAMESPACE\" delete pod \"$OLD_POD\" --wait=false" in text
    assert 'evidence_class=LIVE_OPERATIONAL' in text
    assert '| OLD_UID="$OLD_UID" python -c' in text


def test_committed_o5_evidence_records_baseline_and_predeclared_rto():
    baseline = _summary(BASELINE_SUMMARY)
    rto = _summary(RTO_SUMMARY)

    assert baseline["evidence_class"] == "LIVE_OPERATIONAL"
    assert baseline["scope"] == "LOCAL_CRC_CONTROLLED_FAILURE"
    assert baseline["observed_recovery_seconds"] == "15.301"
    assert baseline["lab_rto_target_seconds"] == "NOT_SET"
    assert baseline["lab_rto_target_result"] == "NOT_EVALUATED"
    assert baseline["verification"] == "CRC_RESILIENCE_DRILL_PASS"

    assert rto["evidence_class"] == "LIVE_OPERATIONAL"
    assert rto["scope"] == "LOCAL_CRC_CONTROLLED_FAILURE"
    assert rto["old_uid"] == baseline["new_uid"]
    assert rto["new_uid"] != rto["old_uid"]
    assert rto["observed_recovery_seconds"] == "14.302"
    assert rto["lab_rto_target_seconds"] == "30"
    assert rto["lab_rto_target_result"] == "PASS"
    assert rto["rpo_applicable"] == "false"
    assert rto["provider_cost_claim"] == "NOT_MEASURED_ON_LOCAL_CRC"
    assert rto["carbon_claim"] == "NOT_MEASURED"
    assert rto["full_resilience_finops_greenops_gate_claim"] == "false"
    assert rto["verification"] == "CRC_RESILIENCE_DRILL_PASS"


def test_o5_manifest_records_operational_resilience_without_overclaiming_combined_gate():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    criterion = next(
        item
        for item in manifest["criteria"]
        if item["id"] == "RESILIENCE_FINOPS_GREENOPS_VERIFIED"
    )

    assert criterion["status"] == "PARTIAL"
    assert criterion["evidence_class"] == "OPERATIONAL"
    assert criterion["verified_at"] == "2026-09-12T20:28:09Z"
    assert (
        "repo:evidence/graduation/live/resilience/20260912T202019Z/00-summary.txt"
        in criterion["evidence_refs"]
    )
    assert (
        "repo:evidence/graduation/live/resilience/20260912T202740Z/00-summary.txt"
        in criterion["evidence_refs"]
    )
    assert "Azure provider cost and carbon evidence remain unmeasured" in criterion["notes"]
