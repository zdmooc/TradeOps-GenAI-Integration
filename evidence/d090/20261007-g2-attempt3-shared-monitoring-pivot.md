# D-090 G2 CRC live-governance attempt #3 — product Prometheus projection remains stale — 2026-10-07

Status: **RUNTIME ATTEMPT INCOMPLETE / SAFETY CLEANUP PASS / OBSERVABILITY PATH CORRECTED**

## Observed pass markers

The third G2 attempt again passed:
- shared OIDC bootstrap;
- bounded TradeOps activation;
- LiteLLM/Ollama rollout, readiness, reachability and real completion;
- genai gateway mode;
- runtime issuer observation;
- canonical Kong hot reload / route / no-token denial / persistence;
- G2 auth chain.

The API ConfigMap already contained the desired AI Access target:

```text
D090_G2_PROMETHEUS_PATCH=ALREADY_PRESENT
```

But after the extended 180-second wait, the running product Prometheus pod still did not observe the updated mounted file:

```text
D090_G2_PROMETHEUS_CONFIG=FAIL mounted config did not update within 180s resourceVersion=7762402
```

## Interpretation

This is no longer treated as ordinary projection latency.

The repository desired state and API ConfigMap contain `ai-access-policy:8020`, while the existing CRC Prometheus pod remains on stale projected content. Restarting that pod only to refresh configuration would destroy its `emptyDir` TSDB and is not justified for the G2 governance proof.

## Safety cleanup

```text
D090_G2_POLICY_RESTORE=PASS
D090_G2_WINDOW_REPARK=PASS
```

No StatefulSet was scaled and the product Prometheus pod was not restarted.

## Architecture correction

G2 runtime observability is moved to the existing shared OpenShift monitoring capability, consistent with the ODM workload:

- `ServiceMonitor/ai-access-policy`;
- Service discovery labels;
- NetworkPolicy allowing only `openshift-user-workload-monitoring` to TCP/8020;
- Thanos query proof for target health and AI Access request metrics.

The product Prometheus desired configuration still includes `ai-access-policy:8020`, but the stale local projection is tracked as a CRC runtime anomaly rather than a G2 dependency.

Implementation:
- TradeOps PR #19;
- merged commit `441cb27b2d05802a84a28f2ea08d943485596ff2`;
- CI run `37642871961` SUCCESS.

G2 remains **CRC_RUNTIME_PENDING** until the shared-monitoring version of the gate returns `D090_G2_GOVERNANCE=PASS`.
