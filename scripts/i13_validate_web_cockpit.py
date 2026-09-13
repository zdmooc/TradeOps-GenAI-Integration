from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate_web_cockpit() -> list[str]:
    errors: list[str] = []
    required = (
        "frontend/tradeops-ui/package.json",
        "frontend/tradeops-ui/tsconfig.json",
        "frontend/tradeops-ui/vite.config.ts",
        "frontend/tradeops-ui/src/App.tsx",
        "frontend/tradeops-ui/src/api.ts",
        "frontend/tradeops-ui/src/demo.ts",
        "frontend/tradeops-ui/src/styles.css",
        "frontend/tradeops-ui/nginx.conf",
        "frontend/tradeops-ui/Dockerfile",
        "infra/helm/tradeops/templates/web-ui.yaml",
        "docs/27-tradeops-web-cockpit.md",
        "docs/28-demo-urls.md",
    )
    for relpath in required:
        if not (ROOT / relpath).is_file():
            errors.append(f"missing UI artifact: {relpath}")
    if errors:
        return errors

    app = _read("frontend/tradeops-ui/src/App.tsx")
    api = _read("frontend/tradeops-ui/src/api.ts")
    for marker in (
        "TradeOps Cockpit",
        "Human-in-the-Loop",
        "Créer proposition",
        "Approuver",
        "Aucun ordre réel",
        "DEMO_SYNTHETIC",
    ):
        if marker not in app:
            errors.append(f"UI capability missing: {marker}")
    for forbidden in (
        "localStorage.setItem",
        "localStorage.getItem",
        "VITE_MCP_AGENT_TOKEN",
        "VITE_MCP_REVIEWER_TOKEN",
    ):
        if forbidden in app or forbidden in api:
            errors.append(f"browser secret persistence/config forbidden: {forbidden}")

    nginx = _read("frontend/tradeops-ui/nginx.conf")
    for marker in (
        "listen 8080",
        "location = /healthz",
        "location /api/market/",
        "location /api/workflow/",
        "location /api/agent/",
        "Content-Security-Policy",
        "X-Frame-Options DENY",
    ):
        if marker not in nginx:
            errors.append(f"Nginx UI boundary missing: {marker}")
    for forbidden in ("mcp-server", "postgres:5432", "redpanda:9092", "qdrant:6333"):
        if forbidden in nginx:
            errors.append(f"sensitive internal service exposed by UI proxy: {forbidden}")

    dockerfile = _read("frontend/tradeops-ui/Dockerfile")
    for marker in (
        "FROM node:22-alpine AS build",
        "nginxinc/nginx-unprivileged:1.27-alpine",
        "npm run build",
        "EXPOSE 8080",
        "chmod -R g=u",
    ):
        if marker not in dockerfile:
            errors.append(f"UI image hardening/build missing: {marker}")

    values = _read("infra/helm/tradeops/values.yaml")
    for marker in (
        "webUi:",
        "tag: i13-ui",
        "tradeops-ui: 8080",
        "name: MCP_AGENT_TOKEN",
        "secretKey: MCP_AGENT_TOKEN",
        "name: MCP_REVIEWER_TOKEN",
        "secretKey: MCP_REVIEWER_TOKEN",
    ):
        if marker not in values:
            errors.append(f"Helm UI/auth contract missing: {marker}")

    template = _read("infra/helm/tradeops/templates/web-ui.yaml")
    for marker in (
        "name: tradeops-ui",
        "automountServiceAccountToken: false",
        "path: /healthz",
        "resources:",
        "include \"tradeops.containerSecurityContext\"",
    ):
        if marker not in template:
            errors.append(f"UI Helm deployment hardening missing: {marker}")

    build = _read("infra/openshift/base/build.yaml")
    for marker in (
        "name: tradeops-ui",
        "dockerfilePath: frontend/tradeops-ui/Dockerfile",
        "name: tradeops-ui:i13-ui",
    ):
        if marker not in build:
            errors.append(f"OpenShift UI build contract missing: {marker}")

    network = _read("infra/openshift/base/networkpolicies.yaml")
    if "tradeops-ui" not in network:
        errors.append("router ingress policy does not include tradeops-ui")

    deploy = _read("scripts/i9_crc_deploy.sh")
    for marker in ("MCP_AGENT_TOKEN", "MCP_REVIEWER_TOKEN", "start-build tradeops-ui"):
        if marker not in deploy:
            errors.append(f"CRC deploy does not prepare UI/HITL: {marker}")

    verify = _read("scripts/i9_crc_verify.sh")
    for marker in ("tradeops-ui", "route tradeops-ui", "/healthz"):
        if marker not in verify:
            errors.append(f"CRC verify does not prove UI route: {marker}")

    demo_urls = _read("docs/28-demo-urls.md")
    if "https://tradeops-ui-tradeops.apps-crc.testing" not in demo_urls:
        errors.append("demo URL catalog lacks canonical CRC cockpit URL")
    if "PLANNED | TradeOps Web Cockpit" not in demo_urls:
        errors.append("cockpit URL must remain PLANNED until live CRC evidence exists")

    return errors


def main() -> int:
    errors = validate_web_cockpit()
    if errors:
        for error in errors:
            print(f"I13_WEB_COCKPIT_VALIDATION_FAIL: {error}")
        return 1
    print("I13_WEB_COCKPIT_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
