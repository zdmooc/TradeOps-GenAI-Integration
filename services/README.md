# Services

- `market_data`: API prix + publication d'événements
- `workflow_api`: orchestration des demandes et approvals
- `genai_api`: RAG + LLM adapter, consomme `workflow.requested`
- `signal_engine`: consomme `market.prices` -> produit `signals.generated`
- `risk_engine`: consomme `signals.generated` -> produit `risk.breach` (si besoin)
- `paper_oms`: consomme `workflow.approved` -> exécute paper -> `orders.filled`
- `notifier`: consomme événements et log (simulateur notification)
