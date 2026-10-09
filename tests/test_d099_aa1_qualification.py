"""No network; measurement data is synthetic and NOT official AA1 evidence."""
from scripts.d099_aa1_qualification import inspect


def fixture():
    return {
        "model_id": "test/fictional-instruct",
        "model_digest": "a" * 64,
        "endpoint": "http://127.0.0.1:11434/v1",
        "advertised_context_tokens": 65536,
        "observed_context_tokens": 65536,
        "host_memory_mib": 32768,
        "peak_process_memory_mib": 8000,
        "elapsed_ms": 1000,
        "opencode_json_contract": "PASS",
        "resolved_policy": "DENY_WITH_EXTERNAL_TRACE",
        "source_evidence": "USER_CAPTURED_LOCAL",
    }


def test_complete_synthetic_packet_only_enables_review():
    report = inspect(fixture())
    assert report["status"] == "AA1_EVIDENCE_REVIEW_READY"
    assert report["AA1_LOCAL_MODEL_BASELINE_VALIDATED"] is False


def test_32k_model_is_not_64k_qualified():
    m = fixture()
    m["advertised_context_tokens"] = 32768
    m["observed_context_tokens"] = 32768
    report = inspect(m)
    assert "ADVERTISED_CONTEXT_TOKENS_BELOW_TARGET_OR_UNMEASURED" in report["violations"]
    assert "OBSERVED_CONTEXT_TOKENS_BELOW_TARGET_OR_UNMEASURED" in report["violations"]


def test_missing_runtime_policy_and_memory_are_blocking():
    m = fixture()
    m["resolved_policy"] = "DENY_ONLY_REQUESTED"
    m["peak_process_memory_mib"] = 0
    report = inspect(m)
    assert "POLICY_RUNTIME_DENIAL_NOT_PROVEN" in report["violations"]
    assert "PEAK_PROCESS_MEMORY_MIB_UNMEASURED" in report["violations"]


def test_no_external_endpoint_cloud_or_model_without_digest():
    m = fixture()
    m["model_digest"] = "unknown"
    m["endpoint"] = "https://model.vendor.example/v1"
    report = inspect(m)
    assert "MODEL_DIGEST_NOT_PINNED" in report["violations"]
    assert "UNAPPROVED_PROVIDER_ENDPOINT" in report["violations"]


def test_false_positive_boolean_metrics_denied():
    m = fixture()
    m["observed_context_tokens"] = True
    m["elapsed_ms"] = True
    report = inspect(m)
    assert "OBSERVED_CONTEXT_TOKENS_BELOW_TARGET_OR_UNMEASURED" in report["violations"]
    assert "ELAPSED_MS_UNMEASURED" in report["violations"]
