# TradeOps GenAI Integration Hub

**Trading · Integration IA/GenAI · API/Event/Workflow · Agentic AI · MCP · RAG · Run**

Projet portfolio "Consultant Integration AI" orienté **intégration IA/GenAI dans un SI de trading** :

- Intégration via **APIs** (gateway type API Management)
- Architecture **event-driven** (Kafka compatible)
- Orchestration de **workflows** (demande → revue IA → approbation → exécution paper)
- **RAG** sur documentation interne (règles de risque, runbooks) + LLM **plug-in** (Mock/Azure/OpenAI)
- **Agent Controller** (LangGraph) avec boucle plan→act→observe et **confidence gating**
- **MCP Server** (Model Context Protocol) pour standardiser l'accès aux outils internes
- **Robustesse / sécurité / performance** : idempotence, retries, rate limit, audit trail, mode dégradé
- **Mise en prod + Run** : métriques Prometheus, dashboards Grafana, traces OpenTelemetry

## Architecture

Le projet combine trois paradigmes complémentaires :

| Paradigme | Composant | Description |
|-----------|-----------|-------------|
| **LLM Workflow** | genai-api | Revue IA des trades via LLM (mock/Azure/OpenAI) |
| **RAG** | rag-api + Qdrant | Enrichissement contextuel via base de connaissances vectorielle |
| **Agentic AI** | agent-controller | Décision autonome avec confidence gating (LangGraph) |
| **MCP** | mcp-server | Accès standardisé aux outils internes (DB, OMS, Risk, Market) |

Le graphe agent exécute : **PLAN → RETRIEVE (RAG) → TOOL_CALLS (MCP) → EVALUATE → DECIDE → EXECUTE**

Pour les détails, voir `docs/architecture/agentic.md`.

## Services

| Service | Port | Description |
|---------|------|-------------|
| market-data | 8011 | API de données de marché (synthétique) |
| workflow-api | 8012 | Orchestrateur de workflows |
| genai-api | 8013 | Revue GenAI (LLM + RAG simple) |
| rag-api | 8014 | API RAG (Qdrant + sentence-transformers) |
| agent-controller | 8015 | Agent Controller (LangGraph + confidence gating) |
| mcp-server | 8016 | MCP Server (outils internes) |
| qdrant | 6333 | Base de données vectorielle |
| kong | 8000 | API Gateway |
| postgres | 5433 | Base de données (workflows, orders, audit_logs) |
| redpanda | 9092 | Event bus (Kafka compatible) |
| prometheus | 9090 | Métriques |
| grafana | 3000 | Dashboards (admin/admin) |

## 0) Prérequis

- Docker Desktop + Docker Compose v2
- (Option) `make` / Git Bash (Windows ok)
- (Option) Clés LLM : Azure OpenAI ou OpenAI (sinon **Mock** par défaut)

## 1) Démarrage rapide (local Docker Compose)

```bash
cp .env.example .env
docker compose up -d --build
```

Vérifications santé :

```bash
curl http://localhost:8011/health   # market-data
curl http://localhost:8012/health   # workflow-api
curl http://localhost:8013/health   # genai-api
curl http://localhost:8014/health   # rag-api
curl http://localhost:8015/health   # agent-controller
curl http://localhost:8016/health   # mcp-server
```

## 2) Démo end-to-end (paper trading classique)

```bash
# 1) seed market data + publish events
docker compose exec tools python scripts/demo_seed_and_publish.py

# 2) crée une demande de trade (workflow)
docker compose exec tools python scripts/demo_request_trade.py

# 3) approuve la demande (simulateur "risk/compliance")
docker compose exec tools python scripts/demo_approve_trade.py

# 4) observe les événements et l'audit trail
docker compose exec tools python scripts/demo_show_audit.py
```

## 3) Démo Agentic AI (1 ligne)

```bash
docker compose exec tools python scripts/demo_agentic_trade.py
```

Ce script soumet un trade au **Agent Controller** qui :
1. Crée un workflow (REQUESTED)
2. Exécute le graphe LangGraph (PLAN → RETRIEVE → TOOL_CALLS → EVALUATE → DECIDE)
3. Si APPROVE : place l'ordre via MCP/OMS et affiche le `order_id` + `fill_price`
4. Si NEEDS_HUMAN : signale que la confiance est insuffisante

## 4) Structure

```
services/
  common/              # Config, DB, audit, Kafka, logging, metrics
  market_data/         # API données de marché
  workflow_api/        # Orchestrateur de workflows
  genai_api/           # Revue GenAI (LLM + RAG simple)
  rag_api/             # API RAG (Qdrant + sentence-transformers)
  agent_controller/    # Agent Controller (LangGraph)
  mcp_server/          # MCP Server (outils internes)
  signal_engine/       # Moteur de signaux (Kafka worker)
  risk_engine/         # Moteur de risque (Kafka worker)
  paper_oms/           # OMS papier (Kafka worker)
  notifier/            # Notificateur (Kafka worker)
infra/                 # Docker, Kong, observabilité, init DB
schemas/               # Catalogue d'événements (JSON Schema)
docs/                  # Architecture, runbooks, sécurité, SLO
  architecture/        # Diagrammes agentic AI
  rag.md               # Documentation RAG
  mcp.md               # Documentation MCP
gitops/                # Déploiement Kubernetes/OpenShift
```

## 5) Mode LLM (Mock / Azure / OpenAI)

Par défaut : `LLM_PROVIDER=mock`.

- `azure_openai` : configure `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`
- `openai` : configure `OPENAI_API_KEY`, `OPENAI_MODEL`

## 6) Evidence (Audit Trail)

Les événements critiques sont persistés dans PostgreSQL (`audit_logs`) avec : `kind`, `ref_id`, `correlation_id`, `hash`, `created_at`.

### Preuve : derniers événements agent

```bash
docker compose exec postgres sh -lc 'psql -P pager=off -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select audit_id, kind, ref_id, correlation_id, created_at
from audit_logs
where kind like '\''agent.%'\'' or kind like '\''mcp.%'\'' or kind like '\''rag.%'\''
order by audit_id desc
limit 20;"'
```

### Preuve : workflows avec decision/confidence

```bash
docker compose exec postgres sh -lc 'psql -P pager=off -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select workflow_id, status, decision, confidence_score, reviewer, created_at
from workflows
order by created_at desc
limit 10;"'
```

### Export evidence complet

```bash
bash scripts/export_evidence.sh
```

Les fichiers sont générés dans `evidence/` (ignoré par git). Un sample est disponible dans `evidence-sample/`.

## 7) Licence

MIT (voir `LICENSE`).
