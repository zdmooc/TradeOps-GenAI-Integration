# CRC TradeOps PARK / RESUME runbook

Status: **IMPLEMENTED / CI-VALIDATION TARGETED / LIVE CRC EVIDENCE PENDING**

This runbook provides a bounded way to release CPU and memory on the single-node OpenShift Local / CRC workstation without deleting the TradeOps namespace or intentionally destroying the stateful stores.

## Safety boundary

The normal PARK operation:

- snapshots the exact desired replica count of every Deployment;
- never scales any StatefulSet;
- keeps the `prometheus` Deployment at its current replica count;
- scales only eligible Deployments to zero;
- fails closed when an automated Argo CD Application targets the `tradeops` namespace;
- fails closed when an HPA targets a Deployment selected for PARK;
- fails closed when an active CronJob could create new pods;
- records before/after workload and best-effort metrics evidence;
- rolls back already-scaled Deployments if the PARK operation fails part-way through.

The RESUME operation:

- restores the exact Deployment replica counts from the PARK snapshot;
- refuses to proceed if the Deployment set changed while parked;
- refuses to proceed if any StatefulSet desired replica count drifted;
- fails closed if a new HPA now controls one of the snapshotted Deployments;
- rolls back to the pre-resume replica state if a restore fails part-way through;
- can optionally execute the complete existing `i9_crc_verify.sh` smoke gate.

## Why StatefulSets must stay running on CRC

`infra/helm/tradeops/values-crc.yaml` sets:

```yaml
crc:
  ephemeralPlatformStorage: true
```

In that CRC profile:

- PostgreSQL uses `emptyDir` for `/var/lib/postgresql/data`;
- Redpanda uses `emptyDir` for `/var/lib/redpanda/data`;
- Qdrant uses `/tmp/qdrant-storage` and `/tmp/qdrant-snapshots`.

Scaling those StatefulSets to zero can delete their current pods and therefore lose the local lab data. The PARK scripts intentionally do not offer a switch that scales them down.

## Why Prometheus stays running in normal mode

The TradeOps Prometheus Deployment also uses an `emptyDir` TSDB. Normal PARK therefore keeps its current desired replica count.

A deep PARK may scale Prometheus with the other Deployments only when the caller explicitly accepts this loss:

```bash
export TRADEOPS_PARK_MODE=deep
export TRADEOPS_DEEP_PARK_CONFIRM_TSDB_LOSS=yes
bash scripts/crc/suspend-tradeops.sh
```

Deep PARK still never scales PostgreSQL, Redpanda or Qdrant.

## Preflight

Use the CRC context that owns the TradeOps runtime.

```bash
oc whoami
oc get clusterversion
oc get nodes
oc -n tradeops get deployment,statefulset,pods
oc get applications.argoproj.io -A
```

Do not disable the Argo CD guard by editing the scripts. If an automated Application targets `tradeops`, suspend that reconciliation using the approved GitOps owner procedure first. The goal is to avoid a scale-to-zero / self-heal loop.

## Normal PARK

```bash
cd /c/workspaces/TradeOps-GenAI-Integration
git pull --ff-only

bash scripts/crc/suspend-tradeops.sh
```

Expected final markers:

```text
TRADEOPS_PARK=PASS
TRADEOPS_PARK_MODE=normal
TRADEOPS_STATEFULSETS_PRESERVED=PASS
TRADEOPS_PROMETHEUS_PRESERVED=PASS
```

The local snapshot is stored under:

```text
.runtime/tradeops-park/<UTC timestamp>/
```

and `.runtime/tradeops-park/LATEST` points to the active snapshot.

A second PARK while that snapshot is still marked `PARKED` is a no-op and emits:

```text
TRADEOPS_PARK_ALREADY_ACTIVE=PASS
```

## Capacity observation while parked

Capture the cluster state before starting the next runtime gate:

```bash
oc get pods -A --field-selector=status.phase=Pending -o wide
oc -n tradeops get deployment,statefulset,pods -o wide
oc adm top node
oc adm top pods -n tradeops
```

The PARK script already stores best-effort before/after evidence in its snapshot. These observations are used by the separate capacity/GitOps iteration; they do not by themselves promote a D-090 runtime claim.

## RESUME

By default RESUME uses the active `LATEST` PARK snapshot:

```bash
bash scripts/crc/resume-tradeops.sh
```

Expected final markers:

```text
TRADEOPS_RESUME=PASS
TRADEOPS_REPLICA_RESTORE=EXACT
TRADEOPS_STATEFULSETS_PRESERVED=PASS
```

To force a specific snapshot:

```bash
export TRADEOPS_PARK_SNAPSHOT="/absolute/path/to/.runtime/tradeops-park/<timestamp>"
bash scripts/crc/resume-tradeops.sh
```

To add the full existing TradeOps runtime verification after all Deployment rollouts:

```bash
TRADEOPS_RESUME_FULL_VERIFY=yes bash scripts/crc/resume-tradeops.sh
```

A second RESUME against a snapshot already marked `RESUMED` is a no-op.

## Failure handling

PARK and RESUME are fail-closed around ownership/autoscaling drift. Do not bypass a failure until its cause is understood.

Important examples:

- **automated Argo CD Application found**: pause the owning reconciliation first; do not fight self-heal;
- **HPA found**: reconcile autoscaling ownership before PARK/RESUME;
- **active CronJob found**: suspend it through the owning configuration before PARK;
- **Deployment set changed while parked**: refresh the runtime inventory rather than restoring an obsolete snapshot;
- **StatefulSet desired replica drift**: investigate before restoring Deployments.

Neither script deletes Namespace, PVC, Secret, ConfigMap, Route or NetworkPolicy resources. Neither script regenerates credentials. Neither script performs a global prune.

## Evidence and claim boundary

Repository/CI validation can prove the PARK/RESUME implementation and its safety invariants.

Only an observed CRC execution can promote a runtime claim such as:

```text
TRADEOPS_CRC_PARK_RESUME_RUNTIME_PROVEN
```

Until then the correct claim is:

```text
TRADEOPS_CRC_PARK_RESUME_IMPLEMENTED_AND_CI_VALIDATED
```

CRC remains a single-node local OpenShift proof. It is not an HA or production-runtime claim.
