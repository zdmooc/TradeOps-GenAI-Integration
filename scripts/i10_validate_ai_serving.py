#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate() -> list[str]:
    findings: list[str] = []
    version = read("infra/openshift-ai/VERSION")
    if "RHOAI_TARGET=3.4" not in version:
        findings.append("RHOAI target must be explicitly versioned")

    runtime = read("infra/openshift-ai/base/servingruntime-signal-quality.yaml")
    service = read("infra/openshift-ai/base/inferenceservice-signal-quality.yaml")
    vllm = read("infra/openshift-ai/examples/inferenceservice-vllm.yaml")
    rbac = read("infra/openshift-ai/base/serviceaccount-rbac.yaml")
    rules = read("infra/openshift-ai/monitoring/slo-rules.yaml")
    preflight = read("scripts/i10_rhoai_preflight.sh")

    checks = {
        "ServingRuntime API": "apiVersion: serving.kserve.io/v1alpha1" in runtime,
        "InferenceService API": "apiVersion: serving.kserve.io/v1beta1" in service,
        "raw deployment": "serving.kserve.io/deploymentMode: RawDeployment" in service,
        "HA min replicas": "minReplicas: 2" in service,
        "bounded max replicas": "maxReplicas: 4" in service,
        "resource requests": "requests:" in runtime and "limits:" in runtime,
        "readiness probe": "/health/ready" in runtime,
        "liveness probe": "/health/live" in runtime,
        "MLflow RBAC": "mlflow-operator-mlflow-integration" in rbac,
        "Kubernetes MLflow auth": "MLFLOW_K8S_INTEGRATION" in service,
        "no model URI in git": "models:/" not in service,
        "vLLM runtime": "runtime: vllm-runtime" in vllm,
        "vLLM GPU": 'nvidia.com/gpu: "1"' in vllm,
        "vLLM placeholder storage": "s3://REPLACE-ME/" in vllm,
        "SLO availability alert": "TradeOpsModelServingUnavailable" in rules,
        "SLO error alert": "TradeOpsModelServingErrorRateHigh" in rules,
        "SLO latency alert": "TradeOpsModelServingP95High" in rules,
        "KServe preflight": "inferenceservices.serving.kserve.io" in preflight,
        "MLflow operator preflight": "mlflowoperator.managementState" in preflight,
    }
    findings.extend(name for name, passed in checks.items() if not passed)

    if ":latest" in runtime or ":latest" in service or ":latest" in vllm:
        findings.append("mutable latest image tag is forbidden")
    return findings


def main() -> None:
    findings = validate()
    if findings:
        for finding in findings:
            print(f"I10_AI_SERVING_VALIDATION_FAIL: {finding}")
        raise SystemExit(1)
    print("I10_AI_SERVING_VALIDATION_PASS")


if __name__ == "__main__":
    main()
