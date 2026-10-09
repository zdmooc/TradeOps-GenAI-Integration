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

def test_default_host_is_loopback(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert aa1.ollama_base() == "http://127.0.0.1:11434"


@pytest.mark.parametrize("host,expected", [
    ("localhost:11434", "http://localhost:11434"),
    ("http://127.0.0.1:11434", "http://127.0.0.1:11434"),
    ("192.168.56.1:11434", "http://192.168.56.1:11434"),
])
def test_configured_local_host_is_used(monkeypatch, host, expected):
    monkeypatch.setenv("OLLAMA_HOST", host)
    assert aa1.ollama_base() == expected


@pytest.mark.parametrize("host", [
    "https://localhost:11434", "https://example.com:443",
    "http://example.com:11434", "http://user:pass@localhost:11434",
    "http://localhost:11434/other", "http://localhost:11434?x=1",
    "0.0.0.0:11434", "10.0.0.2:11434",
])
def test_non_local_or_ambiguous_host_is_rejected(monkeypatch, host):
    monkeypatch.setenv("OLLAMA_HOST", host)
    with pytest.raises(ValueError):
        aa1.ollama_base()


def test_version_probe_does_not_run_inference(monkeypatch, capsys):
    seen = []
    def request(path, data=None):
        seen.append((path, data))
        return {"version": "0.test"}
    monkeypatch.setattr(aa1, "local_request", request)
    assert aa1.main(["--probe"]) == 0
    assert seen == [("/api/version", None)]
    assert "D099_AA1_OLLAMA_API_PROBE_PASS" in capsys.readouterr().out


def test_allowed_api_paths_only():
    with pytest.raises(ValueError, match="unsupported Ollama API path"):
        aa1.local_request("/api/delete")


def test_proxy_handler_is_explicitly_disabled(monkeypatch):
    from urllib.request import ProxyHandler
    observed = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, *_): return b'{"version": "test"}'
    class Opener:
        def open(self, req, timeout):
            assert req.full_url.startswith("http://127.0.0.1:11434/api/")
            return Response()
    def fake_build(*handlers):
        observed.extend(handlers)
        return Opener()
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr(aa1, "build_opener", fake_build)
    assert aa1.local_request("/api/version") == {"version": "test"}
    assert any(isinstance(handler, ProxyHandler) and handler.proxies == {}
               for handler in observed)
