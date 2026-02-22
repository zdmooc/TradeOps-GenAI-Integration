# SLO / SLA (démo)

## Services API
- Disponibilité (rolling 30j) : 99.5%
- Latence p95 : < 500ms (hors appels LLM externes)
- Taux d’erreur 5xx : < 0.5%

## Workflows
- Temps “request → review IA” : < 30s (mode mock) / < 2 min (LLM externe)
- Temps “approved → order filled” : < 10s (paper)

## Alertes (exemples)
- p95 latence > 1s sur 5 min
- taux 5xx > 2% sur 5 min
- absence d’événements `orders.filled` pendant 30 min (si trafic attendu)
