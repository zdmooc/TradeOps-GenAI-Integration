# Iteration UI — TradeOps Web Cockpit implementation evidence

Status: **DEPLOYED LIVE ON CRC / PLATFORM VERIFIED / END-TO-END HITL LIVE PROOF PENDING**

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

## Live CRC evidence — 2026-09-13

Deployment source commit for the UI build:

`c12356190e5daa3bf2a6a194df794b0565a7f240`

Verified live facts:

- OpenShift build `tradeops-ui-1`: `Complete`;
- ImageStreamTag `tradeops-ui:i13-ui` published;
- image digest `sha256:8ff2900c8cdc2859cb226af6757522934efb12de92685536f42066172b7dbecf`;
- Helm release `tradeops`: `STATUS: deployed`, revision `5`;
- `deployment.apps/tradeops-ui`: `1/1` Ready;
- runtime pod `tradeops-ui-6d55454df9-dk4jl`: `1/1 Running`;
- Service `tradeops-ui` exposed internally on port `8080`;
- Route `tradeops-ui-tradeops.apps-crc.testing` created with edge TLS/Redirect;
- UI `/`: HTTP 200;
- `/healthz`: HTTP 200;
- `/api/market/health`: HTTP 200;
- `/api/workflow/health`: HTTP 200;
- `/api/agent/health`: HTTP 200;
- `scripts/i9_crc_verify.sh`: `I9_CRC_VERIFY_PASS`.

Canonical LIVE URL:

`https://tradeops-ui-tradeops.apps-crc.testing`

Detailed evidence:

`evidence/graduation/live/ui/20260913/README.md`

## Runtime capacity finding

During deployment, two rebuild attempts of the heavy `tradeops-runtime` image were evicted by the single-node CRC kubelet because of low `ephemeral-storage`. DiskPressure returned to `False` after removal of failed builds. The already-published healthy `tradeops-runtime:i9` image and the running backend deployments were reused, while the dedicated `tradeops-ui` image built successfully.

This is a CRC capacity/build-optimization finding, not a failure of the cockpit runtime deployment. Future work should slim or split the heavy runtime image and/or provision more ephemeral storage before a full rebuild.

## Claims intentionally bounded

The following claims are now supported:

- the Web Cockpit is deployed and reachable on real CRC;
- the canonical Route is LIVE;
- the UI health endpoint works;
- same-origin proxy health to Market, Workflow and Agent works;
- the platform verification script passes.

The following are still not claimed as live-proven:

- complete `REVIEW_REQUIRED -> human review -> SHADOW/PAPER -> audit` business flow;
- real-time IG feed; current market API remains synthetic/demo;
- real-money execution;
- production OIDC/Entra browser auth;
- real performance from the UI's labelled `DEMO_SYNTHETIC` outcomes.

## Remaining live functional proof

1. create a governed decision proposal and observe `REVIEW_REQUIRED`;
2. perform an explicit reviewer `APPROVE` or `REJECT`;
3. for approval, execute `SHADOW` or `PAPER` only;
4. verify the resulting audit event.

No real-money order is permitted or required.
