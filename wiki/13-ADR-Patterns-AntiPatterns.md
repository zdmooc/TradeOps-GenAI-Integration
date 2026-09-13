# 13 — ADR, patterns et anti-patterns

## 1. Pourquoi des ADR ?

Un Architecture Decision Record capture :

- le contexte ;
- la décision ;
- les alternatives ;
- les conséquences ;
- le statut.

L’objectif n’est pas de justifier rétrospectivement tout choix, mais de rendre explicite **pourquoi l’architecture est ainsi**.

## 2. Décisions structurantes TradeOps

### ADR — Runtime principal unique

Un seul dépôt porte le runtime exécutable. Les dépôts de référence ne deviennent pas des runtimes concurrents.

### ADR — Déterministe hors LLM

Indicateurs, patterns déterministes, risk policy et veto restent hors raisonnement LLM.

### ADR — Events canoniques

Les events préservent source, event time, ingest time, spread, latency et état de qualité.

### ADR — ML probability qualification

Une probabilité nécessite calibration/qualification ; les scores synthétiques ne deviennent pas des probabilités métier.

### ADR — LangGraph pour orchestration

LangGraph est le framework agentique implémenté ; les alternatives restent des références tant qu’une décision explicite ne les adopte pas.

### ADR — MCP comme security boundary

L’accès outil impose identité, scopes, allowlist, validation, timeout, rate-limit et audit.

### ADR — HITL séparé de l’identité Agent

Le reviewer dispose d’une identité/autorité distincte. Le veto risque ne peut pas être overridé.

### ADR — OpenTelemetry portable

OTEL est le contrat de télémétrie inter-environnements.

### ADR — OpenShift/GitOps + RHOAI/KServe

OpenShift fournit le runtime, GitOps la réconciliation, RHOAI/KServe le modèle de serving IA.

### ADR — Azure ARO-first

ARO conserve les contrats OpenShift ; Foundry est optionnel.

### ADR — Evidence status explicite

`DESIGNED`, `IMPLEMENTED`, `TESTED`, `DEPLOYED`, `VERIFIED` ne sont jamais synonymes.

## 3. Patterns utilisés

### Event-Driven Architecture

Découple producteurs et consommateurs et permet replay.

### Human-in-the-Loop

Ajoute une autorité humaine explicite avant action sensible.

### Policy Enforcement Point

Le Risk Gate applique une décision de politique et peut bloquer.

### BFF léger / Same-Origin Proxy

Le cockpit passe par Nginx vers un petit nombre de backends autorisés.

### GitOps

Git représente l’état désiré et Argo CD réconcilie le cluster.

### Bulkhead / isolation

Les responsabilités et droits sont séparés pour réduire le blast radius.

### Idempotent Consumer

Une répétition d’événement ou de commande ne doit pas dupliquer l’effet métier.

### Retrieval-Augmented Generation

Sépare corpus versionné/retrieval de la logique générative.

### Saga / Stateful Workflow

Le lifecycle décision/review/execution ressemble à un workflow distribué long avec états et compensations/refus explicites.

## 4. Anti-patterns interdits

### LLM as Risk Engine

Confier directement les règles de risque à un LLM rend la politique non déterministe.

### Agent with God Token

Un agent avec tous les scopes annule la séparation des responsabilités.

### Browser-to-Database

Expose les stores internes et contourne les contrôles métier.

### Secret in Frontend

Tout secret compilé dans React est public pour le navigateur.

### Majority Voting = Truth

Plusieurs agents peuvent partager la même erreur. Le vote ne remplace pas les gates de politique.

### Score = Probability

Présenter un score non calibré comme probabilité crée une fausse précision.

### GitOps bypass

Modifier durablement le cluster à la main crée du drift.

### Retry Storm

Retries infinis sans backoff/idempotence aggravent la panne.

### Observability by Logs Only

Les logs seuls ne donnent ni SLO ni corrélation complète.

### Synthetic = Real

Une donnée de démonstration ou un outcome synthétique ne doit jamais être présenté comme mesure réelle.

## 5. Template ADR recommandé

```markdown
# ADR-XXX — Titre

Status: PROPOSED | ACCEPTED | SUPERSEDED | REJECTED
Date: YYYY-MM-DD

## Context
...

## Decision
...

## Alternatives
...

## Consequences
### Positive
...
### Negative / Trade-offs
...

## Evidence
...
```

## 6. Critère de maturité

Une architecture mature ne cherche pas à avoir le plus de technologies possible. Elle sait expliquer :

- pourquoi une technologie est présente ;
- quelle responsabilité elle porte ;
- quelles alternatives ont été écartées ;
- quel coût/risque le choix introduit ;
- comment la décision sera remise en question si le contexte change.
