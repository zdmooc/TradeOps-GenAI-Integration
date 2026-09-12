from pathlib import Path

from scripts.i10_capacity_plan import required_replicas
from scripts.i10_validate_ai_serving import ROOT, validate


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_i10_platform_validator_passes():
    assert validate() == []


def test_rhoai_target_is_versioned():
    version = read("infra/openshift-ai/VERSION")
    assert "RHOAI_TARGET=3.4" in version
    assert "RHOAI_MANAGED_OPERATOR" in version


def test_signal_quality_serving_is_ha_and_bounded():
    text = read("infra/openshift-ai/base/inferenceservice-signal-quality.yaml")
    assert "minReplicas: 2" in text
    assert "maxReplicas: 4" in text
    assert "MODEL_SERVING_MODE" in text
    assert "MLFLOW_TRACKING_AUTH" in text


def test_vllm_example_requires_gpu_and_explicit_storage_replacement():
    text = read("infra/openshift-ai/examples/inferenceservice-vllm.yaml")
    assert "runtime: vllm-runtime" in text
    assert 'nvidia.com/gpu: "1"' in text
    assert "s3://REPLACE-ME/" in text


def test_capacity_plan_keeps_two_replica_ha_floor():
    assert required_replicas(1.0, 0.1, 10.0) == 2


def test_capacity_plan_scales_above_ha_floor():
    assert required_replicas(100.0, 0.5, 10.0, 0.5) == 10


def test_capacity_plan_rejects_invalid_utilization():
    try:
        required_replicas(10.0, 0.1, 2.0, 0.0)
    except ValueError as exc:
        assert "target_utilization" in str(exc)
    else:
        raise AssertionError("invalid utilization must be rejected")


def test_operational_scripts_exist():
    for name in (
        "i10_rhoai_preflight.sh",
        "i10_rhoai_deploy.sh",
        "i10_rhoai_verify.sh",
    ):
        path = Path(ROOT) / "scripts" / name
        assert path.is_file()
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
