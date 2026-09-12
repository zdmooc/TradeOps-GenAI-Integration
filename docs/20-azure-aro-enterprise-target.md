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

The versioned ARO helper uses `az aro create --enable-mi true` and private API/ingress. It deliberately does not store credentials in Git.

## Network

The Terraform foundation defines dedicated master, worker and shared-service subnets. The enterprise target is private-by-default. Production routing, DNS forwarding, ExpressRoute/VPN, firewall policy and egress inspection belong to the landing-zone integration and must be validated in the consuming subscription.

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
- measured Azure cost, carbon or DR results;
- automated real-money execution.
