from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate() -> list[str]:
    errors: list[str] = []
    required = (
        "services/genai_api/llm.py",
        "services/genai_api/ai_access.py",
        "services/ai_access_policy/main.py",
        "services/ai_access_policy/run.py",
        "infra/ai-access/kong.template.yml",
        "infra/ai-access/consumers.example.json",
        "infra/ai-access/values-ai-access.example.yaml",
        "infra/ai-access/litellm-config.example.yaml",
        "infra/ai-access/litellm-deployment.example.yaml",
        "scripts/d090_real_model_probe.py",
        "scripts/d090_g2_governance_probe.py",
        "scripts/crc/d090-g2-live-governance-from-park.sh",
        "scripts/d090_shared_isolation_probe.py",
        "scripts/d090_bootstrap_oidc_crc.sh",
        "scripts/d090_prepare_crc.sh",
        "infra/ai-access/D090_CRC_RUNBOOK.md",
        "scripts/d090_run_g1_live_crc.sh",
        "scripts/d090_enable_genai_crc.sh",
        "scripts/d090_deploy_litellm_crc.sh",
        "infra/ai-access/ai-access-policy-crc.yaml",
        "infra/ai-access/litellm-deployment-crc.yaml",
        "infra/ai-access/networkpolicy-local-ollama-crc.template.yaml",
        "tests/test_ai_access_d090.py",
        "tests/test_ai_access_policy_d090.py",
    )
    for path in required:
        if not (ROOT / path).is_file():
            errors.append(f"missing D-090 artifact: {path}")

    if errors:
        return errors

    values = read("infra/helm/tradeops/values.yaml")
    for marker in (
        "ai-access-policy:",
        "enabled: false",
        "module: services.ai_access_policy.run",
        "secretKey: AI_ACCESS_OIDC_JWKS_JSON",
        "secretKey: AI_ACCESS_CONSUMERS_JSON",
        "secretKey: LITELLM_API_KEY",
    ):
        if marker not in values:
            errors.append(f"AI Access Helm packaging missing: {marker}")

    overlay = read("infra/ai-access/values-ai-access.example.yaml")
    for marker in (
        "LLM_PROVIDER: gateway",
        "AI_GATEWAY_AUTH_MODE: client_credentials",
        "AI_OIDC_CLIENT_ID: tradeops-ai",
        "AI_GATEWAY_MODEL_ALIAS: tradeops-default",
        "ai-access-policy:",
        "enabled: true",
    ):
        if marker not in overlay:
            errors.append(f"G1 overlay missing: {marker}")

    policy = read("services/ai_access_policy/main.py")
    for marker in (
        "MISSING_TOKEN",
        "SCOPE_DENIED",
        "UNKNOWN_CONSUMER",
        "MODEL_DENIED",
        "QUOTA_EXCEEDED",
        "BUDGET_EXCEEDED",
        "/metrics",
        "mayabank_ai_access_requests_total",
        "mayabank_ai_access_denials_total",
    ):
        if marker not in policy:
            errors.append(f"G2 policy/telemetry missing: {marker}")

    probe = read("scripts/d090_real_model_probe.py")
    for marker in (
        "D090_OIDC_TOKEN=PASS",
        "D090_CONSUMER_IDENTITY=PASS",
        "D090_PROVIDER_EVIDENCE=PASS",
        "D090_MODEL_EVIDENCE=PASS",
        "D090_REAL_MODEL_PATH=PASS",
    ):
        if marker not in probe:
            errors.append(f"G1 evidence probe missing: {marker}")

    litellm = read("infra/ai-access/litellm-deployment.example.yaml")
    if "ghcr.io/berriai/litellm:v1.103.0" not in litellm:
        errors.append("LiteLLM example must pin v1.103.0")
    if ":latest" in litellm:
        errors.append("LiteLLM example must not use latest")

    bootstrap = read("scripts/d090_bootstrap_oidc_crc.sh")
    for marker in (
        "tradeops-ai",
        "ai-gateway",
        "ai.inference",
        "D090_SHARED_OIDC_CLIENT=PASS",
        "D090_RUNTIME_SECRET_MERGE=PASS",
    ):
        if marker not in bootstrap:
            errors.append(f"G1 CRC OIDC bootstrap missing: {marker}")

    prepare = read("scripts/d090_prepare_crc.sh")
    if "D090_G1A_PREPARE=PASS" not in prepare:
        errors.append("G1 CRC prepare marker missing")

    crc_policy = read("infra/ai-access/ai-access-policy-crc.yaml")
    for marker in (
        "https://keycloak.apps-crc.testing/realms/mayabank",
        "AI_ACCESS_OIDC_AUDIENCE",
        "ai-gateway",
        "LITELLM_BASE_URL",
        "http://litellm:4000",
        "AI_ACCESS_UPSTREAM_TIMEOUT_SECONDS",
        'value: "120"',
    ):
        if marker not in crc_policy:
            errors.append(f"G1 CRC AI Access manifest missing: {marker}")

    litellm_crc = read("infra/ai-access/litellm-deployment-crc.yaml")
    for marker in (
        "ghcr.io/berriai/litellm:v1.103.0",
        "LITELLM_PROVIDER_API_KEY",
        "TRADEOPS_LITELLM_API_BASE",
        "d090-ai-model",
        "d090-litellm-config",
    ):
        if marker not in litellm_crc:
            errors.append(f"G1 CRC LiteLLM manifest missing: {marker}")

    deploy = read("scripts/d090_deploy_litellm_crc.sh")
    for marker in (
        "D090_LITELLM_MODEL",
        "D090_PROVIDER_API_KEY",
        "D090_LITELLM_DEPLOY=PASS",
        "openai/gpt-6-luna",
        "OPENAI_API_KEY",
        "tradeops-default",
        "odm-extraction",
        "local-ollama",
        "ollama/qwen2.5:3b",
        "D090_OLLAMA_HOST_RESOLUTION=PASS",
        "D090_OLLAMA_NETWORKPOLICY=PASS",
        "D090_OLLAMA_REACHABILITY=PASS",
        "D090_LITELLM_LOCAL_MODEL_E2E=PASS",
        "D090_LOCAL_REAL_MODEL_PRECHECK=PASS",
    ):
        if marker not in deploy:
            errors.append(f"G1-B LiteLLM deploy gate missing: {marker}")

    local_np = read("infra/ai-access/networkpolicy-local-ollama-crc.template.yaml")
    for marker in (
        "allow-litellm-to-local-ollama",
        "__OLLAMA_HOST_CIDR__",
        "app.kubernetes.io/name: litellm",
        "port: 11434",
    ):
        if marker not in local_np:
            errors.append(f"G1 local Ollama NetworkPolicy missing: {marker}")

    live = read("scripts/d090_run_g1_live_crc.sh")
    for marker in (
        "D090_LOCAL_REAL_MODEL_PROFILE=PASS",
        "D090_G1_CLAIM=LOCAL_REAL_MODEL_PROVEN",
        "MSYS_NO_PATHCONV=1 oc -n tradeops exec deploy/genai-api",
    ):
        if marker not in live:
            errors.append(f"G1 local evidence wrapper missing: {marker}")

    enable = read("scripts/d090_enable_genai_crc.sh")
    for marker in (
        "LLM_PROVIDER=gateway",
        "api-gateway.mayabank-api.svc:8000/ai",
        "keycloak-service.keycloak-system.svc:8080",
        "otel-collector.shared-observability.svc:4318",
        "AI_OIDC_CLIENT_SECRET",
        "AI_GATEWAY_TIMEOUT_SECONDS=120",
        "oc -n tradeops exec -i deploy/genai-api",
        "D090_GENAI_GATEWAY_MODE=PASS",
    ):
        if marker not in enable:
            errors.append(f"G1-B genai enable gate missing: {marker}")

    live = read("scripts/d090_run_g1_live_crc.sh")
    for marker in (
        "d090_real_model_probe.py",
        "D090_REAL_MODEL_PATH=PASS",
        "mayabank_ai_access_requests_total",
        "D090_G1_LIVE=PASS",
    ):
        if marker not in live:
            errors.append(f"G1 live evidence wrapper missing: {marker}")

    g2 = read("scripts/crc/d090-g2-live-governance-from-park.sh")
    for marker in (
        "D090_G2_BASELINE_METRICS=PASS",
        "D090_G2_SHARED_OTEL_TRACE=PASS",
        "D090_G2_PROMETHEUS_TARGET=PASS",
        "D090_G2_PROMETHEUS_QUERY=PASS",
        "D090_G2_QUOTA_METRICS=PASS",
        "D090_G2_COST_METRIC=PASS",
        "D090_G2_POLICY_RESTORE=PASS",
        "D090_G2_GOVERNANCE=PASS",
    ):
        if marker not in g2:
            errors.append(f"G2 live governance wrapper missing: {marker}")

    prom = read("infra/helm/tradeops/templates/platform.yaml")
    if "ai-access-policy:8020" not in prom:
        errors.append("G2 Prometheus target missing: ai-access-policy:8020")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"D090_AI_ACCESS_VALIDATION_FAIL: {error}")
        return 1
    print("D090_AI_ACCESS_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
