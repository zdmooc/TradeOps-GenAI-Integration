# I11 — Azure / ARO enterprise target

## Objective

Transpose the TradeOps architecture from the local OpenShift/RHOAI lab into an enterprise Azure target without changing the core runtime contracts.

The target remains **ARO-first**, not AKS-first:

- Azure Red Hat OpenShift for the OpenShift control plane;
- private API/ingress for the enterprise target;
- managed identities and workload identity instead of long-lived application secrets;
- Key Vault with Azure RBAC and purge protection;
- Azure Monitor / Log Analytics / Managed Prometheus integration;
- OpenTelemetry preserved end-to-end;
- Microsoft Foundry as an optional managed AI integration, not a mandatory replacement for RHOAI/vLLM;
- Terraform for low-cost foundation resources and repeatable validation;
- expensive ARO/Foundry resources created only for explicit labs.

## Reuse decision

Reference repository: `zdmooc/mayabank-azure-cloud-ai-platform` at reviewed commit `dfe3909dc6904ac502aac857eb55f8ac2a0d1309`.

Reuse:
- Landing Zone / hub-spoke principles;
- Entra / PIM / RBAC posture;
- Key Vault + managed/workload identity patterns;
- Azure Monitor / OpenTelemetry patterns;
- FinOps / GreenOps and lab-destroy discipline;
- Microsoft Foundry architectural guidance.

Adapt:
- replace the AKS runtime target with Azure Red Hat OpenShift for this program;
- keep the existing I9/I10 OpenShift/KServe/RHOAI deployment contracts;
- keep Kafka-compatible messaging semantics rather than replacing them by Azure-native messaging without a functional decision.

## Enterprise topology

```text
Users / enterprise systems
        |
Private connectivity / enterprise DNS
        |
Azure hub / firewall / routing
        |
ARO private API + private ingress
        |
OpenShift namespaces / GitOps / policies
        |
TradeOps runtime + RHOAI/KServe
   |             |             |
Key Vault     Azure Monitor   Optional Microsoft Foundry
via workload  + Managed       models/agents/tools
identity      Prometheus
```

## Identity

Cluster provisioning uses ARO managed identities. Application access to Azure services uses workload identity/federated credentials. Static client secrets are not part of the target architecture.

The versioned ARO helper uses `az aro create --enable-mi true`. It deliberately does not store credentials in Git.

## Network

The Terraform foundation defines dedicated master, worker and shared-service subnets. The enterprise target is private-by-default. Production routing, DNS forwarding, ExpressRoute/VPN, firewall policy and egress inspection belong to the landing-zone integration and must be validated in the consuming subscription.

Azure documents two ARO visibility modes for both API and ingress. `Public` is externally reachable, while `Private` requires connected networking such as peered virtual networks or other connected subnets. The enterprise architecture remains private.

### Ephemeral graduation-lab access profile

The short-lived graduation lab is a separate operational profile. It may use public API and public ingress so the cluster can be administered from the local workstation without first purchasing and operating a VPN or jump-host path.

This does **not** redefine the enterprise target. The helper defaults the lab variables to:

- `ARO_API_VISIBILITY=Public`;
- `ARO_INGRESS_VISIBILITY=Public`.

Public exposure is fail-closed: `ALLOW_PUBLIC_LAB_ACCESS=1` must be explicitly set in addition to `ALLOW_AZURE_COST=1`. A private lab remains available by setting both visibility variables to `Private`; that mode requires connected networking before it is useful from the workstation.

No sensitive or production data is allowed in the public graduation lab. Authentication, TLS, short runtime, immediate teardown, and evidence redaction remain mandatory.

## Secrets

Key Vault uses Azure RBAC, purge protection, disabled public network access and a private endpoint. A user-assigned workload identity receives the least-privilege `Key Vault Secrets User` role.

## Observability

I8 OpenTelemetry remains the application telemetry contract. The Azure target adds:

- Log Analytics for logs/queries;
- Azure Monitor Workspace for managed Prometheus integration;
- remote-write/managed-Prometheus integration for ARO when enabled;
- correlation IDs and trace context unchanged across environments.

## Microsoft Foundry

Microsoft Foundry is optional in I11. It can host selected enterprise models/agents/tools behind Entra/RBAC/network policy. It does not replace deterministic risk, I7 HITL, RHOAI serving or the governed tool boundary by default.

No Foundry resource is automatically created by the default Terraform lab because it can incur cost and quota dependencies.

## FinOps / GreenOps

Required tags include workload, environment, cost center, data classification and managed-by. The lab targets small foundation resources only. ARO and Foundry must be explicitly created and destroyed during dedicated sessions.

The ARO creation helper now applies FinOps tags to the cluster and remains cost-gated. The read-only O5 evidence collector is `scripts/o5_azure_finops_greenops_capture.sh`.

For FinOps it queries Azure Cost Management `ActualCost` at the lab resource-group scope for an explicitly supplied UTC window. The retained response is redacted before it can be committed. A provider response is evidence to review, not an automatic graduation claim; Cost Management data can be delayed.

For GreenOps it queries the Azure Carbon Optimization API available-date-range endpoint and can optionally request an `ItemDetailsReport` scoped to the lab resource group for a provider-available month. Microsoft documents Carbon Optimization emissions as previous-month data that becomes available later in the following month, so same-day ARO runtime must not be presented as same-day provider carbon evidence.

The carbon API requires appropriate Azure authorization (for example the Carbon Optimization Reader role for the intended scope). A failed or not-yet-available query remains an explicit non-proof, not a synthetic PASS.

The evidence collector intentionally records:

- a hashed subscription fingerprint instead of the raw subscription ID;
- a redacted resource-group identifier in provider payloads;
- resource inventory, ARO state and tags;
- the exact Cost Management query window;
- raw-provider-derived cost/carbon responses only after redaction;
- `full_resilience_finops_greenops_gate_claim=false` and `automatic_graduation_claim=false` until manual evidence review.

## DR and resilience

I11 documents a two-region enterprise pattern but does not claim active/active deployment. RTO/RPO remain business inputs. Cluster/data recovery, DNS failover and multi-region state replication require measured exercises before being marked VERIFIED.

## Explicit non-claims

I11 does not claim:

- an Azure subscription apply;
- a running ARO cluster;
- private DNS/ExpressRoute/firewall validation;
- live Key Vault workload-identity access;
- Azure Monitor ingestion from a real cluster;
- a Microsoft Foundry deployment;
- measured Azure cost, carbon or DR results unless corresponding live evidence is retained and reviewed;
- automated real-money execution.
