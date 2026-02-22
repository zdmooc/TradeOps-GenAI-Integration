# TradeOps GenAI Integration Hub (Trading • Integration IA/GenAI • API/Event/Workflow • Run)

Projet portfolio “Consultant Integration AI” orienté **intégration IA/GenAI dans un SI de trading** :
- Intégration via **APIs** (gateway type API Management)
- Architecture **event-driven** (Kafka compatible)
- Orchestration de **workflows** (demande → revue IA → approbation → exécution paper)
- **RAG** sur documentation interne (règles de risque, runbooks) + LLM **plug-in** (Mock/Azure/OpenAI)
- **Robustesse / sécurité / performance** : idempotence, retries, rate limit, audit trail, mode dégradé
- **Mise en prod + Run** : métriques Prometheus, dashboards Grafana, traces OpenTelemetry, logs Loki (option)

## 0) Prérequis
- Docker Desktop + Docker Compose v2
- (Option) `make` / Git Bash (Windows ok)
- (Option) Clés LLM : Azure OpenAI ou OpenAI (sinon **Mock** par défaut)

## 1) Démarrage rapide (local Docker Compose)
```bash
cp .env.example .env
docker compose up -d --build
```

Vérifications :
- Gateway (Kong): http://localhost:8000
- Market Data API: http://localhost:8011/docs
- Workflow API: http://localhost:8012/docs
- GenAI API: http://localhost:8013/docs
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

## 2) Démo end-to-end (paper trading)
```bash
# 1) seed market data + publish events
docker compose exec tools python scripts/demo_seed_and_publish.py

# 2) crée une demande de trade (workflow)
docker compose exec tools python scripts/demo_request_trade.py

# 3) approuve la demande (simulateur "risk/compliance")
docker compose exec tools python scripts/demo_approve_trade.py

# 4) observe les événements et l’audit trail
docker compose exec tools python scripts/demo_show_audit.py
```

## 3) Structure
- `services/` : microservices (FastAPI + workers Kafka)
- `infra/` : docker-compose, Kong (API gateway), observabilité, init DB
- `schemas/` : catalogue d’événements (JSON Schema)
- `docs/` : architecture, runbooks, sécurité, SLO
- `gitops/` + `infra/helm/` : déploiement Kubernetes/OpenShift (Helm + Argo CD)

## 4) Mode LLM (Mock / Azure / OpenAI)
Par défaut : `LLM_PROVIDER=mock`.
- `azure_openai` : configure `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`
- `openai` : configure `OPENAI_API_KEY`, `OPENAI_MODEL`

## 5) Licence
MIT (voir `LICENSE`).
