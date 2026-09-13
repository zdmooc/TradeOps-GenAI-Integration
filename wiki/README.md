# Wiki source — TradeOps Architecture

Ce dossier est la **source versionnée** du Wiki d’architecture TradeOps.

Entrée principale : [Home.md](Home.md).

## Pourquoi conserver le Wiki dans le dépôt principal ?

Le Wiki GitHub natif utilise un dépôt Git séparé (`TradeOps-GenAI-Integration.wiki.git`). Conserver les sources ici permet :

- review par commit/PR ;
- CI et contrôle de liens futurs ;
- versioning avec le code ;
- restauration simple ;
- publication du même contenu vers le Wiki natif sans divergence.

## Pages

1. Vision et principes
2. C4 et architecture logique
3. Architecture applicative et services
4. Agentic AI / RAG / MCP
5. Risk / Fusion / HITL
6. EDA / Data / ML / Replay
7. Sécurité / Zero Trust
8. OpenShift / CRC / GitOps / RHOAI
9. Observabilité / Résilience / SLO
10. FinOps / GreenOps
11. Web Cockpit
12. Azure / ARO Target
13. ADR / Patterns / Anti-patterns
14. Demo Runbook / Evidence
15. Glossaire

## Publication GitHub Wiki

Le script `scripts/publish_wiki.sh` synchronise ce dossier vers le dépôt Wiki natif si celui-ci est activé et si l’utilisateur Git dispose des droits de push.

Le script ne contient aucun credential et n’exécute aucune action Azure.

## Gouvernance

Toute page doit préserver la distinction :

- `DESIGNED`
- `IMPLEMENTED`
- `TESTED`
- `DEPLOYED`
- `LIVE VERIFIED`
- `TARGET`

Les claims runtime doivent être soutenus par `evidence/`.
