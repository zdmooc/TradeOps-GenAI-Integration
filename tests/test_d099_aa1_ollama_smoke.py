"""D-099 AA1 smoke tests: mocked local HTTP only, never run an LLM in CI."""
import pytest

from scripts import d099_aa1_ollama_smoke as aa1


def test_denies_without_explicit_consent(monkeypatch):
    monkeypatch.setattr(aa1, "local_request", lambda *a, **kw: pytest.fail("network called"))
    with pytest.raises(ValueError, match="required"):
        aa1.smoke("qwen:3b", consent="NO")


@pytest.mark.parametrize("name", ["cloud-model:cloud", "../malicious name", "bad?name"])
def test_reject_cloud_or_invalid_model(name, monkeypatch):
    monkeypatch.setattr(aa1, "local_request", lambda *a, **kw: pytest.fail("network called"))
    with pytest.raises(ValueError):
        aa1.smoke(name, consent="YES")


def test_reject_uninstalled(monkeypatch):
    monkeypatch.setattr(aa1, "local_request", lambda *a, **kw: {"models": []})
    with pytest.raises(ValueError, match="not installed"):
        aa1.smoke("qwen:3b", consent="YES")


def test_json_smoke_is_not_opencode_qualification(monkeypatch):
    def request(path, data=None):
        if path == "/api/tags":
            return {"models": [{"name": "qwen:3b", "digest": "sha256:fake", "size": 5}]}
        assert path == "/api/generate"
        assert data["model"] == "qwen:3b"
        return {"response": '{"ok": true, "purpose": "local-smoke"}',
                "total_duration": 1234, "eval_count": 12}
    monkeypatch.setattr(aa1, "local_request", request)
    result = aa1.smoke("qwen:3b", consent="YES")
    assert result["status"] == "LOCAL_JSON_SMOKE_PASS"
    assert result["AA1_LOCAL_MODEL_BASELINE_VALIDATED"] is False
    assert result["opencode_run"] == "NOT_TESTED"
    assert result["host_cpu_ram"] == "NOT_MEASURED"


def test_json_semantic_mismatch_fails(monkeypatch):
    def request(path, data=None):
        if path == "/api/tags":
            return {"models": [{"name": "qwen:3b"}]}
        return {"response": '{"ok": false, "purpose": "local-smoke"}'}
    monkeypatch.setattr(aa1, "local_request", request)
    assert aa1.smoke("qwen:3b", consent="YES")["status"] == "LOCAL_JSON_SMOKE_FAIL"
