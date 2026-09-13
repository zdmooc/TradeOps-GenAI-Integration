# Iteration UI — TradeOps Web Cockpit implementation evidence

Status: **IMPLEMENTED + TESTED IN CI / LIVE CRC PENDING**

## CI evidence — 2026-09-13

Runtime commit: `17d47d33a663b78fd5e23518927929fe5e43b4ce`.

GitHub Actions CI run **#92**, run id `34750050606`: **SUCCESS**.

Verified gates:

- Ruff: PASS;
- `SECURITY_AUDIT_PASS`;
- `SBOM_CHECK_PASS`;
- Node 22 / npm install: PASS;
- React/TypeScript production build: PASS (`tsc -b && vite build`);
- Vite 5.4.14: 33 modules transformed, production bundle generated;
- Helm lint: 1 chart linted, 0 failed;
- Helm render: PASS;
- `I9_PLATFORM_VALIDATION_PASS`;
- `I10_AI_SERVING_VALIDATION_PASS`;
- `I13_WEB_COCKPIT_VALIDATION_PASS`;
- Terraform fmt/init/validate: PASS with AzureRM 5.2.0;
- `I11_AZURE_TARGET_VALIDATION_PASS`;
- I12 graduation checker: PASS with expected `NOT_GRADUATED` state;
- Pytest: **230 passed, 69 non-blocking warnings in 18.50s**.

Graduation remains correctly blocked only by:

- `OPENSHIFT_AZURE_DEPLOYMENT`;
- `RESILIENCE_FINOPS_GREENOPS_VERIFIED`.

## Implemented artifacts

- React 18 + TypeScript + Vite frontend under `frontend/tradeops-ui`;
- responsive cockpit, market cards, signal detail, agent evidence, HITL, performance, audit and platform views;
- same-origin Nginx proxy to market-data, workflow-api and agent-controller only;
- CSP/security headers and no committed/browser-persisted credentials;
- OpenShift arbitrary-UID-compatible unprivileged Nginx image;
- `tradeops-ui` ImageStream/BuildConfig;
- Helm Deployment/Service/Route and CRC sizing;
- NetworkPolicy router ingress update;
- CRC deploy/verify script integration;
- GitHub Actions Node build plus `i13_validate_web_cockpit.py`;
- canonical demo URL catalog.

## Claims intentionally not made yet

- no live CRC Route claim until deployment evidence exists;
- no real-time IG feed claim; current market API is synthetic/demo;
- no real-money execution;
- no production OIDC/Entra browser auth claim;
- no real performance claim from the UI's labelled `DEMO_SYNTHETIC` outcomes.

## Live target

`https://tradeops-ui-tradeops.apps-crc.testing`

The URL remains `PLANNED` until `scripts/i9_crc_deploy.sh` and `scripts/i9_crc_verify.sh` succeed against the real CRC and live evidence is committed.
