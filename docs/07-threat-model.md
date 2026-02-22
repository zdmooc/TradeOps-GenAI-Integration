# Threat model (résumé)

## Menaces principales
- Exfiltration de données via prompts (prompt injection)
- Utilisation non autorisée des APIs (tokens/keys)
- Altération d’audit trail
- Emission d’ordres “automatiques” par GenAI (interdit)

## Mesures
- GenAI: **read-only** (aucune capacité d’exécution)
- RAG: corpus contrôlé + citations + limite taille contexte
- Gateway: auth + rate limit + quotas
- Audit: hash SHA-256 stocké + event `audit.logged`
- Secrets: variables d’environnement / vault (à brancher)
