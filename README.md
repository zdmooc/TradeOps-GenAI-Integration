# TradeOps GenAI Integration Hub

**Trading · Integration IA/GenAI · API/Event/Workflow · Agentic AI · MCP · RAG · Run**

Projet portfolio orienté **architecture et intégration IA/GenAI dans un SI de trading temps réel** :

- intégration via **APIs** et architecture **event-driven** Kafka compatible ;
- orchestration de workflows trading, revue, approbation et exécution SHADOW/PAPER ;
- **RAG**, **LangGraph**, agents spécialisés et frontière **MCP** gouvernée ;
- moteur de risque déterministe avec droit de veto et **Human-in-the-Loop** ;
- observabilité Prometheus/Grafana/OpenTelemetry ;
- OpenShift/CRC, GitOps/Argo CD, RHOAI/KServe et cible Azure/ARO ;
- **TradeOps Web Cockpit** : IHM métier React/TypeScript **implémentée dans Git**, avec déploiement/validation live CRC encore à exécuter.

## Architecture

Le projet combine plusieurs capacités complémentaires :

| Capacité | Composant | Rôle |
|---|---|---|
| Market data | market-data | Données de marché / replay / démonstration |
| Workflow | workflow-api | Orchestration et audit |
| GenAI | genai-api | Revue IA gouvernée |
| RAG | rag-api + Qdrant | Contexte documentaire |
| Agentic AI | agent-controller | Fusion des preuves, décision et HITL |
| MCP | mcp-server | Accès gouverné aux outils internes |
| Risk | risk-engine | Contrôles déterministes / veto |
| Paper OMS | paper-oms | Exécution simulée uniquement |
| Web UI | tradeops-ui | Cockpit métier / démonstration |

Le principe de sécurité reste : **aucun LLM ou agent ne peut contourner le Risk Gate déterministe ni le Human-in-the-Loop**.

## Services

| Service | Port | Description |
|---|---:|---|
| market-data | 8011 | API de données de marché |
| workflow-api | 8012 | Orchestrateur de workflows |
| genai-api | 8013 | Revue GenAI |
| rag-api | 8014 | API RAG |
| agent-controller | 8015 | Orchestration agentique + HITL |
| mcp-server | 8016 | Frontière outils gouvernée |
| tradeops-ui | 8080 | Cockpit Web React/TypeScript |
| qdrant | 6333 | Base vectorielle |
| postgres | 5432 | Workflows, orders, audit_logs |
| redpanda | 9092 | Event bus Kafka compatible |
| prometheus | 9090 | Métriques |
| grafana | 3000 | Dashboards SRE/LLMOps |

## Démarrage local historique

Le projet conserve son mode Docker Compose pour les services backend :

```bash
cp .env.example .env
docker compose up -d --build
```

Vérifications santé :

```bash
curl http://localhost:8011/health
curl http://localhost:8012/health
curl http://localhost:8013/health
curl http://localhost:8014/health
curl http://localhost:8015/health
curl http://localhost:8016/health
```

## TradeOps Web Cockpit

Le frontend est maintenant présent sous :

```text
frontend/tradeops-ui/
```

Technologies :

- React + TypeScript + Vite ;
- Nginx unprivileged pour l'image OpenShift ;
- reverse proxy same-origin vers `market-data`, `workflow-api` et `agent-controller` ;
- aucun accès direct navigateur à MCP, PostgreSQL, Kafka/Redpanda ou Qdrant ;
- CSP et headers de sécurité ;
- tokens Agent/Reviewer saisis uniquement pour la démo HITL et conservés en mémoire navigateur ;
- Helm + BuildConfig + Route + GitOps/Argo CD.

L'IHM offre :

- Market Dashboard ;
- Signal Detail : entry, stop, targets, R/R, régime, pattern, ML ;
- Agent Evidence ;
- Risk Gate ;
- Human-in-the-Loop : `REVIEW_REQUIRED -> APPROVE/REJECT -> SHADOW/PAPER` ;
- Performance/outcomes avec provenance explicite ;
- Audit backend ;
- liens Grafana, Swagger et OpenShift Console.

Architecture/backlog détaillé : [`docs/27-tradeops-web-cockpit.md`](docs/27-tradeops-web-cockpit.md).

## OpenShift / CRC

Le chart Helm déploie désormais le backend, la plateforme d'observabilité et `tradeops-ui`. Le BuildConfig OpenShift construit séparément :

```text
tradeops-runtime:i9
tradeops-ui:i13-ui
```

La Route cible de l'IHM est :

```text
https://tradeops-ui-tradeops.apps-crc.testing
```

**Statut : IMPLEMENTED IN GIT / NOT YET VERIFIED LIVE ON CRC.**

Elle ne doit pas être présentée comme `LIVE` tant que `scripts/i9_crc_deploy.sh` puis `scripts/i9_crc_verify.sh` n'ont pas réussi sur le CRC réel et qu'une preuve n'a pas été capturée.

## URLs de démonstration

Catalogue complet et statuts `LIVE / INTERNAL / PLANNED / REFERENCE` : [`docs/28-demo-urls.md`](docs/28-demo-urls.md).

Routes CRC déjà vérifiées :

```text
https://agent-controller-tradeops.apps-crc.testing
https://workflow-api-tradeops.apps-crc.testing
https://grafana-tradeops.apps-crc.testing
```

Plateforme CRC :

```text
https://console-openshift-console.apps-crc.testing
https://api.crc.testing:6443
```

Route IHM à valider :

```text
https://tradeops-ui-tradeops.apps-crc.testing
```

## CI / qualité

La CI valide désormais notamment :

- Ruff et audit sécurité ;
- SBOM ;
- build React/TypeScript/Vite ;
- Helm lint/render ;
- contrats OpenShift I9 ;
- RHOAI/KServe I10 ;
- Web Cockpit I13 ;
- Terraform/Azure I11 ;
- graduation I12 ;
- suite Pytest complète.

Le validator cockpit est :

```bash
python scripts/i13_validate_web_cockpit.py
```

## Evidence et sécurité financière

Le périmètre trading reste :

```text
analysis -> signal -> replay/backtest -> SHADOW/PAPER -> Human-in-the-Loop
```

L'exécution automatique d'argent réel est hors scope. Les métriques ou outcomes synthétiques affichés par l'IHM sont explicitement marqués comme tels et ne sont jamais présentés comme une performance réelle.

Evidence IHM : [`evidence/ITERATION-013-WEB-COCKPIT.md`](evidence/ITERATION-013-WEB-COCKPIT.md).

## Structure principale

```text
services/               # APIs, agents, risk, OMS, common
frontend/tradeops-ui/   # IHM React/TypeScript
infra/helm/tradeops/    # packaging OpenShift
infra/openshift/        # BuildConfig, policies, CRC overlays
gitops/                 # Argo CD
docs/                   # architecture, runbooks, demo URLs
scripts/                # deploy/verify/validators/evidence
schemas/                # contrats JSON
evidence/               # preuves versionnées
```

## Licence

MIT (voir `LICENSE`).
