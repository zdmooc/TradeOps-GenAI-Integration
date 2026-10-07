# D-090 G2 — CRC live governance from PARK

Status: **IMPLEMENTED / CI VALIDATION TARGETED / CRC LIVE EVIDENCE PENDING**

G2 proves the governance controls that remain after G1 established the full governed real-model path.

## Scope

The bounded G2 gate proves on the single-node CRC lab:

- workload OIDC token acquisition;
- server-derived consumer identity `tradeops`;
- allowed model success;
- forbidden model denial;
- live per-consumer RPM quota denial;
- live budget denial after measured provider usage;
- AI Access Prometheus counters;
- shared OpenShift user-workload Prometheus target health and Thanos PromQL query;
- a real `genai-api /review` call through `ObservedLLM`;
- Shared OTel trace reception during that real application call;
- policy-secret restoration;
- automatic re-PARK.

The in-memory quota/budget store remains lab-only and single replica. G2 does not claim a distributed production quota service.

## Preconditions

G1 must already be runtime-proven and TradeOps must still be PARKED.

The sibling API Management checkout must exist:

```text
../mayabank-api-management-architecture
```

The default local model profile is:

```text
ollama/qwen2.5:3b
http://192.168.56.1:11434
```

## Execute

```bash
cd /c/workspaces/mayabank-api-management-architecture
git switch main
git pull --ff-only origin main

cd /c/workspaces/TradeOps-GenAI-Integration
git switch main
git pull --ff-only origin main

export D090_LITELLM_API_BASE='http://192.168.56.1:11434'

bash scripts/crc/d090-g2-live-governance-from-park.sh
```

Do not resume the full TradeOps product first.

## Bounded runtime window

Only these TradeOps Deployments are temporarily activated:

```text
ai-access-policy
genai-api
litellm
```

PostgreSQL, Redpanda and Qdrant remain at their existing StatefulSet replica counts. Prometheus remains running and is **not restarted**, because its CRC TSDB uses `emptyDir`.

At exit, the wrapper scales the three temporary Deployments back to zero.

## Policy variants

The wrapper snapshots the original `AI_ACCESS_CONSUMERS_JSON` Secret value before any mutation.

It exercises three sequential policy variants:

1. **baseline** — original policy, real success + forbidden `odm-extraction` for TradeOps;
2. **quota** — `rpm=1`, first real request succeeds, second request must return `QUOTA_EXCEEDED`;
3. **budget** — high lab token rates + tiny budget, first real request records spend, second request must return `BUDGET_EXCEEDED`.

The original Secret value is restored even on failure.

## Prometheus proof

The repository still declares `ai-access-policy:8020` in the product Prometheus desired configuration.

Three CRC attempts showed that the **already-running product Prometheus pod** can keep a stale ConfigMap projection even while the API ConfigMap already contains the new target. Because that pod stores its TSDB on `emptyDir`, G2 deliberately stops trying to mutate/restart it just to prove a scrape.

The runtime gate now consumes the same shared OpenShift observability plane already proven by the ODM workload:

- `ServiceMonitor/ai-access-policy` in namespace `tradeops`;
- a NetworkPolicy allowing only `openshift-user-workload-monitoring` to reach TCP/8020;
- the cluster `thanos-querier` route for runtime PromQL evidence.

The AI Access CRC manifest carries those monitoring resources, and the G2 wrapper requires:

```text
D090_G2_SHARED_PROMETHEUS_INTENT=PASS
D090_G2_PROMETHEUS_TARGET=PASS source=openshift-user-workload-monitoring
D090_G2_PROMETHEUS_QUERY=PASS source=thanos
D090_G2_SHARED_PROMETHEUS=PASS
```

The gate waits up to 180 seconds for both the AI Access target to report `up == 1` and:

```promql
mayabank_ai_access_requests_total{consumer="tradeops",status="ok"}
```

to become greater than zero.

This proves live Prometheus scrape/query without mutating or restarting the product Prometheus pod. The stale local projection remains a CRC runtime anomaly and is no longer a G2 dependency.

## Shared OTel proof

The G1 evidence probe intentionally called the gateway directly and therefore did not create the application `llm.complete` span.

G2 calls the actual:

```text
genai-api POST /review
```

endpoint. That path uses `ObservedLLM`, which emits `llm.complete` and attributes for requested model, executed provider/model, consumer, tokens, token source and estimated cost.

The Shared OTel collector must receive traces during that exact window:

```text
D090_G2_SHARED_OTEL_TRACE=PASS
```

The live collector receipt and the CI-validated span attribute contract together form the G2 telemetry evidence.

## Expected final markers

```text
D090_G2_AUTH_MATERIAL_REFRESH=PASS
D090_G2_WINDOW_BASE_ACTIVE=PASS
D090_G2_WINDOW_ACTIVE=PASS
D090_G2_AUTH_CHAIN=PASS
D090_G2_SHARED_PROMETHEUS_INTENT=PASS
D090_G2_SUCCESS=PASS consumer=tradeops
D090_G2_MODEL_DENIED=PASS http=403
D090_G2_BASELINE=PASS
D090_G2_BASELINE_METRICS=PASS
D090_G2_GENAI_REVIEW=PASS
D090_G2_SHARED_OTEL_TRACE=PASS
D090_G2_PROMETHEUS_TARGET=PASS
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

## Evidence bundle

The local bundle is written under the active PARK snapshot:

```text
.runtime/tradeops-park/<park timestamp>/g2-<UTC timestamp>/
```

No token or client secret is written to the bundle.

## Claim boundary

Only a successful CRC run may promote:

```text
D090_G2_CRC_RUNTIME_PROVEN
D090_G2_VERIFIED_SINGLE_CONSUMER
```

It does not promote G3/G4 multi-consumer claims or production quota/HA claims.
