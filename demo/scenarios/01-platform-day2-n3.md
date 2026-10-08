# Scénario 01 — Platform Engineering / OpenShift CaaS / Day-2 / N3

**Mode : READ_ONLY / PARK-friendly.** Durée : 3–5 min.

## Intention

Démontrer la réduction progressive du diagnostic, plutôt qu'un catalogue de commandes :

```text
ClusterVersion / ClusterOperators
 -> Node Ready / requests vs usage
 -> Namespace tradeops / quotas / LimitRange
 -> Deployment / StatefulSet / Pod / Events
 -> Route -> Service -> EndpointSlice -> Pod
 -> RBAC / SCC / NetworkPolicy
 -> OLM / GitOps / CapabilityConsumption
 -> stockage / observabilité / RCA
```

## Commandes

```bash
bash demo/scripts/00-preflight.sh
oc get clusterversion version
oc get clusteroperators
oc adm top nodes
oc -n tradeops get deployments,statefulsets,pods -o wide
oc -n tradeops get routes,services,endpointslices.discovery.k8s.io
oc -n tradeops get networkpolicy,resourcequota,limitrange
oc get applications.argoproj.io -A
oc get capabilityconsumptions -A
```

## Interprétation

Un déploiement `0/0` du snapshot PARK ne correspond pas à un incident. Présenter les pressions *requests* de la capture du 08/10 comme datées, non comme une mesure instantanée. Les StatefulSets Ready et les PVC du lab ne prouvent aucune durabilité production.

## Evidence et frontières

- [Dossier OpenShift / N3 (29 pages)](../../docs/dossiers/Dossier_TradeOps_OpenShift_CRC_Platform_Engineering_Day2_N3_20261008.pdf)
- [PARK/RESUME](../../docs/runbooks/CRC_TRADEOPS_PARK_RESUME.md).
- Pas de HA, pas de rolling upgrade, pas de chaos ni démonstration de rollback exécutée aujourd'hui.
