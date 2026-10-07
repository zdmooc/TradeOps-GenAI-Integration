# D-090 T1/T2 CRC runtime evidence — 2026-10-07

Status: **T1 CRC_RUNTIME_PROVEN / T2 CRC_RUNTIME_PROVEN**

Scope: single-node OpenShift Local / CRC workstation. This evidence does not imply HA or production readiness.

## T1 — TradeOps PARK

Observed markers:

```text
TRADEOPS_PARK=PASS
TRADEOPS_PARK_MODE=normal
TRADEOPS_STATEFULSETS_PRESERVED=PASS
TRADEOPS_PROMETHEUS_PRESERVED=PASS
```

The active PARK snapshot is:

```text
/c/workspaces/TradeOps-GenAI-Integration/.runtime/tradeops-park/20261007T103947Z
```

Fourteen stateless Deployments were scaled from 1 to 0:

```text
agent-controller
ai-access-policy
genai-api
grafana
litellm
market-data
mcp-server
notifier
otel-collector
paper-oms
rag-api
risk-engine
tradeops-ui
workflow-api
```

Stateful workload desired replicas were preserved and Prometheus remained running in normal PARK mode.

## T2 — capacity / GitOps gate

The corrected T2 gate was executed twice against the same PARK snapshot and passed both times.

Observed capacity markers:

```text
T2_BEFORE_ACTIVE_PODS=163
T2_AFTER_PARK_ACTIVE_PODS=150
T2_CURRENT_ACTIVE_PODS=148
T2_BEFORE_PENDING_PODS=3
T2_AFTER_PARK_PENDING_PODS=0
T2_CURRENT_PENDING_PODS=0
T2_BEFORE_UNSCHEDULED_MEMORY_MIB=1792
T2_AFTER_PARK_UNSCHEDULED_MEMORY_MIB=0
T2_CURRENT_UNSCHEDULED_MEMORY_MIB=0
T2_BEFORE_SCHEDULED_MEMORY_MIB=23323
T2_AFTER_PARK_SCHEDULED_MEMORY_MIB=23171
T2_CURRENT_SCHEDULED_MEMORY_MIB=23139
T2_CURRENT_MEMORY_PRESSURE_PODS=0
T2_CURRENT_CPU_PRESSURE_PODS=0
T2_IMMEDIATE_SCHEDULED_MEMORY_DELTA_MIB=-152
T2_CURRENT_SCHEDULED_MEMORY_DELTA_MIB=-184
```

Observed GitOps/OpenShift markers:

```text
T2_GITOPS_READY_PODS=8
T2_GITOPS_TERMINAL_PODS_IGNORED=3
T2_GITOPS_TERMINAL_PODS=cluster-894577c9f-hqw8x:Failed,gitops-plugin-59c99f455b-8zk6v:Failed,openshift-gitops-redis-6fbcf59479-zjmhk:Failed
T2_GITOPS_WORKLOAD_CONTROLLERS=PASS
T2_CLUSTEROPERATORS_HEALTH=PASS
T2_CAPACITY_EVIDENCE_CAPTURED=PASS
T2_SCHEDULER_CAPACITY_GATE=PASS
T2_GITOPS_CORE=PASS
T2_CAPACITY_GITOPS_GATE=PASS
```

Second successful evidence bundle:

```text
/c/workspaces/TradeOps-GenAI-Integration/.runtime/tradeops-park/20261007T103947Z/t2-20261007T110147Z
```

## Terminal GitOps pod interpretation

The first T2 implementation treated historical terminal `Failed` pods as active readiness failures. PR #9 corrected the gate so `Succeeded` and `Failed` pods are treated as terminal history while current Deployment and StatefulSet controller readiness remains mandatory.

Correction:

- commit `39095063b4a3cd60d35a4854f5d0a2ecb9ce1365`;
- CI run `37609405957`: SUCCESS.

The corrected runtime gate then passed twice.

## Claim boundary

Allowed:

```text
TRADEOPS_CRC_PARK_RUNTIME_PROVEN
D090_T2_CRC_CAPACITY_GITOPS_RUNTIME_PROVEN
```

Not implied:

- OpenShift HA;
- multi-node resilience;
- production SLO;
- G1 real-model governed-path proof;
- G2 live governance proof.

Next gate:

```text
D-090 G1 full governed live
TradeOps genai-api
 -> Shared Keycloak
 -> canonical Kong
 -> AI Access
 -> LiteLLM
 -> Ollama/qwen2.5:3b
```
