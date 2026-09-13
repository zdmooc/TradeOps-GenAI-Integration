# TradeOps Web Cockpit — IHM métier de démonstration

## Statut

**IMPLEMENTED IN GIT / CRC LIVE DEPLOYMENT PENDING** au 2026-09-13.

L'IHM React/TypeScript, son image OpenShift, son reverse proxy, son packaging Helm/GitOps, ses contrôles CI et ses scripts CRC sont implémentés. La Route canonique reste `PLANNED` tant qu'un déploiement réel CRC n'a pas fourni de preuve runtime.

Route cible :

`https://tradeops-ui-tradeops.apps-crc.testing`

## Objectif

Donner une vraie interface métier au-dessus des capacités TradeOps existantes, sans modifier les principes d'architecture : visualisation marché/signaux, preuves agents, Risk Gate, Human-in-the-Loop, SHADOW/PAPER, performance de démonstration, audit et liens plateforme.

Grafana reste l'interface SRE/observabilité. Le cockpit est l'interface métier/démonstration.

## Architecture implémentée

```text
Browser
  -> TradeOps Web Cockpit (React + TypeScript)
      -> Nginx same-origin reverse proxy
          -> /api/market/*   -> market-data:8011
          -> /api/workflow/* -> workflow-api:8012
          -> /api/agent/*    -> agent-controller:8015

agent-controller
  -> RAG API / MCP / deterministic fusion / Risk Gate / HITL

workflow-api
  -> PostgreSQL / audit
```

Les services sensibles ne reçoivent pas de Route dédiée pour l'IHM : MCP, PostgreSQL, Redpanda/Kafka, Qdrant, Prometheus et OTEL restent internes.

## Écrans livrés

- **Cockpit** : cartes instruments, contexte marché, chart illustratif clairement marqué démo/synthétique, signal, entry/stop/target/R:R, régime, pattern, score ML qualifié.
- **Agent Evidence** : Market, Technical, Pattern, Macro, RAG, ML et états `SUPPORTED/NEUTRAL/WATCH/VETO`.
- **HITL** : création de proposition réelle via Agent Controller, revue `APPROVE/REJECT`, puis exécution gouvernée `SHADOW/PAPER`.
- **Performance** : outcomes de démonstration avec provenance `DEMO_SYNTHETIC` et avertissement explicite qu'il ne s'agit pas d'une performance réelle.
- **Audit** : lecture du vrai endpoint `/audit` du Workflow API.
- **Plateforme** : liens Agent Swagger, Workflow Swagger, Grafana et OpenShift Console.

## Sécurité

- aucun secret n'est compilé dans le frontend ;
- les tokens Agent/Reviewer sont saisis explicitement par l'utilisateur et conservés uniquement en mémoire React ;
- ils ne sont pas stockés dans un stockage persistant du navigateur ;
- CSP, `X-Frame-Options`, `nosniff`, Referrer Policy et Permissions Policy sont appliqués par Nginx ;
- le frontend n'accède jamais directement à MCP/DB/Kafka/Qdrant ;
- `MCP_AGENT_TOKEN` et `MCP_REVIEWER_TOKEN` sont injectés côté backend via le Secret OpenShift ;
- le Risk Gate déterministe garde le veto ;
- aucun bouton real-money n'existe.

## Packaging OpenShift/GitOps

- `frontend/tradeops-ui/Dockerfile` : build Node + runtime Nginx unprivileged ;
- `tradeops-ui` ImageStream + BuildConfig ;
- image cible `tradeops-ui:i13-ui` ;
- Helm `Deployment` + `Service` + Route ;
- probes `/healthz` ;
- requests/limits adaptés CRC ;
- NetworkPolicy autorise uniquement l'ingress routeur nécessaire ;
- Argo CD réutilise automatiquement le chart Helm existant.

## Backlog

| ID | Statut | Résultat |
|---|---|---|
| UI-01 | DONE | React/TypeScript/Vite scaffold |
| UI-02 | DONE | shell, navigation, responsive layout |
| UI-03 | DONE | reverse proxy same-origin market/workflow/agent |
| UI-04 | DONE | market dashboard + provenance démo/API |
| UI-05 | DONE | signal detail entry/stop/target/R:R |
| UI-06 | DONE | agent evidence + états de conflit/veille |
| UI-07 | DONE_CODE | workflow HITL branché sur vraies APIs ; preuve live CRC encore requise |
| UI-08 | DONE_DEMO | outcome history avec provenance ; métriques réelles à enrichir plus tard |
| UI-09 | DONE | catalogue `docs/28-demo-urls.md` |
| UI-10 | DONE | Dockerfile + Deployment + Service + Route |
| UI-11 | DONE | intégration Helm/GitOps |
| UI-12 | DONE | CSP, headers, no embedded secrets, fail-closed credentials |
| UI-13 | PENDING_LIVE | déploiement CRC + evidence runtime |
| UI-14 | DONE | polling 15 s ; SSE/WebSocket non nécessaire pour V1 |
| UI-15 | DONE_DEMO | vue performance avec labels de provenance |
| UI-16 | DONE | scénario déterministe de démonstration |
| UI-17 | PARTIAL | responsive/keyboard native ; audit accessibilité formel non fait |
| UI-18 | DEFERRED | OIDC/Entra production après preuve CRC |

## CI

La CI doit maintenant valider :

1. build TypeScript/Vite ;
2. Helm lint/render ;
3. `I13_WEB_COCKPIT_VALIDATION_PASS` ;
4. tests Python de contrat ;
5. gates I9/I10/I11/I12 existants.

## Definition of Done CRC

Le cockpit ne passera à `DEPLOYED/VERIFIED` qu'après preuve réelle :

1. BuildConfig `tradeops-ui` terminé ;
2. Deployment Ready ;
3. Route `tradeops-ui-tradeops.apps-crc.testing` créée ;
4. `/healthz` OK ;
5. `/api/agent/health` et `/api/workflow/health` OK via le proxy UI ;
6. une proposition devient `REVIEW_REQUIRED` ;
7. reviewer humain APPROVE ou REJECT ;
8. SHADOW/PAPER démontré sans ordre réel ;
9. audit visible ;
10. evidence capturée sous `evidence/graduation/live/ui/<UTC_TIMESTAMP>/`.

Jusqu'à cette preuve, `docs/28-demo-urls.md` conserve la Route IHM en `PLANNED`.
