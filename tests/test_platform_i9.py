from scripts.i9_validate_platform import ROOT, EXPECTED_APPS, validate_platform


def read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_i9_platform_validator_passes():
    assert validate_platform() == []


def test_target_workloads_are_packaged_and_legacy_signal_is_disabled():
    values = read("infra/helm/tradeops/values.yaml")
    assert all(f"  {name}:\n" in values for name in EXPECTED_APPS)
    assert "legacySignalEngine:\n  enabled: false" in values


def test_api_workloads_have_three_health_probes_and_resource_contracts():
    template = read("infra/helm/tradeops/templates/app-workloads.yaml")
    assert "startupProbe:" in template
    assert "readinessProbe:" in template
    assert "livenessProbe:" in template
    assert "toYaml $app.resources" in template


def test_platform_has_stateful_dependencies_and_observability():
    template = read("infra/helm/tradeops/templates/platform.yaml")
    assert template.count("kind: StatefulSet") == 3
    for name in ("postgres", "redpanda", "qdrant", "otel-collector", "prometheus", "grafana"):
        assert f"name: {name}" in template


def test_network_policy_starts_from_default_deny():
    network = read("infra/openshift/base/networkpolicies.yaml")
    assert "name: default-deny" in network
    assert "policyTypes: [Ingress, Egress]" in network
    assert "name: allow-dns-egress" in network
    assert "name: allow-router-ingress" in network


def test_quota_and_limitrange_are_versioned():
    assert "kind: ResourceQuota" in read("infra/openshift/base/resourcequota.yaml")
    assert "kind: LimitRange" in read("infra/openshift/base/limitrange.yaml")


def test_kyverno_uses_current_cel_policy_api_only():
    policy_dir = ROOT / "infra/openshift/policies/kyverno"
    policies = "\n".join(path.read_text(encoding="utf-8") for path in policy_dir.glob("*.yaml"))
    assert policies.count("kind: ValidatingPolicy") == 3
    assert "apiVersion: policies.kyverno.io/v1" in policies
    assert "kind: ClusterPolicy" not in policies
    assert "apiVersion: kyverno.io/v1" not in policies


def test_argocd_apps_target_real_repository_and_expected_paths():
    argo = "\n".join(
        read(path)
        for path in (
            "gitops/argocd/application.yaml",
            "gitops/argocd/platform-guardrails.yaml",
            "gitops/argocd/kyverno-policies.yaml",
        )
    )
    assert "example.com/your/repo" not in argo
    assert "https://github.com/zdmooc/TradeOps-GenAI-Integration.git" in argo
    assert "infra/helm/tradeops" in argo
    assert "infra/openshift/overlays/crc" in argo
    assert "infra/openshift/policies/kyverno" in argo


def test_unified_image_is_arbitrary_uid_compatible_and_pinned():
    dockerfile = read("Dockerfile.openshift")
    assert "chgrp -R 0 /app" in dockerfile
    assert "chmod -R g=u /app" in dockerfile
    assert "sentence-transformers==6.0.1" in dockerfile
    assert "qdrant-client==1.19.0" in dockerfile


def test_crc_operational_scripts_are_present_and_executable_by_contract():
    for name in ("i9_crc_preflight.sh", "i9_crc_deploy.sh", "i9_crc_verify.sh", "i9_image_scan.sh"):
        path = ROOT / "scripts" / name
        assert path.is_file()
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
