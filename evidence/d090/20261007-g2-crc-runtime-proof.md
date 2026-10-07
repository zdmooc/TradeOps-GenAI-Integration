# D-090 G2 full live-governance CRC runtime proof — 2026-10-07

Status: **CRC_RUNTIME_PROVEN / VERIFIED × SINGLE_CONSUMER GOVERNANCE**

Environment: OpenShift Local / CRC single-node lab.

## Acceptance markers

```text
D090_G2_AUTH_MATERIAL_REFRESH=PASS
D090_G2_WINDOW_BASE_ACTIVE=PASS
D090_G2_WINDOW_ACTIVE=PASS
D090_G2_AUTH_CHAIN=PASS
D090_G2_SHARED_PROMETHEUS_INTENT=PASS

D090_G2_OIDC_TOKEN=PASS
D090_G2_SUCCESS=PASS consumer=tradeops provider=litellm
D090_G2_MODEL_DENIED=PASS http=403
D090_G2_BASELINE=PASS
D090_G2_BASELINE_METRICS=PASS

D090_G2_GENAI_REVIEW=PASS
D090_G2_SHARED_OTEL_TRACE=PASS

D090_G2_PROMETHEUS_TARGET=PASS source=openshift-user-workload-monitoring
D090_G2_PROMETHEUS_QUERY=PASS source=thanos
D090_G2_SHARED_PROMETHEUS=PASS

D090_G2_QUOTA_EXCEEDED=PASS http=429
D090_G2_QUOTA=PASS
D090_G2_QUOTA_METRICS=PASS

D090_G2_BUDGET_EXCEEDED=PASS http=429
D090_G2_BUDGET=PASS
D090_G2_COST_METRIC=PASS

D090_G2_POLICY_RESTORE=PASS
D090_G2_GOVERNANCE=PASS
D090_G2_WINDOW_REPARK=PASS
```

Local evidence bundle:

```text
.runtime/tradeops-park/20261007T103947Z/g2-20261007T161929Z
```

## Proven controls

The live CRC gate proves, for the TradeOps consumer:
- OIDC workload token acquisition and server-derived identity;
- allowed real-model request through the governed gateway;
- model allowlist denial;
- live per-consumer RPM quota denial;
- live budget denial after measured provider usage;
- AI Access request/token/cost/denial metrics;
- real `genai-api /review` path through `ObservedLLM`;
- Shared OTel trace receipt;
- OpenShift user-workload Prometheus scrape;
- Thanos PromQL query of AI Access metrics;
- restoration of the original consumer policy Secret;
- automatic re-PARK of the temporary G2 window.

## Observability decision

The product Prometheus desired state still includes `ai-access-policy:8020`, but the already-running CRC product Prometheus pod retained stale projected ConfigMap content across three attempts.

G2 therefore uses the shared OpenShift user-workload monitoring plane for runtime acceptance:
- `ServiceMonitor/ai-access-policy`;
- narrow monitoring ingress from `openshift-user-workload-monitoring`;
- `thanos-querier` for runtime PromQL.

This is consistent with the shared monitoring capability already exercised by the ODM workload and avoids restarting the product Prometheus pod with its `emptyDir` TSDB.

## Claim boundary

Allowed:

```text
D090_G2_CRC_RUNTIME_PROVEN
D090_G2_VERIFIED_SINGLE_CONSUMER_GOVERNANCE
```

Not implied:
- distributed/HA quota or budget storage;
- multi-consumer isolation;
- ODM second-consumer live proof;
- production readiness.

Next canonical gate:

```text
D-093 I6 TradeOps Observe
```
