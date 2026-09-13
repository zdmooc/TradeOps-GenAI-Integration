# Iteration UI — TradeOps Web Cockpit implementation evidence

Status: **IMPLEMENTED / CI VALIDATION PENDING / LIVE CRC PENDING**

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

The URL remains `PLANNED` until `scripts/i9_crc_deploy.sh` and `scripts/i9_crc_verify.sh` succeed against CRC and evidence is committed.
