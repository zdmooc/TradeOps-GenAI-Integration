# TradeOps Web Cockpit — CRC live deployment evidence

Date: 2026-09-13

Runtime source commit deployed for the UI build: `c12356190e5daa3bf2a6a194df794b0565a7f240`.

## Verified OpenShift build

`tradeops-ui-1` completed successfully from Git commit `c123561`.

Published ImageStreamTag:

`tradeops-ui:i13-ui`

Image digest:

`sha256:8ff2900c8cdc2859cb226af6757522934efb12de92685536f42066172b7dbecf`

## Verified Helm deployment

Helm release: `tradeops`

- namespace: `tradeops`
- status: `deployed`
- revision: `5`
- deployment time reported by Helm: `Sun Sep 13 16:11:18 2026`

Verified runtime resources:

- `deployment.apps/tradeops-ui`: `1/1` Ready;
- `pod/tradeops-ui-6d55454df9-dk4jl`: `1/1 Running`;
- `service/tradeops-ui`: ClusterIP, port `8080/TCP`;
- `route.route.openshift.io/tradeops-ui`: `tradeops-ui-tradeops.apps-crc.testing`, edge TLS with redirect.

## Verified public URL

`https://tradeops-ui-tradeops.apps-crc.testing`

Direct checks returned HTTP 200 for:

- `/`
- `/healthz`
- `/api/market/health`
- `/api/workflow/health`
- `/api/agent/health`

Observed health payloads included:

- Market: `{"status":"ok"}`
- Workflow: `{"status":"ok"}`
- Agent Controller: status `ok`, mode `ANALYSIS_PLUS_HITL`, execution `SHADOW_OR_PAPER_AFTER_HUMAN_APPROVAL`.

## Repository verification script

`scripts/i9_crc_verify.sh` completed successfully against the real CRC cluster and ended with:

```text
TRADEOPS_UI_URL=https://tradeops-ui-tradeops.apps-crc.testing
I9_CRC_VERIFY_PASS
```

The script also reported successful rollout of the TradeOps deployments and StatefulSets required by the platform.

## Network/security evidence

The live namespace reported these relevant NetworkPolicies:

- `allow-intra-namespace` excludes `tradeops-ui`;
- `allow-router-ingress` includes `tradeops-ui`;
- `allow-tradeops-ui-backends` selects `tradeops-ui`;
- `default-deny` remains present.

This is consistent with the cockpit design where the frontend reaches only the approved backend services through same-origin proxying while sensitive services remain internal.

## Runtime-build incident encountered during deployment

Two attempted rebuilds of the heavy `tradeops-runtime` image were evicted because the single-node CRC environment crossed its ephemeral-storage eviction threshold. The failed builds were removed, DiskPressure returned to `False`, and the already-published healthy `tradeops-runtime:i9` image was reused for the existing running backends. The cockpit image itself then built and deployed successfully.

This does not invalidate the cockpit live proof; it is a local CRC capacity finding to address separately by slimming/splitting the runtime image or increasing local ephemeral storage before future full runtime rebuilds.

## Evidence boundary

This evidence proves **live CRC deployment and route/proxy health for the Web Cockpit**.

It does **not yet prove** the full interactive HITL business scenario. Remaining live functional proof:

1. create a decision proposal and observe `REVIEW_REQUIRED`;
2. perform an explicit human `APPROVE` or `REJECT`;
3. for an approved proposal, execute governed `SHADOW` or `PAPER` only;
4. verify the resulting audit record through the cockpit/API.

No real-money execution is part of this proof.

## Graduation status

This cockpit deployment does not change the I12 graduation blockers. They remain:

- `OPENSHIFT_AZURE_DEPLOYMENT`;
- `RESILIENCE_FINOPS_GREENOPS_VERIFIED`.
