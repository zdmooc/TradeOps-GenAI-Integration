# Runbooks (extraits)

## Incident: LLM provider indisponible
Symptômes : erreurs 5xx sur `/genai/*`, hausse latence.
Actions :
1) Basculer `LLM_PROVIDER=mock` (mode dégradé) via config.
2) Vérifier logs `genai-service`.
3) Continuer workflow avec règles déterministes (risk).

## Incident: backlog Kafka (consumers en retard)
Symptômes : délais sur approvals/exécutions.
Actions :
1) Vérifier `docker compose logs redpanda`
2) Vérifier nombre de consumers & lag
3) Scale-out workers (K8s) ou augmenter ressources local

## Incident: Postgres saturé
Actions :
1) Vérifier connexions/locks
2) Vérifier index (workflows/orders)
3) Augmenter pool / ressources
