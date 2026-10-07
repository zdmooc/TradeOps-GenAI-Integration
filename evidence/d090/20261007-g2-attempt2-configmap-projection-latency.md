# D-090 G2 CRC live-governance attempt #2 — ConfigMap projection latency — 2026-10-07

Status: **RUNTIME ATTEMPT INCOMPLETE / SAFETY CLEANUP PASS / PROJECTION WAIT FIXED**

Observed before failure:
- OIDC client/audience/scope bootstrap PASS;
- G2 bounded window active;
- LiteLLM/Ollama rollout/readiness/reachability/real completion PASS;
- genai gateway mode PASS;
- runtime token issuer observed;
- canonical Kong hot reload/route/no-token denial/persistence PASS;
- G2 auth chain PASS;
- Prometheus ConfigMap patch helper returned `D090_G2_PROMETHEUS_PATCH=CHANGED`.

Failure:

```text
D090_G2_PROMETHEUS_CONFIG=FAIL mounted config did not update
```

Root cause:
- the Prometheus Deployment mounts the full ConfigMap directory at `/etc/prometheus`;
- this is not a `subPath` mount;
- OpenShift/Kubernetes ConfigMap projection is asynchronous;
- the previous 60-second hard timeout was too short for kubelet projection on this CRC workstation.

Safety cleanup:

```text
D090_G2_POLICY_RESTORE=PASS
D090_G2_WINDOW_REPARK=PASS
```

Correction:
- configurable projection wait with default 180 seconds;
- 5-second polling of the mounted file;
- explicit `D090_G2_PROMETHEUS_PROJECTION=PASS` before SIGHUP;
- Prometheus pod restart remains forbidden;
- ConfigMap resourceVersion is emitted on timeout for diagnostics;
- TradeOps PR #18 merged as `a121ac4fb1cfe76743ecdf920c285d5902915911`;
- CI run `37639015726` SUCCESS.

G2 remains **CRC_RUNTIME_PENDING** until the full corrected run returns `D090_G2_GOVERNANCE=PASS`.
