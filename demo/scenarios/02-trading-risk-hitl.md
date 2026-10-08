# Scénario 02 — Trading événementiel / Risk Gate / HITL

**Mode : lecture d'architecture et evidence historique par défaut.** Durée : 3 min.

## Chaîne produit

```text
Market Data -> Kafka compatible (Redpanda) -> signaux / agents
 -> Risk Gate déterministe (ACCEPT | VETO | REVIEW)
 -> REVIEW_REQUIRED -> APPROVE/REJECT par humain
 -> seulement si autorisé : SHADOW/PAPER -> audit
```

À montrer dans [le dossier GenAI](../../docs/dossiers/Dossier_TradeOps_GenAI_Agentic_MCP_IBM_MQ_Architecture_Runtime_20261008.pdf) et [le pack d'entretien I12](../../docs/22-interview-demo-pack.md). L'interface métier est [TradeOps Web Cockpit](../../docs/27-tradeops-web-cockpit.md).

## Preuves réelles vs incomplètes

- **Acquis :** build/UI/proxy/health, Route et `I9_CRC_VERIFY_PASS` lors de la capture datée du 13/09.
- **À prouver :** scénario live entier `REVIEW_REQUIRED -> humain APPROVE/REJECT -> SHADOW/PAPER -> audit` dans le CRC courant.
- **Hors périmètre :** argent réel, ordre envoyé à une bourse et P&L réel. Les outcomes de démonstration portent un label `DEMO_SYNTHETIC`.

Aucune action POST n'est exécutée par la présente démo. Ne pas utiliser les `scripts/demo_*.py` automatiquement : certains produisent des événements ou modifient l'état métier. Les scripts préexistants restent la source de vérité d'une future démonstration ACTIVE approuvée.
