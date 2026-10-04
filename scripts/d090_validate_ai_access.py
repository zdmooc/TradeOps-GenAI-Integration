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
        "scripts/d090_shared_isolation_probe.py",
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
