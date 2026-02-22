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



Chaîne de décision (GenAI review → exécution paper → audit)

Les événements critiques sont persistés dans PostgreSQL (audit_logs) avec :

kind : type d’événement (genai.review, order.filled)

ref_id : identifiant métier corrélé (workflow_id ou order_id)

correlation_id : corrélation inter-services

hash : intégrité de l’événement

created_at : horodatage

Preuve : derniers événements

docker compose exec postgres sh -lc 'psql -P pager=off -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select audit_id, kind, ref_id, correlation_id, created_at
from audit_logs
order by audit_id desc
limit 10;"'

Preuve : chaîne complète (workflow ↔ orders ↔ audit_logs)

docker compose exec postgres sh -lc 'psql -P pager=off -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select
  w.workflow_id,
  w.status as workflow_status,
  o.order_id,
  o.status as order_status,
  o.symbol, o.side, o.qty, o.fill_price,
  ar.audit_id as genai_audit_id,
  ar.correlation_id as genai_corr,
  ar.created_at as genai_at,
  af.audit_id as filled_audit_id,
  af.correlation_id as filled_corr,
  af.created_at as filled_at
from workflows w
left join orders o
  on o.workflow_id = w.workflow_id
left join audit_logs ar
  on ar.kind=''\''genai.review'\'' and ar.ref_id = w.workflow_id::text
left join audit_logs af
  on af.kind=''\''order.filled'\'' and af.ref_id = o.order_id::text
order by w.created_at desc
limit 10;"'
Latence opérationnelle (review → filled)

Mesure du temps entre la revue GenAI et le remplissage de l’ordre (paper) :

docker compose exec postgres sh -lc 'psql -P pager=off -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
select
  w.workflow_id,
  round(extract(epoch from (af.created_at - ar.created_at))::numeric, 3) as seconds_review_to_filled
from workflows w
join orders o
  on o.workflow_id = w.workflow_id
join audit_logs ar
  on ar.kind=''\''genai.review'\'' and ar.ref_id = w.workflow_id::text
join audit_logs af
  on af.kind=''\''order.filled'\'' and af.ref_id = o.order_id::text
order by w.created_at desc
limit 10;"'
Mini runbook “démo 60 secondes”
docker compose up -d --build
docker compose exec tools sh -lc "touch scripts/__init__.py 2>/dev/null || true; python -m scripts.demo_seed_and_publish && python -m scripts.demo_request_trade && python -m scripts.demo_approve_trade && python -m scripts.demo_show_audit"
docker compose exec postgres sh -lc 'psql -P pager=off -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select kind, count(*) from audit_logs group by kind order by 2 desc;"'
Point important dans tes résultats (à valoriser)

Tu as 3 workflows APPROVED qui mènent à 3 orders FILLED (paper).

La latence review → filled est mesurée : ~0.47s, 2.78s, 2.57s (preuve “performance process”).

Prochaine étape “niveau mission” (top 5 améliorations)

API Gateway policies (Kong) : rate limit, auth, correlation-id propagation

DLQ / retries côté event bus pour robustesse

Auth OIDC (Keycloak/Entra mock) + RBAC Trader/Risk

Tests charge (k6) + SLO p95 sur endpoints

Export evidence automatique (SQL + logs + versions images) vers evidence/…/

## 5) Licence
MIT (voir `LICENSE`).


