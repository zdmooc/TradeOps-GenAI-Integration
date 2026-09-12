from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "o5_crc_resilience_live.sh"


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
