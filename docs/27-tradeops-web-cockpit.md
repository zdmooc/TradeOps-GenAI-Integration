# TradeOps Web Cockpit — IHM métier de démonstration

## Objectif

Ajouter une vraie IHM Web au-dessus des capacités TradeOps déjà construites, sans modifier les principes d'architecture existants.

Le cockpit doit permettre à un utilisateur de **voir, comprendre et piloter le workflow de décision trading** depuis un navigateur : données marché, signal, preuves techniques, agents, risk gate, Human-in-the-Loop, exécution SHADOW/PAPER, résultat et historique.

Grafana reste l'interface d'observabilité/SRE. Le cockpit est l'interface métier.

## Positionnement dans l'architecture

```text
Browser
  -> TradeOps Web Cockpit (React + TypeScript)
      -> same-origin /api/agent/*    -> agent-controller
      -> same-origin /api/workflow/* -> workflow-api
      -> read-only links             -> Grafana / OpenShift Console

agent-controller
  -> RAG API (internal)
  -> MCP Server (internal)
  -> deterministic risk / fusion / HITL

workflow-api
  -> PostgreSQL / Kafka-compatible event backbone
```

### Règle de sécurité

Le navigateur ne doit pas exposer directement les services internes sensibles :

- MCP Server ;
- RAG API ;
- Risk Engine ;
- Paper OMS ;
- PostgreSQL ;
- Redpanda/Kafka ;
- Qdrant ;
- OpenTelemetry Collector ;
- Prometheus.

La V1 utilise un reverse proxy same-origin dans le conteneur Web (par exemple Nginx) pour éviter de multiplier les Routes et les règles CORS.

## Route cible CRC

```text
https://tradeops-ui-tradeops.apps-crc.testing
```

Statut au 2026-09-13 : **PLANNED / NOT YET DEPLOYED**.

Ne pas présenter cette URL comme LIVE avant qu'une Route OpenShift réelle soit créée et vérifiée.

## Écrans fonctionnels

### 1. Market Dashboard

Afficher :

- instrument / symbole ;
- prix et timestamp ;
- spread / fraîcheur / qualité ;
- régime de marché ;
- volatilité ;
- indicateurs disponibles ;
- contexte multi-timeframe ;
- graphique prix/candles lorsque la source disponible le permet.

### 2. Signals

Afficher pour chaque proposition :

- LONG / SHORT ;
- entry ;
- stop ;
- targets ;
- risk/reward ;
- pattern ;
- timeframe ;
- régime ;
- evidence quality ;
- score ML et statut de qualification ;
- raisons de rejet éventuelles.

### 3. AI Agents

Rendre visible la chaîne de synthèse :

- Market evidence ;
- Technical evidence ;
- Pattern evidence ;
- Macro context ;
- Risk evidence ;
- RAG evidence ;
- fusion result ;
- conflits / DATA_STALE / UNKNOWN / VETO.

Le cockpit ne doit jamais laisser croire qu'un LLM remplace les calculs déterministes.

### 4. Human-in-the-Loop

Cycle visible :

```text
REVIEW_REQUIRED
  -> REJECT
  -> APPROVE SHADOW
  -> APPROVE PAPER
```

Le reviewer doit voir les preuves avant décision. Les actions doivent conserver l'identité du reviewer, le proposal ID, le correlation ID et l'audit trail.

### 5. Positions / Outcomes / Performance

Afficher :

- SHADOW / PAPER ;
- PENDING / TARGET / STOP / EXPIRED ;
- entry / exit ;
- PnL ;
- R multiple ;
- durée ;
- win rate ;
- expectancy ;
- drawdown lorsque calculable ;
- historique filtrable.

Les résultats réels, synthétiques et estimés doivent rester explicitement distingués.

### 6. Platform / Demo

Afficher des liens rapides vers :

- Grafana ;
- OpenShift Console ;
- Agent Controller Swagger ;
- Workflow API Swagger ;
- catalogue des URLs de démo.

## UX cible — écran principal

```text
+------------------------------------------------------------------+
| TRADEOPS                     Environment: CRC       Mode: PAPER    |
+----------+----------+----------+----------+-----------------------+
| CAC40    | DAX      | NASDAQ   | S&P500  | BTC                   |
+--------------------------------+---------------------------------+
| MARKET / CHART                 | CURRENT SIGNAL                  |
| price / indicators / regime    | LONG / SHORT                    |
|                                | entry / stop / targets / R:R    |
+--------------------------------+---------------------------------+
| AGENT EVIDENCE                 | DETERMINISTIC RISK GATE         |
| market / technical / pattern   | ACCEPT / VETO + reasons         |
| macro / RAG / ML / fusion      |                                 |
+------------------------------------------------------------------+
| HITL: REVIEW_REQUIRED                                             |
|             [REJECT] [APPROVE SHADOW] [APPROVE PAPER]            |
+------------------------------------------------------------------+
| Positions | Outcomes | Performance | Audit | Platform | Grafana  |
+------------------------------------------------------------------+
```

## Technologie cible

- React ;
- TypeScript ;
- Vite ;
- client HTTP typé ;
- bibliothèque de charts financiers à sélectionner après vérification licence/poids ;
- Nginx ou équivalent pour static hosting + reverse proxy ;
- image OCI compatible OpenShift restricted SCC ;
- Helm/GitOps pour déploiement ;
- aucune clé Azure/OpenAI/IG dans le frontend.

## Backlog UI

| ID | Priority | Status | Work item | Definition of Done |
|---|---|---|---|---|
| UI-01 | P0 | TODO | Scaffold React/TypeScript | `frontend/tradeops-ui` build reproductible, lint/test. |
| UI-02 | P0 | TODO | Shell + navigation | Header, environment/mode badges, navigation responsive. |
| UI-03 | P0 | TODO | API reverse proxy | `/api/agent` and `/api/workflow` same-origin, no direct MCP/RAG exposure. |
| UI-04 | P0 | TODO | Market dashboard | Instruments, freshness, regime, indicators, chart placeholder/live adapter. |
| UI-05 | P0 | TODO | Signal detail | Entry/stop/targets/R:R/evidence/ML qualification visible. |
| UI-06 | P0 | TODO | Agent evidence | Market/technical/pattern/macro/risk/RAG/fusion with conflict states. |
| UI-07 | P0 | TODO | HITL workflow | REVIEW_REQUIRED -> reject/shadow/paper using authenticated backend calls. |
| UI-08 | P0 | TODO | Outcome history | PAPER/SHADOW results, TP/SL/EXPIRED, PnL and filters. |
| UI-09 | P0 | TODO | Demo links page | Every verified CRC URL centralized with LIVE/INTERNAL/PLANNED status. |
| UI-10 | P0 | TODO | OpenShift packaging | Dockerfile, Deployment, Service, Route, probes, requests/limits. |
| UI-11 | P0 | TODO | GitOps integration | Helm/Kustomize + Argo CD reconciliation. |
| UI-12 | P0 | TODO | Security hardening | CSP/security headers, no secrets, token handling, fail-closed actions. |
| UI-13 | P0 | TODO | CRC live evidence | Route reachable, UI loads, backend health and HITL demo captured. |
| UI-14 | P1 | TODO | Near-real-time updates | Polling initially; SSE/WebSocket only if justified by backend contract. |
| UI-15 | P1 | TODO | Performance dashboard | Outcomes, win rate, expectancy, drawdown with provenance labels. |
| UI-16 | P1 | TODO | Demo mode | Deterministic demo dataset/workflow for interview repeatability. |
| UI-17 | P1 | TODO | Accessibility / responsive | Keyboard navigation, readable contrast, laptop/desktop layouts. |
| UI-18 | P2 | DEFERRED | Production auth federation | External OIDC/Entra integration after CRC demo path is proven. |

## Definition of Done CRC

The cockpit is considered `DEPLOYED` only when all of the following are evidenced:

1. `frontend/tradeops-ui` builds in CI.
2. Image builds under OpenShift constraints.
3. Deployment and Service are healthy in namespace `tradeops`.
4. Route `tradeops-ui-tradeops.apps-crc.testing` exists.
5. `/api/agent/health` and `/api/workflow/health` work through the UI proxy.
6. No internal MCP/RAG/DB endpoint is exposed by a public Route solely for UI convenience.
7. One end-to-end REVIEW_REQUIRED -> SHADOW/PAPER demo is captured.
8. Grafana/OpenShift/Swagger links work from the Demo page.
9. No live-money action exists.
10. Evidence is committed under `evidence/graduation/live/ui/<UTC_TIMESTAMP>/`.

## Non-goals

- no broker real-money execution ;
- no autonomous approval ;
- no replacement of Grafana ;
- no direct browser access to MCP, databases or internal event bus ;
- no claim of real-time streaming until measured and demonstrated ;
- no Azure dependency for the CRC version.
