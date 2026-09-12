from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_APPS = (
    "market-data",
    "workflow-api",
    "genai-api",
    "rag-api",
    "agent-controller",
    "mcp-server",
    "risk-engine",
    "paper-oms",
    "notifier",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate_platform() -> list[str]:
    errors: list[str] = []
    required_paths = (
        "Dockerfile.openshift",
        "infra/helm/tradeops/Chart.yaml",
        "infra/helm/tradeops/values.yaml",
        "infra/helm/tradeops/values-crc.yaml",
        "infra/helm/tradeops/templates/app-workloads.yaml",
        "infra/helm/tradeops/templates/platform.yaml",
        "infra/helm/tradeops/templates/routes.yaml",
        "infra/openshift/base/resourcequota.yaml",
        "infra/openshift/base/limitrange.yaml",
        "infra/openshift/base/networkpolicies.yaml",
        "infra/openshift/overlays/crc/kustomization.yaml",
        "infra/openshift/policies/kyverno/kustomization.yaml",
        "gitops/argocd/application.yaml",
        "gitops/argocd/platform-guardrails.yaml",
        "gitops/argocd/kyverno-policies.yaml",
        "scripts/i9_crc_preflight.sh",
        "scripts/i9_crc_deploy.sh",
        "scripts/i9_crc_verify.sh",
    )
    for relpath in required_paths:
        if not (ROOT / relpath).is_file():
            errors.append(f"missing required I9 artifact: {relpath}")

    if errors:
        return errors

    values = _read("infra/helm/tradeops/values.yaml")
    for app in EXPECTED_APPS:
        if f"  {app}:\n" not in values:
            errors.append(f"target workload missing from Helm values: {app}")
    if "legacySignalEngine:\n  enabled: false" not in values:
        errors.append("legacy signal-engine must remain explicitly disabled")
    if "tag: latest" in values or ":latest" in values:
        errors.append("Helm values must not use latest image tags")
    if "image: qdrant/qdrant:v1.19.0" not in values:
        errors.append("Qdrant server must stay aligned with qdrant-client 1.19.0")

    crc_values = _read("infra/helm/tradeops/values-crc.yaml")
    for required in (
        "ephemeralPlatformStorage: true",
        "HF_HOME: /tmp/huggingface",
    ):
        if required not in crc_values:
            errors.append(f"CRC runtime value missing: {required}")

    workload = _read("infra/helm/tradeops/templates/app-workloads.yaml")
    for required in (
        "startupProbe:",
        "readinessProbe:",
        "livenessProbe:",
        "resources:",
        "allowPrivilegeEscalation",
        "secretKeyRef:",
        "automountServiceAccountToken: false",
    ):
        if required not in workload and required not in _read(
            "infra/helm/tradeops/templates/_helpers.tpl"
        ):
            errors.append(f"Helm workload hardening missing: {required}")

    platform = _read("infra/helm/tradeops/templates/platform.yaml")
    for required in (
        "--rpc-addr",
        "0.0.0.0:33145",
        "--advertise-rpc-addr",
        "redpanda:33145",
        "QDRANT__STORAGE__STORAGE_PATH",
        "/tmp/qdrant-storage",
        "QDRANT__STORAGE__SNAPSHOTS_PATH",
        "/tmp/qdrant-snapshots",
    ):
        if required not in platform:
            errors.append(f"CRC platform compatibility missing: {required}")

    network = _read("infra/openshift/base/networkpolicies.yaml")
    for required in (
        "name: default-deny",
        "name: allow-intra-namespace",
        "name: allow-dns-egress",
        "name: allow-router-ingress",
        "name: allow-external-https-egress",
        "name: allow-openshift-build-egress",
    ):
        if required not in network:
            errors.append(f"NetworkPolicy missing: {required}")
    for required in (
        "key: openshift.io/build.name",
        "port: 443",
        "port: 5000",
        "kubernetes.io/metadata.name: openshift-image-registry",
    ):
        if required not in network:
            errors.append(f"OpenShift build egress policy incomplete: {required}")
    for required in (
        "values: [market-data, genai-api, rag-api]",
        "port: 53",
        "port: 5353",
        "kubernetes.io/metadata.name: openshift-dns",
    ):
        if required not in network:
            errors.append(f"CRC application egress policy incomplete: {required}")

    for relpath in (
        "infra/openshift/policies/kyverno/require-resources.yaml",
        "infra/openshift/policies/kyverno/disallow-latest.yaml",
        "infra/openshift/policies/kyverno/require-container-security.yaml",
    ):
        policy = _read(relpath)
        if "apiVersion: policies.kyverno.io/v1" not in policy:
            errors.append(f"Kyverno current API missing in {relpath}")
        if "kind: ValidatingPolicy" not in policy:
            errors.append(f"Kyverno ValidatingPolicy missing in {relpath}")
        if "kind: ClusterPolicy" in policy or "apiVersion: kyverno.io/v1" in policy:
            errors.append(f"legacy Kyverno policy type forbidden in {relpath}")

    argo = "\n".join(
        _read(path)
        for path in (
            "gitops/argocd/application.yaml",
            "gitops/argocd/platform-guardrails.yaml",
            "gitops/argocd/kyverno-policies.yaml",
        )
    )
    if "example.com/your/repo" in argo:
        errors.append("placeholder Argo CD repository is forbidden")
    if argo.count("apiVersion: argoproj.io/v1alpha1") != 3:
        errors.append("all three Argo CD Applications must use argoproj.io/v1alpha1")
    if "targetRevision: main" not in argo:
        errors.append("Argo CD must pin the repository branch explicitly")

    dockerfile = _read("Dockerfile.openshift")
    for pin in (
        "torch==2.14.0+cpu",
        "sentence-transformers==6.0.1",
        "qdrant-client==1.19.0",
    ):
        if pin not in dockerfile:
            errors.append(f"OpenShift runtime image dependency is not pinned: {pin}")
    if "https://download.pytorch.org/whl/cpu" not in dockerfile:
        errors.append("OpenShift CRC image must use the CPU-only PyTorch wheel index")
    if "chgrp -R 0 /app" not in dockerfile or "chmod -R g=u /app" not in dockerfile:
        errors.append("OpenShift arbitrary-UID compatibility permissions are missing")

    build = _read("infra/openshift/base/build.yaml")
    if "dockerfilePath: Dockerfile.openshift" not in build:
        errors.append("BuildConfig does not use the unified OpenShift runtime image")

    return errors


def main() -> int:
    errors = validate_platform()
    if errors:
        for error in errors:
            print(f"I9_PLATFORM_VALIDATION_FAIL: {error}")
        return 1
    print("I9_PLATFORM_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
