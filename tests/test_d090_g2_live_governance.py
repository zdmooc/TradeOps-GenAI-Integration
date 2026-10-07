from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "crc" / "d090-g2-live-governance-from-park.sh"
PROBE = ROOT / "scripts" / "d090_g2_governance_probe.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_g2_wrapper_and_probe_are_syntax_valid():
    bash = subprocess.run(
        ["bash", "-n", str(WRAPPER)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert bash.returncode == 0, bash.stderr

    py = subprocess.run(
        ["python", "-m", "py_compile", str(PROBE)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert py.returncode == 0, py.stderr


def test_g2_requires_park_and_reparks_without_stateful_mutation():
    script = read(WRAPPER)
    assert 'grep -qx "PARKED"' in script
    assert 'REQUIRED_DEPLOYMENTS=(ai-access-policy genai-api litellm)' in script
    assert 'scale "deployment/$name" --replicas=0' in script
    assert "statefulset/" not in script
    assert "D090_G2_WINDOW_REPARK=PASS" in script


def test_g2_restores_consumer_policy_on_exit():
    script = read(WRAPPER)
    assert "ORIGINAL_POLICY_B64" in script
    assert "restore_policy()" in script
    assert "D090_G2_POLICY_RESTORE=PASS" in script
    assert "patch secret tradeops-runtime-secrets" in script


def test_g2_proves_model_quota_budget_and_metrics():
    script = read(WRAPPER)
    probe = read(PROBE)

    for marker in (
        "D090_G2_SUCCESS=PASS",
        "D090_G2_MODEL_DENIED=PASS",
        "D090_G2_QUOTA_EXCEEDED=PASS",
        "D090_G2_BUDGET_EXCEEDED=PASS",
    ):
        assert marker in probe

    for marker in (
        "D090_G2_BASELINE_METRICS=PASS",
        "D090_G2_QUOTA_METRICS=PASS",
        "D090_G2_COST_METRIC=PASS",
        "D090_G2_GOVERNANCE=PASS",
    ):
        assert marker in script

    assert 'policy["rpm"]=1' in script
    assert 'policy["budget_usd"]=0.000001' in script


def test_g2_uses_real_genai_path_for_shared_otel():
    script = read(WRAPPER)
    assert '"http://127.0.0.1:8013/review"' in script
    assert "shared-observability" in script
    assert "logs deploy/otel-collector" in script
    assert "D090_G2_SHARED_OTEL_TRACE=PASS" in script


def test_g2_prometheus_scrape_query_preserves_tsdb():
    script = read(WRAPPER)
    helm = read(ROOT / "infra" / "helm" / "tradeops" / "templates" / "platform.yaml")
    standalone = read(ROOT / "infra" / "observability" / "prometheus.yml")

    assert "ai-access-policy:8020" in helm
    assert 'targets: ["ai-access-policy:8020"]' in standalone
    assert "D090_G2_PROMETHEUS_TARGET=PASS" in script
    assert "D090_G2_PROMETHEUS_QUERY=PASS" in script
    assert "kill -HUP 1" in script
    assert "rollout restart deploy/prometheus" not in script


def test_g2_probe_does_not_print_credentials():
    probe = read(PROBE)
    assert "print(token)" not in probe
    assert "print(client_secret)" not in probe
    assert "Authorization" in probe


def test_g2_waits_for_configmap_projection_before_hup():
    script = read(WRAPPER)
    assert 'D090_G2_PROM_CONFIG_WAIT_SECONDS:-180' in script
    assert 'D090_G2_PROMETHEUS_PROJECTION=PASS' in script
    assert 'kill -HUP 1' in script
    assert script.index('D090_G2_PROMETHEUS_PROJECTION=PASS') < script.index('kill -HUP 1')
    assert 'rollout restart deploy/prometheus' not in script
