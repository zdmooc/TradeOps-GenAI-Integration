# Contexte & positionnement “Consultant Integration AI”

Le projet simule un SI trading “paper” où l’on doit intégrer des briques IA/GenAI au cœur des processus :
- **Briefing** (GenAI) : synthèse des marchés + positions + règles internes
- **Trade Review** (GenAI + RAG) : justification et contrôle avant exécution
- **Workflow** : demande → revue → approbations → exécution
- **Event-driven** : traçabilité, découplage, scalabilité
- **Run** : observabilité, SLO, runbooks, audit

Ce repo met l’accent sur l’**intégration** (API/event/workflow) et l’**industrialisation** (sécurité/robustesse/run),
pas sur l’optimisation d’une stratégie de trading.
