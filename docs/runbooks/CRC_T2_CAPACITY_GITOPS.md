# D-090 T2 — CRC capacity and OpenShift GitOps gate

Status: **IMPLEMENTED / CI-VALIDATION TARGETED / LIVE CRC EVIDENCE PENDING**

T2 is the read-only gate executed after the normal TradeOps PARK. Its purpose is to verify that the released capacity is sufficient to remove scheduler pressure and that the OpenShift GitOps control plane is healthy before D-090 G1/G2 live evidence.

## Preconditions

1. T1 PARK/RESUME implementation is present on `main`.
2. TradeOps is currently parked with:

```text
TRADEOPS_PARK=PASS
```

3. The active PARK snapshot contains the structured cluster snapshots written by `scripts/crc/suspend-tradeops.sh`.
4. OpenShift GitOps is installed in `openshift-gitops` unless `TRADEOPS_GITOPS_NAMESPACE` explicitly selects another namespace.

## Execute

```bash
cd /c/workspaces/TradeOps-GenAI-Integration
git pull --ff-only

bash scripts/crc/t2-capacity-gitops-evidence.sh
```

The script is read-only. It does not scale, patch or delete cluster resources.

## Evidence captured

The T2 bundle is stored below the active PARK snapshot:

```text
.runtime/tradeops-park/<park timestamp>/t2-<UTC timestamp>/
```

It records:

- all current pods and nodes as JSON;
- current Pending pods;
- current FailedScheduling events;
- OpenShift GitOps pods/workloads;
- all Argo CD Applications;
- ClusterOperators;
- best-effort `oc adm top` node and TradeOps pod metrics;
- normalized capacity summaries for:
  - before PARK;
  - immediately after PARK;
  - current state;
- before/after/current request deltas.

## Capacity semantics

`scripts/crc/k8s_capacity_summary.py` computes effective pod requests from regular containers, the maximum init-container request and pod overhead. Completed/failed pods are excluded from active scheduler demand.

The gate distinguishes generic Pending pods from scheduler pressure. T2 fails only when an unscheduled pod reports:

```text
Insufficient memory
```

or:

```text
Insufficient cpu
```

A Pending pod caused by an image pull or another non-capacity fault remains visible in the evidence but does not falsely classify the cluster as capacity constrained.

## GitOps gate

T2 requires:

- at least one active pod in the OpenShift GitOps namespace;
- every active GitOps pod to be Running with all reported containers Ready;
- Argo CD Application CRD present;
- all OpenShift ClusterOperators Available=True, Degraded!=True and Progressing!=True.

The Applications are captured for inspection, but a deliberately parked TradeOps Application may be OutOfSync and is therefore not itself used as the health gate.

## Expected success markers

```text
T2_CAPACITY_EVIDENCE_CAPTURED=PASS
T2_SCHEDULER_CAPACITY_GATE=PASS
T2_GITOPS_CORE=PASS
T2_CLUSTEROPERATORS_HEALTH=PASS
T2_CAPACITY_GITOPS_GATE=PASS
```

The script also prints capacity markers including current Pending pods, unscheduled memory requests, scheduler memory-pressure pod count and scheduled-memory deltas.

## Claim boundary

CI can validate the parser, quantity conversions, script syntax and the fact that T2 is read-only.

Only observed execution on the workstation may promote:

```text
D090_T2_CRC_CAPACITY_GITOPS_RUNTIME_PROVEN
```

Until that execution, the correct state is:

```text
D090_T2_CAPACITY_GITOPS_IMPLEMENTED_AND_CI_VALIDATED
```

T2 does not prove D-090 G1 or G2. Its successful runtime execution only authorizes the next live probe.
