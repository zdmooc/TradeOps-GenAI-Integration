# Troubleshooting de la démo — lecture seule et frontières

| Symptôme | Premier diagnostic sans mutation | Décision |
| --- | --- | --- |
| `oc` pointe ailleurs que CRC | `oc whoami --show-server` | Stop : ne jamais changer le contexte automatiquement |
| `0/0` sur plusieurs Deployments | `bash demo/scripts/00-preflight.sh`, état PARK et replica count | PARK plausible/confirmé, pas panne déclarée |
| Snapshot `PARKED` mais replicas actifs | Comparer `.runtime/tradeops-park/LATEST` et `oc -n tradeops get deploy` | Divergence : stopper le scénario ACTIVE |
| Route présente mais HTTP 503 | `oc -n tradeops get route,svc,endpointslices,pods` | Avec PARK, EndpointSlice sans Pod est attendu |
| `Pending`, `OOMKilled` ou ancien `ContainerStatusUnknown` | `oc -n tradeops get pods -o wide` ; `oc -n tradeops get events --sort-by=.metadata.creationTimestamp` | Correlation avec état courant, timestamp et pression mémoire |
| Memory requests élevées | `oc adm top nodes` et `oc describe node crc` | Distinguer consommation instantanée et requests |
| StatefulSet présent, PVC absent | `oc -n tradeops get sts,pvc` ; lire `values-crc.yaml` | Profil `emptyDir`, aucune garantie de persistance |
| Argo CD OutOfSync | `oc get applications.argoproj.io -A` | Analyse ownership et policy ; pas de self-heal forcé |
| `CapabilityConsumption Ready=False` | `oc get capabilityconsumptions -A` | Examiner mode `Observe` / ownership ; aucun `Manage` |
| MCP/R5 absent de l'état PARK | [Résumé R5](../evidence/r5/20261008-crc-native-mcp-mq-observed-summary.md) | Preuve historique acquise, pas service courant |
| `i9_crc_verify.sh` échoue pendant PARK | Préflight et état des Deployments | Normal : cette vérification exige un stack ACTIVE |

## Commandes interdites sans démarche séparée

Ne pas lancer `oc delete`, `oc scale`, `oc apply`, `oc patch`, `oc rollout restart/undo`, `helm upgrade`, `crc delete` ou les runners G1/G2/R5 en démonstration read-only. Ne pas `oc get secret -o yaml` ni publier logs ou archives sans assainissement.

Pour le diagnostic RCA approfondi, appliquer d'abord la hiérarchie : nœud/scheduling, workloads/events, réseau/Service, politiques, StatefulSets/stockage, GitOps/Operator, puis reproduction contrôlée après accord distinct.
