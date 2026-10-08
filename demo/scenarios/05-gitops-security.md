# Scénario 05 — GitOps / sécurité / observabilité / Shared Platform

**Mode : READ_ONLY / PARK-friendly.** Durée : 3 min.

## Chaîne de gouvernance

```text
Git desired state -> Argo CD -> API Kubernetes -> workloads
Namespace / SA / RBAC / SCC / NetworkPolicy / Quotas
Shared Platform Operator -> CapabilityConsumption tradeops-crc (Observe)
Metrics / Traces -> diagnostic et remediation gouvernée
```

## Commandes de présentation

```bash
oc -n openshift-gitops get pods
oc get applications.argoproj.io -A
oc -n tradeops get networkpolicy,serviceaccount,role,rolebinding
oc get capabilityconsumptions -A
oc -n shared-platform-services get deployment,pods
oc adm top nodes
```

**Distinguer** présence d'Argo CD et preuve de réconciliation du produit, santé d'un Operator et Ready d'une CR, Event Warning historique et anomalie courante. La capture `tradeops-crc` en `Observe` ne permet pas de `Manage` sans instruction explicite et arbitrage brownfield.

## Evidence et limites

- [Runbook Shared — méthode CaaS N3](https://github.com/zdmooc/shared-platform-services-openshift/blob/main/docs/runbooks/OPENSHIFT_CAAS_DAY2_N3_DEMO.md)
- [Evidence G2 — OTel + OpenShift monitoring](../../evidence/d090/20261007-g2-crc-runtime-proof.md)
- [Dossier OpenShift](../../docs/dossiers/README.md)

Pas de drift provoqué, d'auto-sync forcé, de modification RBAC/NetworkPolicy ou d'enforcement Supply Chain revendiqué sans preuve dédiée.
