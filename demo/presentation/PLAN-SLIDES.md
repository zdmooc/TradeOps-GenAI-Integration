# Plan de présentation — TradeOps CRC / OpenShift / Agentic AI

**Support documentaire** : [PDF OpenShift / N3](../../docs/dossiers/Dossier_TradeOps_OpenShift_CRC_Platform_Engineering_Day2_N3_20261008.pdf) et [PDF GenAI / MCP / IBM MQ](../../docs/dossiers/Dossier_TradeOps_GenAI_Agentic_MCP_IBM_MQ_Architecture_Runtime_20261008.pdf). Ce fichier est un **plan éditable de 10 vues**, pas un PowerPoint déjà généré.

| Vue | Message à faire passer | Illustration / preuve |
| --- | --- | --- |
| 1 | Contexte : architecture de décision de marché supervisée | Dossier GenAI : chaîne fonctionnelle |
| 2 | CRC mono-nœud et PARK volontaire | État OpenShift et snapshot |
| 3 | N3 top-down et capacity management | Dossier OpenShift et métriques datées |
| 4 | Architecture réseau / Route/Service/EndpointSlice | Diagnostic read-only |
| 5 | GitOps + Platform Operator + ownership Observe | `CapabilityConsumption/tradeops-crc` |
| 6 | Redpanda / données de marché / décisions | Scripts métier **présentés**, non exécutés |
| 7 | Risk Gate / HITL / SHADOW-PAPER | UI infrastructure prouvée, HITL complet pending |
| 8 | MCP R5 -> IBM MQ réel, queue refusée | Evidence R5, HTTP 403, re-PARK |
| 9 | G1/G2 AI Access gouverné + OTel/Prometheus | Preuves datées distinctes |
| 10 | Findings, limites, prochaines décisions | G3/G4, A2A live, HA non prouvés |

Adaptations commerciales : 15 min [TALK-TRACK](../TALK-TRACK.md), 30 min [pack entretien](../../docs/22-interview-demo-pack.md). Aucun des PDF ne remplace les preuves brutes d'une nouvelle campagne runtime.
