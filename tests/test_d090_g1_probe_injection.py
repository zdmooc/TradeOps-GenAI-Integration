from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "d090_run_g1_live_crc.sh"
DOCKERFILE = ROOT / "Dockerfile.openshift"


def test_g1_probe_is_injected_not_baked_into_runtime_image():
    runner = RUNNER.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "oc -n tradeops exec -i deploy/genai-api --" in runner
    assert "python -" in runner
    assert "< scripts/d090_real_model_probe.py" in runner
    assert "--evidence-out /tmp/d090-real-model.json" in runner
    assert "/app/scripts/d090_real_model_probe.py" not in runner
    assert "COPY scripts" not in dockerfile


def test_g1_probe_keeps_windows_path_conversion_guard():
    runner = RUNNER.read_text(encoding="utf-8")
    assert "MSYS_NO_PATHCONV=1 oc -n tradeops exec -i deploy/genai-api --" in runner
    assert "MSYS_NO_PATHCONV=1 oc -n tradeops exec deploy/genai-api --" in runner


def test_real_model_probe_reports_bounded_http_failure():
    probe = (ROOT / "scripts" / "d090_real_model_probe.py").read_text(encoding="utf-8")
    assert "urllib.error.HTTPError" in probe
    assert "D090_GATEWAY_HTTP_FAIL status=" in probe
    assert "[:512]" in probe


def test_runtime_issuer_probe_emits_only_issuer_contract():
    probe = (ROOT / "scripts" / "d090_runtime_issuer_probe.py").read_text(encoding="utf-8")
    assert "AI_OIDC_TOKEN_URL" in probe
    assert "AI_OIDC_CLIENT_SECRET" in probe
    assert 'claims.get("iss"' in probe
    assert "print(issuer)" in probe
    assert "print(token)" not in probe
