# Runbook A–Z — démonstration TradeOps sur OpenShift Local / CRC

## A — Vérifier le dépôt et le contexte

```bash
cd /c/workspaces/TradeOps-GenAI-Integration
git status --short --branch
oc whoami --show-server
crc status
```

**Ne pas faire** `git pull`, `crc start`, `kubectl config use-context` ou une bascule Kind/CRC automatiquement : ces choix relèvent de la préparation explicite. Le préflight refuse un cluster autre que `api.crc.testing:6443`.

## B — Identifier PARK / ACTIVE

```bash
bash demo/scripts/00-preflight.sh
oc -n tradeops get deployments,statefulsets,pods
```

La commande annonce le snapshot PARK *enregistré* et observe les replicas actifs. Si le snapshot et le runtime divergent, suspendre la démo fonctionnelle et investiguer. Un Deployment `0/0` pendant PARK n'est pas un incident. Les StatefulSets `postgres`, `redpanda` et `qdrant` ne doivent pas être arrêtés pour libérer de la RAM en profil CRC à stockage éphémère.

## C — Capture Day-2 / N3 (lecture seule)

```bash
bash demo/scripts/01-capture-readonly.sh
```

Les fichiers restent dans `.runtime/tradeops-demo/<UTC>/` avec résumé et codes de sortie. Cette collecte ne reproduit **pas** les 89 commandes historiques ; elle fournit un jeu plus court et renouvelable. La capture de référence du 08/10 est déjà documentée dans [les PDF](../docs/dossiers/README.md).

## D — Présenter OpenShift / CaaS

Lecture : ClusterVersion -> ClusterOperators -> nœud/capacité -> namespaces/quotas -> workloads -> Routes/Services/EndpointSlices -> sécurité -> OLM/Operators -> GitOps -> stockage/observabilité -> RCA.

Scénario détaillé : [01-platform-day2-n3](scenarios/01-platform-day2-n3.md).

## E — Démontrer l'application (ou lire les preuves si PARK)

```text
Market Data -> Kafka/Redpanda -> signaux / agents / RAG
             -> décision déterministe / Risk Gate -> revue humaine
             -> SHADOW/PAPER -> audit
```

- [02-trading-risk-hitl](scenarios/02-trading-risk-hitl.md)
- [03-agentic-ai-rag](scenarios/03-agentic-ai-rag.md)

Le script `scripts/i9_crc_verify.sh` est réservé à un environnement **réellement ACTIVE** : il attend la disponibilité de plusieurs Deployments et échouera normalement si TradeOps est en PARK. Ne pas l'utiliser comme préflight read-only PARK.

## F — Preuve native MCP -> IBM MQ

Ouvrir [04-mcp-ibm-mq](scenarios/04-mcp-ibm-mq.md). Le run R5 du 08/10 a déjà vérifié outils MCP, profondeur de queue, négatif HTTP 403 et refus du bypass, puis le re-PARK. **Ne pas exécuter** `scripts/r5_crc_mcp_mq_run.sh` dans un entretien : il peut déployer/rebuilder selon l'état local.

## G — GitOps, Security, Observability, IA gouvernée

Suivre [05-gitops-security](scenarios/05-gitops-security.md), puis les preuves historiques G1/G2. `D-093 Observe` reste non mutateur ; aucune déduction `Manage`.

## H — Parcours oral

- **15 min** : [TALK-TRACK](TALK-TRACK.md).
- **30 min** : [pack existant](../docs/22-interview-demo-pack.md).
- **Support** : [plan des slides](presentation/PLAN-SLIDES.md), et les deux PDF dans `docs/dossiers`.

## I — Diagnostic si une ressource paraît absente

Vérifier ordre : date du snapshot -> PARK vs ACTIVE -> Phase/Ready du Pod -> scheduling/memory -> Route/Service/EndpointSlice -> NetworkPolicy/RBAC/SCC -> Operators/GitOps -> logs **après validation de leur confidentialité** -> RCA. Voir [TROUBLESHOOTING](TROUBLESHOOTING.md).

## J — Fin de démonstration

Vérifier `git status --short`. Ne pas restaurer ou arrêter le cluster : cette démo n'a modifié aucune ressource. Toute campagne ACTIVE ultérieure aura une procédure dédiée avec précondition, consentement, ressource et retour PARK.

## Frontières

CRC mono-nœud ≠ HA/DR/production. R5 ≠ A2A live ; G1/G2 mono-consommateur ≠ D-090 G3/G4 ; UI opérationnelle à une date donnée ≠ scénario HITL end-to-end aujourd'hui. Les données de marché/performances de démo ne sont pas des transactions en argent réel.
