# Scénario 03 — Agentic AI, RAG et AI Access

**Mode : lecture d'architecture / preuves G1 et G2 datées.** Durée : 3 min.

## Architecture

```text
Agent Controller -> agents spécialisés / RAG-Qdrant / MCP
                             |
                          Risk Gate / HITL

TradeOps genai-api -> Shared Keycloak -> Kong -> AI Access policy
                                     -> LiteLLM -> Ollama/qwen2.5:3b
```

Les agents assistent, mais ne remplacent ni le calcul déterministe, ni le veto risque, ni la validation humaine.

## G1 et G2 : preuves séparées

- [G1 — chemin réel modèle gouverné](../../evidence/d090/20261007-g1-crc-runtime-proof.md) : OIDC + Kong + consommation réelle du modèle, re-PARK.
- [G2 — gouvernance mono-consommateur](../../evidence/d090/20261007-g2-crc-runtime-proof.md) : modèle non autorisé 403, quota/budget 429, OTel, métriques Prometheus/Thanos, restauration de policy, re-PARK.
- **Non prouvé live :** ODM second consumer G3, isolation inter-consommateurs G4, HA/production.

## À montrer

Ouvrir les preuves, le schéma applicatif du [dossier GenAI](../../docs/dossiers/README.md) et la distinction entre cockpit métier et métriques SRE. Aucun token OIDC, secret ni nouvelle inférence n'est déclenché dans la démo read-only.
