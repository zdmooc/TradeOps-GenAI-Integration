# Dossiers d'architecture et de diagnostic — TradeOps CRC (08/10/2026)

Ces deux dossiers PDF reprennent la méthode de démonstration et de preuve utilisée dans les références `shared-platform-services-openshift` (CaaS / Platform Engineering / Day-2 / N3) et `enterprise-data-lakehouse-kubernetes-openshift` (architecture fonctionnelle / runtime).

## Livrables

| PDF | Portée | SHA-256 |
| --- | --- | --- |
| [Dossier TradeOps OpenShift CRC — Platform Engineering / Day-2 / N3](Dossier_TradeOps_OpenShift_CRC_Platform_Engineering_Day2_N3_20261008.pdf) | 29 pages ; lecture du cluster, capacité, PARK, workloads, réseau, sécurité, GitOps, Operator, storage, observabilité, RCA | `dc7b0af7eede48c6983bb4a8449ae1b87bf1d18ecd59fc203aaa430d8de4e050` |
| [Dossier TradeOps GenAI / Agentic AI / MCP / IBM MQ — Architecture & Runtime](Dossier_TradeOps_GenAI_Agentic_MCP_IBM_MQ_Architecture_Runtime_20261008.pdf) | 29 pages ; métier trading simulé, AI Access, gouvernance, Risk/HITL, MCP natif, IBM MQ, observabilité et architecture applicative | `1df3f356666c473ce91169367d028a73c7d98f0bea0a01648125edf4680dafc3` |

## Sources et frontières de preuve

- Capture **read-only** du 08/10/2026 : `89` commandes réparties sur `12` sections dans OpenShift Local / CRC 4.22.7 mono-nœud, contexte local `tradeops` explicite.
- À la capture, TradeOps était en **PARK volontaire** : les Deployments arrêtés intentionnellement ne constituent pas des pannes. Les StatefulSets doivent être analysés séparément.
- La preuve live de la chaîne **Agent Controller → MCP Native → mq-ops-api → QM.MAYABANK** est **une campagne antérieure**, tracée dans [R5 CRC runtime evidence](../38-mcp-r5-crc-runtime-evidence.md) et [son résumé](../../evidence/r5/20261008-crc-native-mcp-mq-observed-summary.md) ; les commandes read-only du dossier ne réexécutent pas R5.
- Ne pas assimiler CRC mono-nœud à une plateforme hautement disponible ou une mise en production.
- D-093 `CapabilityConsumption/tradeops-crc` demeure en `Observe` ; ni adoption `Manage` ni changement d'ownership implicite.
- La présente publication n'intègre pas le **bundle opérationnel brut** de l'archive locale, qui nécessite un contrôle de sensibilité avant toute publication.

## Contrôle d'intégrité

Sur Git Bash, depuis la racine du dépôt :

```bash
sha256sum docs/dossiers/Dossier_TradeOps_*.pdf
```

Vérifier que les empreintes correspondent au tableau ci-dessus.

Références méthodologiques :
- [Runbook CaaS Day-2/N3](https://github.com/zdmooc/shared-platform-services-openshift/blob/main/docs/runbooks/OPENSHIFT_CAAS_DAY2_N3_DEMO.md)
- [Dossier CaaS / Platform Engineering](https://github.com/zdmooc/shared-platform-services-openshift/blob/main/docs/architecture/OPENSHIFT_CAAS_PLATFORM_ENGINEERING_DAY2_N3_DOSSIER.md)
- [Data Lakehouse Kubernetes/OpenShift](https://github.com/zdmooc/enterprise-data-lakehouse-kubernetes-openshift)

## Parcours de démonstration

Ces dossiers s'intègrent au [parcours TradeOps demo/](../../demo/README.md) : checklist d'entretien, scénarios, présentation orale, préflight et diagnostic CRC read-only. Les PDF reposent sur la capture datée du 08/10/2026 et les preuves historiques citées, pas sur une nouvelle campagne ACTIVE.
