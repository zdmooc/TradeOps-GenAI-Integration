# TradeOps Web Cockpit — IHM métier de démonstration

## Statut

**DEPLOYED LIVE ON CRC / PLATFORM VERIFIED / FULL HITL LIVE SCENARIO PENDING** au 2026-09-13.

L'IHM React/TypeScript, son image OpenShift, son reverse proxy, son packaging Helm/GitOps, ses contrôles CI et ses scripts CRC sont implémentés. Le déploiement réel CRC est maintenant prouvé : BuildConfig `tradeops-ui` terminé, image publiée, Deployment Ready, Route créée, endpoints UI/proxy HTTP 200 et `I9_CRC_VERIFY_PASS`.

Route LIVE :

`https://tradeops-ui-tradeops.apps-crc.testing`

Preuve runtime :

`evidence/graduation/live/ui/20260913/README.md`

Le scénario métier HITL complet reste à capturer en live avant de qualifier le cockpit de démonstration métier end-to-end totalement vérifiée : `REVIEW_REQUIRED -> APPROVE/REJECT -> SHADOW/PAPER -> audit`.

## Preuve CI

GitHub Actions **#92** (`34750050606`) sur le commit `17d47d33a663b78fd5e23518927929fe5e43b4ce` : **SUCCESS**.

La CI a validé : build React/TypeScript/Vite, audit sécurité, SBOM, Helm lint/render, I9, I10, `I13_WEB_COCKPIT_VALIDATION_PASS`, Terraform/I11, graduation I12 et **230 tests Pytest**.

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
- **HITL** : création de proposition via Agent Controller, revue `APPROVE/REJECT`, puis exécution gouvernée `SHADOW/PAPER`.
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
- NetworkPolicy autorise l'ingress routeur nécessaire ;
- Argo CD réutilise le chart Helm existant.

## Backlog

| ID | Statut | Résultat |
|---|---|---|
| UI-01 | DONE | React/TypeScript/Vite scaffold + build CI |
| UI-02 | DONE | shell, navigation, responsive layout |
| UI-03 | DONE | reverse proxy same-origin market/workflow/agent |
| UI-04 | DONE | market dashboard + provenance démo/API |
| UI-05 | DONE | signal detail entry/stop/target/R:R |
| UI-06 | DONE | agent evidence + états de conflit/veille |
| UI-07 | DONE_CODE | workflow HITL branché sur vraies APIs ; preuve live end-to-end encore requise |
| UI-08 | DONE_DEMO | outcome history avec provenance ; métriques réelles à enrichir plus tard |
| UI-09 | DONE | catalogue `docs/28-demo-urls.md` |
| UI-10 | DONE | Dockerfile + Deployment + Service + Route |
| UI-11 | DONE | intégration Helm/GitOps |
| UI-12 | DONE | CSP, headers, no embedded secrets, fail-closed credentials |
| UI-13 | DONE_LIVE | build UI + déploiement CRC + Route/proxy health + evidence runtime |
| UI-14 | DONE | polling 15 s ; SSE/WebSocket non nécessaire pour V1 |
| UI-15 | DONE_DEMO | vue performance avec labels de provenance |
| UI-16 | DONE | scénario déterministe de démonstration |
| UI-17 | PARTIAL | responsive/keyboard native ; audit accessibilité formel non fait |
| UI-18 | DEFERRED | OIDC/Entra production après preuve CRC |

## Preuve CRC obtenue

Le 2026-09-13, les critères de déploiement plateforme suivants ont été vérifiés :

1. BuildConfig `tradeops-ui` terminé (`tradeops-ui-1`, `Complete`) ;
2. ImageStreamTag `tradeops-ui:i13-ui` publiée ;
3. Deployment `tradeops-ui` Ready `1/1` ;
4. Route `tradeops-ui-tradeops.apps-crc.testing` créée ;
5. `/` et `/healthz` répondent HTTP 200 ;
6. `/api/market/health`, `/api/workflow/health` et `/api/agent/health` répondent HTTP 200 via le proxy UI ;
7. `scripts/i9_crc_verify.sh` termine avec `I9_CRC_VERIFY_PASS` ;
8. evidence capturée sous `evidence/graduation/live/ui/20260913/`.

## Reste pour la preuve métier end-to-end

La Route est désormais LIVE. Pour fermer aussi la preuve fonctionnelle HITL complète, il reste à capturer :

1. une proposition passant à `REVIEW_REQUIRED` ;
2. une action reviewer humaine `APPROVE` ou `REJECT` ;
3. pour une approbation, une exécution gouvernée `SHADOW/PAPER` sans ordre réel ;
4. la trace correspondante dans l'audit.

Cette étape fonctionnelle ne change pas les blockers de graduation I12, qui restent `OPENSHIFT_AZURE_DEPLOYMENT` et `RESILIENCE_FINOPS_GREENOPS_VERIFIED`.
