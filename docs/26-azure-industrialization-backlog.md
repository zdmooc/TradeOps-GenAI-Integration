# O5 — Azure industrialization backlog

## Purpose

Industrialize the existing Azure/ARO target **without changing the initial architecture**. The target remains GitHub + GitHub Actions + Terraform + Azure Red Hat OpenShift + OpenShift GitOps/Argo CD + Helm/Kustomize + TradeOps/RHOAI.

This backlog converts the remaining manual Azure steps into a reproducible, cost-controlled enterprise delivery path before the first paid ARO deployment.

## Current verified state — 2026-09-12

- Azure subscription is enabled.
- Target region: `francecentral`.
- Azure CLI observed locally: `2.62.0`; managed-identity ARO workflow requires upgrade before deployment.
- `Microsoft.RedHatOpenShift` observed as `NotRegistered`.
- ARO versions observed in France Central: `4.18.26`, `4.18.34`, `4.19.20`, `4.19.24`, `4.20.15`, `4.21.22`.
- RHOAI 3.4 target: OpenShift 4.19-4.20; selected lab baseline: **ARO 4.20.15**.
- Current regional vCPU quota observed: **10**.
- Current `Standard DSv5 Family vCPUs` quota observed: **0**.
- No paid ARO resource has been created yet.

## Sizing baseline

### First graduation lab

| Component | Count | SKU | Per node | Aggregate |
|---|---:|---|---|---|
| ARO control plane | 3 | `Standard_D8s_v5` | 8 vCPU / 32 GiB | 24 vCPU / 96 GiB |
| ARO workers | 3 | `Standard_D8s_v5` | 8 vCPU / 32 GiB | 24 vCPU / 96 GiB |
| Steady-state nodes | 6 | D8s_v5 | — | **48 vCPU / 192 GiB** |

RHOAI 3.4 requires at least two workers with 8 CPU / 32 GiB each. The planned worker tier provides 3 × 8 vCPU / 32 GiB = **24 vCPU / 96 GiB** before application consumption.

### Quota target

Microsoft documents an ARO cluster minimum of 44 cores in the generic configuration and a higher requirement when using three D8sv5 workers. For this lab, do not request the bare minimum. Target:

- **Regional vCPU quota >= 64** in France Central;
- **DSv5 family quota >= 64** in France Central;
- final creation remains blocked until `az aro validate` succeeds.

The 64-vCPU target gives headroom for bootstrap/installation behavior and avoids building a lab against an exact quota ceiling.

## Cost model

### Pricing snapshot — 2026-09-12

This is a planning snapshot, **not a contractual price**. Refresh pricing immediately before every paid `apply` / ARO creation using the Azure calculator or Retail Prices API and retain the result as evidence.

Current public references used for planning:

- `Standard_D8s_v5`, France Central, Linux pay-as-you-go compute: approximately **USD 0.448/hour per VM**;
- ARO OpenShift worker fee for D8s_v5: **USD 0.342/hour per worker**;
- control-plane OpenShift licensing is included in the control-plane pricing model; worker nodes carry the additional OpenShift fee.

Baseline subtotal for 3 masters + 3 workers:

| Cost item | Formula | Approx. USD/hour |
|---|---:|---:|
| 3 master VMs | 3 × 0.448 | 1.344 |
| 3 worker VM compute | 3 × 0.448 | 1.344 |
| 3 worker OpenShift fees | 3 × 0.342 | 1.026 |
| **ARO node subtotal** | — | **3.714/h** |

Indicative runtime subtotal, before disks/network/logging/private endpoints/monitoring:

| Runtime | Approx. subtotal |
|---:|---:|
| 4 h | USD 14.86 |
| 6 h | USD 22.28 |
| 8 h | USD 29.71 |
| 12 h | USD 44.57 |
| 24 h | USD 89.14 |

### Lab budget policy

- Personal learning budget objective: **EUR 50/month maximum**.
- First ARO lab hard runtime target: **<= 8 hours**.
- Pre-deployment refreshed estimate must leave a safety margin for storage, networking, Log Analytics/Monitor, Key Vault/private endpoint and Terraform state storage.
- Do not start the paid lab if the refreshed all-in estimate approaches the monthly EUR 50 ceiling.
- Cost Management `ActualCost` after the run is the source for measured provider cost; an estimate is never relabeled as measured cost.

### Costs that must be included before approval

- 6 ARO VMs and worker OpenShift fees;
- managed disks;
- load balancer/public IP/network traffic if applicable;
- Log Analytics ingestion and retention;
- Azure Monitor / managed Prometheus if enabled;
- Key Vault and Private Endpoint;
- Private DNS where billed;
- Terraform remote-state Storage Account;
- backup/snapshot resources if introduced;
- egress and any inter-zone/inter-region traffic;
- optional AI/GPU resources only if explicitly approved.

## Industrialization backlog

| ID | Priority | Status | Work item | Definition of Done |
|---|---|---|---|---|
| AZ-01 | P0 | TODO | Upgrade Azure CLI | Local CLI supports managed-identity ARO workflow; version is captured in evidence. |
| AZ-02 | P0 | TODO | Register Azure providers | `Microsoft.RedHatOpenShift`, `Microsoft.Compute`, `Microsoft.Storage`, `Microsoft.Authorization` verified `Registered`. |
| AZ-03 | P0 | BLOCKED_QUOTA | Obtain France Central quota | Regional and DSv5 quota meet target; `az aro validate` succeeds. |
| AZ-04 | P0 | TODO | Freeze supported ARO/RHOAI versions | ARO version available in region and RHOAI support matrix checked immediately before deployment. Current baseline: ARO 4.20.15 / RHOAI 3.4. |
| AZ-05 | P0 | TODO | Terraform remote state | Azure Storage backend, state locking/concurrency strategy, separate bootstrap, no local authoritative state. |
| AZ-06 | P0 | TODO | GitHub → Azure OIDC | Federated identity configured; GitHub Actions uses OIDC; no long-lived Azure client secret stored in GitHub. |
| AZ-07 | P0 | TODO | Least-privilege IAM/RBAC | Deployment identity roles documented and scoped; workload identity and Key Vault access verified. |
| AZ-08 | P0 | TODO | Terraform FinOps controls | Mandatory tags, `expiry`/TTL tag, lab budget/alerts, conservative log retention and allowed-size guardrails. |
| AZ-09 | P0 | TODO | Live cost estimation gate | Pipeline produces timestamped region/SKU/runtime/all-in estimate before paid apply. Approval is blocked if estimate violates budget policy. |
| AZ-10 | P0 | TODO | `azure-create.yml` | Manual `workflow_dispatch`; CI checks; OIDC login; Terraform init/validate/plan; approval; apply foundation; ARO preflight/create; retained evidence. |
| AZ-11 | P0 | TODO | ARO provisioning contract | Creation remains explicit and cost-gated; managed identity enabled; selected API/ingress visibility recorded; no sensitive data in public lab profile. |
| AZ-12 | P0 | TODO | OpenShift GitOps bootstrap | Install/validate OpenShift GitOps/Argo CD, then let Git reconcile TradeOps platform/runtime manifests. |
| AZ-13 | P0 | TODO | RHOAI deployment/verification | Install supported RHOAI; verify minimum worker capacity, default StorageClass, operator health and required serving path. |
| AZ-14 | P0 | TODO | Runtime evidence | Capture cluster health, node sizing, namespaces, GitOps sync, workload identity, monitoring and application probes. |
| AZ-15 | P0 | TODO | FinOps/GreenOps capture | Run `o5_azure_finops_greenops_capture.sh`; retain redacted resource inventory, Cost Management query and provider carbon availability/result when available. |
| AZ-16 | P0 | TODO | `azure-destroy.yml` | Capture final evidence/cost first; delete ARO; verify absence; `terraform plan -destroy`; approval; destroy foundation; verify no billable resources remain. |
| AZ-17 | P0 | TODO | TTL / auto-destroy safety net | Scheduled GitHub Action checks `expiry`; expired lab triggers controlled destroy path or a fail-closed escalation. Manual destroy remains available. |
| AZ-18 | P0 | TODO | Destroy verification | Query resource group/resources after destroy; document Key Vault soft-delete/purge-protection behavior separately. |
| AZ-19 | P1 | TODO | Cost variance report | Compare estimated vs Azure `ActualCost`; explain variance by compute/licence/storage/network/logs. |
| AZ-20 | P1 | TODO | Rightsizing review | Compare actual CPU/RAM usage against D8s_v5 baseline; document whether smaller/larger workers are acceptable without violating RHOAI requirements. |
| AZ-21 | P1 | TODO | Environment promotion model | Define lab/dev/preprod/prod GitOps promotion and approvals; not required to run four paid environments for graduation. |
| AZ-22 | P2 | DEFERRED | Ansible Automation Platform | Add only for Day-2/runbooks/external middleware/legacy operations where GitOps/Operators/Terraform are not the right control plane. Do not use Ansible as primary Azure IaC. |

## CREATE pipeline target

```text
workflow_dispatch
  -> CI/security/SBOM/tests
  -> Azure OIDC login
  -> quota/provider/version preflight
  -> refreshed cost estimate
  -> terraform init/plan
  -> human approval
  -> terraform apply foundation
  -> az aro validate/create
  -> OpenShift GitOps bootstrap
  -> Argo CD sync
  -> RHOAI + TradeOps verification
  -> FinOps evidence
```

No paid step may run merely because code was pushed to `main`.

## DESTROY pipeline target

```text
workflow_dispatch OR TTL expiry
  -> capture resource inventory
  -> capture cost window / evidence
  -> delete ARO
  -> verify ARO absent
  -> terraform plan -destroy
  -> protected approval for foundation destroy
  -> terraform apply destroy plan
  -> verify resource group / residual resources
  -> record final cost and residual soft-deleted resources
```

Destroy must be **idempotent**: rerunning it after partial cleanup must safely converge toward zero billable lab resources.

## GitOps boundary

Industrialization does not replace the initial architecture:

- **GitHub Actions**: CI, infrastructure orchestration, approvals, evidence and lifecycle pipelines;
- **Terraform**: Azure infrastructure lifecycle and declarative IAM/resource configuration where supported;
- **Azure CLI / ARO APIs**: ARO lifecycle where retained as an explicit helper contract;
- **Argo CD / OpenShift GitOps**: OpenShift desired state and application/platform reconciliation;
- **Helm/Kustomize/Operators**: Kubernetes/OpenShift packaging and platform operators;
- **Ansible**: optional Day-2 automation, not the primary source of truth for Azure or OpenShift workloads.

## Go / no-go gate before first paid deployment

All of the following must be true:

1. Azure CLI compatible with the chosen ARO managed-identity workflow.
2. Required providers registered.
3. France Central quota sufficient and `az aro validate` passes.
4. ARO version is still offered and is supported by the selected RHOAI version.
5. GitHub OIDC is working without a stored Azure client secret.
6. Terraform remote state is operational.
7. `terraform plan` is retained and reviewed.
8. Current pricing is refreshed and the all-in estimate fits the lab budget with margin.
9. CREATE and DESTROY workflows are both present and tested in non-paid/dry-run paths.
10. TTL/hard-stop time is defined before CREATE.
11. Explicit user approval is given for the paid run.

Until all eleven conditions are satisfied, `OPENSHIFT_AZURE_DEPLOYMENT` remains blocked and no paid Azure creation is justified.
