from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUSPEND = ROOT / "scripts" / "crc" / "suspend-tradeops.sh"
RESUME = ROOT / "scripts" / "crc" / "resume-tradeops.sh"
RUNBOOK = ROOT / "docs" / "runbooks" / "CRC_TRADEOPS_PARK_RESUME.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_crc_park_resume_scripts_are_bash_syntax_valid():
    for path in (SUSPEND, RESUME):
        assert path.is_file()
        result = subprocess.run(
            ["bash", "-n", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


def test_suspend_is_fail_closed_for_gitops_hpa_and_cronjobs():
    script = read(SUSPEND)
    assert "applications.argoproj.io" in script
    assert "automated Argo CD application(s)" in script
    assert "HPA targets deployments selected for PARK" in script
    assert "active CronJob(s) could create new pods while parked" in script


def test_suspend_never_scales_statefulsets_and_preserves_prometheus_by_default():
    script = read(SUSPEND)
    assert 'protected = set() if mode == "deep" else {"prometheus"}' in script
    assert "oc -n \"$NAMESPACE\" scale \"deployment/$name\"" in script
    assert "scale \"statefulset/" not in script
    assert "TRADEOPS_STATEFULSETS_PRESERVED=PASS" in script
    assert "TRADEOPS_PROMETHEUS_PRESERVED=PASS" in script


def test_suspend_captures_cluster_capacity_before_and_after():
    script = read(SUSPEND)
    assert "08-cluster-pending-before.txt" in script
    assert "09-node-describe-before.txt" in script
    assert "23-node-describe-after.txt" in script
    assert "24-cluster-pending-after.txt" in script
    assert "10-cluster-pods-before.json" in script
    assert "25-cluster-pods-after.json" in script
    assert "11-nodes-before.json" in script
    assert "26-nodes-after.json" in script


def test_deep_park_requires_explicit_tsdb_loss_confirmation():
    script = read(SUSPEND)
    assert "TRADEOPS_DEEP_PARK_CONFIRM_TSDB_LOSS" in script
    assert "deep mode deletes Prometheus emptyDir/TSDB" in script


def test_suspend_and_resume_have_transactional_rollback_and_idempotency():
    suspend = read(SUSPEND)
    resume = read(RESUME)
    assert "TRADEOPS_PARK_ROLLBACK" in suspend
    assert "TRADEOPS_RESUME_ROLLBACK" in resume
    assert "TRADEOPS_PARK_ALREADY_ACTIVE=PASS" in suspend
    assert "TRADEOPS_RESUME_ALREADY_COMPLETE=PASS" in resume
    assert "deployments.tsv" in suspend
    assert "deployments.tsv" in resume


def test_resume_restores_exact_replica_snapshot_without_stateful_scaling():
    script = read(RESUME)
    assert 'scale "deployment/$name" --replicas="$replicas"' in script
    assert "TRADEOPS_REPLICA_RESTORE=EXACT" in script
    assert "scale \"statefulset/" not in script
    assert "statefulset/$name drifted" in script


def test_runbook_documents_ephemeral_crc_storage_and_claim_boundary():
    runbook = read(RUNBOOK)
    assert "ephemeralPlatformStorage: true" in runbook
    assert "PostgreSQL uses `emptyDir`" in runbook
    assert "Redpanda uses `emptyDir`" in runbook
    assert "Prometheus Deployment also uses an `emptyDir` TSDB" in runbook
    assert "TRADEOPS_CRC_PARK_RESUME_IMPLEMENTED_AND_CI_VALIDATED" in runbook
    assert "TRADEOPS_CRC_PARK_RESUME_RUNTIME_PROVEN" in runbook
