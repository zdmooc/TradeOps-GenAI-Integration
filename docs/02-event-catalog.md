# Catalogue d’événements

Les schémas JSON Schema sont dans `schemas/events/*.schema.json`.

Topics (Kafka) :
- `market.prices` : publication prix OHLCV simulés
- `signals.generated` : signaux issus de la stratégie
- `risk.breach` : violation de règles de risque (kill-switch)
- `workflow.requested` : demande de trade créée
- `genai.review.created` : revue IA créée (RAG+LLM)
- `workflow.approved` : demande approuvée
- `orders.filled` : ordre exécuté en paper
- `audit.logged` : audit central (toutes décisions)

Règle : chaque événement doit inclure :
- `event_id` (uuid)
- `event_type`
- `occurred_at` (ISO8601)
- `correlation_id` (uuid) pour trace end-to-end
