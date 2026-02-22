# OpenShift / Kubernetes

Le chart Helm minimal est dans `infra/helm/tradeops/`.
Objectif : fournir un point de départ pour déployer les APIs.

Pour un déploiement “prod-like” :
- ajouter Deployments pour workers (signal/risk/oms/notifier)
- ajouter Postgres managé (ou StatefulSet) + Secret + PVC
- ajouter Redpanda/Kafka managé (ou operator)
- ajouter Ingress/Route + TLS
- ajouter NetworkPolicies + RBAC + PodSecurity
- intégrer Argo CD (voir `gitops/argocd/application.yaml`)
