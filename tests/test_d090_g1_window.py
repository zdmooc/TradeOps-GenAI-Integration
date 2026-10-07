from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "crc" / "d090-g1-live-from-park.sh"


def read() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_g1_window_script_is_bash_syntax_valid():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_g1_window_requires_existing_park_snapshot_and_local_profile():
    script = read()
    assert 'grep -qx "PARKED"' in script
    assert 'PROFILE="${D090_LITELLM_PROFILE:-local-ollama}"' in script
    assert 'MODEL="${D090_LITELLM_MODEL:-ollama/qwen2.5:3b}"' in script
    assert "D090_LITELLM_API_BASE" in script
    assert "currently supports local-ollama only" in script


def test_g1_window_wakes_only_required_tradeops_deployments():
    script = read()
    assert "REQUIRED_DEPLOYMENTS=(ai-access-policy genai-api litellm)" in script
    assert "ACTIVATION_DEPLOYMENTS=(ai-access-policy genai-api)" in script
    assert 'scale "deployment/$name" --replicas="$replicas"' in script
    assert 'REQUIRED_DEPLOYMENTS=(ai-access-policy genai-api litellm)' in script
    assert 'ACTIVATION_DEPLOYMENTS=(ai-access-policy genai-api)' in script
    assert 'oc -n shared-observability wait --for=condition=Available deploy/otel-collector' in script
    assert 'oc -n "$NAMESPACE" scale "deployment/$name"' in script


def test_g1_window_runs_existing_g1_chain_and_reparks():
    script = read()
    assert "bash scripts/d090_deploy_litellm_crc.sh" in script
    assert "D090_G1_WINDOW_BASE_ACTIVE=PASS" in script
    assert "bash scripts/d090_enable_genai_crc.sh" in script
    assert "bash scripts/d090_run_g1_live_crc.sh" in script
    assert 'scale "deployment/$name" --replicas=0' in script
    assert "D090_G1_WINDOW_REPARK=PASS" in script
    assert "D090_G1_FROM_PARK=PASS" in script


def test_g1_window_does_not_touch_statefulsets_or_global_prune():
    script = read()
    assert "statefulset/" not in script
    assert "oc delete namespace" not in script
    assert "oc delete project" not in script
    assert "oc adm prune" not in script


def test_g1_window_refreshes_identity_and_canonical_kong_before_probe():
    script = read()
    assert "D090_API_MANAGEMENT_REPO" in script
    assert "mayabank-api-management-architecture" in script
    assert "bash scripts/d090_bootstrap_oidc_crc.sh" in script
    assert "D090_G1_AUTH_MATERIAL_REFRESH=PASS" in script
    assert "runtime/shared-platform/scripts/enable-d090-ai-access-crc.sh" in script
    assert "D090_G1_KONG_JWT_REFRESH=PASS" in script

    bootstrap = script.index("bash scripts/d090_bootstrap_oidc_crc.sh")
    activate = script.index('echo "D090_G1_WINDOW_BASE_ACTIVE=PASS"')
    kong = script.index("bash runtime/shared-platform/scripts/enable-d090-ai-access-crc.sh")
    probe = script.index("bash scripts/d090_run_g1_live_crc.sh")
    assert bootstrap < activate < kong < probe
