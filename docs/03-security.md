# Sécurité (modèle simplifié)

## Objectifs
- AuthN/AuthZ au niveau Gateway
- Secrets hors code
- Traçabilité (audit) et non-répudiation basique (hash)

## Local (démo)
- Kong en mode “key-auth” (API key) + rate limiting
- Possibilité d’ajouter OIDC (Entra/Keycloak) en extension

## Données
- Principe : le GenAI **n’exécute jamais** d’ordre.
- Le RAG ne lit que des documents “internes” autorisés (corpus local).
- Les réponses GenAI doivent citer les sources internes (IDs de docs).

## Guardrails
- Allowlist d’outils/actions
- Vérification “prompt injection” simple sur les requêtes entrantes (exemple pédagogique)
