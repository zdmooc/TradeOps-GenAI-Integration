# Architecture (C4 + flux)

## Vue d’ensemble (C2)
- API Gateway (Kong) : auth/rate-limit/routing (analogue API Management)
- Kafka compatible (Redpanda) : bus d’événements
- Postgres : états (workflows, orders, audit)
- Services :
  - Market Data API
  - Signal Engine (worker)
  - Risk Service (worker)
  - Workflow Orchestrator API
  - Paper OMS (worker)
  - GenAI Service API (RAG + LLM provider)
  - Notifier (worker)

## Flux principal “Trade Request”
1. Trader crée une demande (`workflow-api`)
2. `genai-service` produit une **revue** (RAG + LLM) et log l’audit
3. Approbations (Risk/Compliance) via API (human-in-the-loop)
4. `paper-oms` exécute en paper et publie `orders.filled`
5. `audit` centralisé

## Schémas (Mermaid)
```mermaid
sequenceDiagram
  participant T as Trader
  participant G as Gateway
  participant W as Workflow API
  participant K as Kafka
  participant A as GenAI API
  participant O as Paper OMS
  participant P as Postgres

  T->>G: POST /workflow/trade-requests
  G->>W: forward
  W->>P: insert workflow
  W->>K: publish workflow.requested
  K->>A: consume workflow.requested
  A->>P: insert audit(genai.review)
  A->>K: publish genai.review.created
  T->>G: POST /workflow/{id}/approve
  G->>W: forward
  W->>P: update status=APPROVED
  W->>K: publish workflow.approved
  K->>O: consume workflow.approved
  O->>P: insert order
  O->>K: publish orders.filled
```

