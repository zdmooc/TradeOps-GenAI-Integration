# 15 — Glossaire des concepts d’architecture

## Architecture

**C4 Model** — méthode de représentation en niveaux : System Context, Containers, Components, Deployment.

**NFR (Non-Functional Requirement)** — exigence portant sur disponibilité, sécurité, performance, auditabilité, coût, etc.

**ADR (Architecture Decision Record)** — trace structurée d’une décision d’architecture.

**Blast radius** — étendue de l’impact possible d’une panne ou compromission.

**Fail closed** — en cas d’incertitude ou d’erreur, refuser l’action plutôt que l’autoriser implicitement.

## API / Event-Driven

**API** — contrat synchrone permettant à un client d’appeler un service.

**Event** — fait métier/technique immuable décrivant quelque chose qui s’est produit.

**EDA** — architecture pilotée par événements.

**Topic** — canal logique Kafka/Redpanda.

**Partition** — unité d’ordre local et de parallélisme dans Kafka.

**Consumer Group** — groupe de consommateurs partageant les partitions.

**Offset** — position de lecture dans un log Kafka.

**Idempotence** — propriété garantissant qu’une répétition n’ajoute pas un effet métier supplémentaire.

**Replay** — rejeu d’événements/données passées dans la logique actuelle.

## Data

**OLTP** — stockage transactionnel orienté cohérence et opérations métier ; PostgreSQL joue ce rôle ici.

**Vector Database** — stockage indexant des vecteurs pour recherche par similarité ; Qdrant joue ce rôle.

**Embedding** — représentation vectorielle d’un texte ou objet.

**Provenance** — origine et lineage d’une donnée ou preuve.

**Event time** — moment où le fait s’est produit.

**Ingest time** — moment où le système a reçu le fait.

## ML

**Feature** — variable disponible au moment de la prédiction.

**Label** — résultat cible utilisé pour apprendre/évaluer.

**Inference** — utilisation d’un modèle entraîné pour produire une sortie.

**Calibration** — alignement entre score probabiliste annoncé et fréquence empirique observée.

**Out-of-sample (OOS)** — évaluation sur données non utilisées pour entraîner le modèle.

**Walk-forward** — évaluation chronologique qui réentraîne/avance dans le temps sans fuite future.

**Data leakage** — utilisation involontaire d’informations indisponibles au moment réel de la décision.

**Drift** — évolution des données ou performances du modèle dans le temps.

## GenAI / RAG / Agents

**LLM** — Large Language Model.

**RAG** — Retrieval-Augmented Generation : récupération de contexte documentaire avant génération/raisonnement.

**Prompt Injection** — contenu visant à détourner les instructions ou outils d’un agent/LLM.

**Agent** — composant orienté objectif/rôle, capable d’interpréter un état et éventuellement d’appeler des outils autorisés.

**Agent orchestration** — coordination de plusieurs étapes/agents avec état explicite.

**LangGraph** — framework utilisé dans TradeOps pour l’orchestration par graphe d’état.

**MCP** — Model Context Protocol ; dans TradeOps, frontière gouvernée d’accès à des outils/contextes.

**Tool call** — invocation structurée d’une capacité externe par un agent.

**Grounding** — fait d’appuyer une sortie sur un contexte/source explicite.

## Decision / Risk

**Risk Gate** — point de contrôle déterministe capable d’interdire la suite.

**VETO** — interdiction terminale issue d’une règle dure.

**Fusion** — combinaison gouvernée de plusieurs preuves.

**SUPPORTED** — preuves compatibles avec une proposition ; ne signifie pas ordre autorisé.

**UNKNOWN** — preuves insuffisantes.

**DATA_STALE** — preuve fondée sur une donnée trop ancienne.

**CONFLICT** — preuves ou contexte contradictoires/non fiables.

**HITL** — Human-in-the-Loop : intervention humaine explicite dans le workflow de décision.

**Segregation of Duties** — séparation des responsabilités/permissions entre acteurs.

## Trading demo modes

**Backtest** — simulation d’une stratégie sur historique.

**SHADOW** — décision complète enregistrée sans ordre simulé/réel.

**PAPER** — exécution simulée via un OMS fictif.

**Real execution** — exécution sur argent réel ; hors scope TradeOps.

**R/R (Risk/Reward)** — rapport entre perte potentielle et gain potentiel selon stop/target.

**Expectancy** — espérance moyenne d’un setup calculée sur un échantillon défini.

## Kubernetes / OpenShift

**Pod** — unité d’exécution Kubernetes.

**Deployment** — contrôleur de workloads stateless.

**StatefulSet** — contrôleur pour workloads stateful avec identité stable.

**Service** — adresse réseau stable vers des pods.

**Route** — exposition HTTP(S) OpenShift.

**ImageStream** — abstraction/référence d’images dans OpenShift.

**BuildConfig** — description d’un build OpenShift.

**SCC** — Security Context Constraints OpenShift.

**NetworkPolicy** — règles de communication réseau entre pods/namespaces.

**ResourceQuota** — plafond de ressources au niveau namespace.

**LimitRange** — limites/défauts de ressources pour pods/containers.

**Probe** — test startup/readiness/liveness effectué par Kubernetes.

**CRC / OpenShift Local** — OpenShift local mono-nœud pour développement/lab.

**ARO** — Azure Red Hat OpenShift.

## GitOps / Delivery

**CI** — intégration continue : build, tests, qualité, sécurité.

**CD** — livraison/déploiement continu.

**GitOps** — Git comme état désiré, réconcilié automatiquement par un contrôleur.

**Argo CD** — contrôleur GitOps utilisé dans le modèle TradeOps.

**Drift** — écart entre l’état désiré Git et l’état réel cluster.

**SBOM** — Software Bill of Materials : inventaire des composants logiciels.

## Observabilité / Résilience

**OpenTelemetry (OTEL)** — standard de télémétrie traces/metrics/logs.

**Prometheus** — collecte/stockage de métriques time-series.

**Grafana** — visualisation/dashboards.

**SLI** — indicateur mesuré.

**SLO** — objectif de fiabilité interne.

**SLA** — engagement contractuel.

**RTO** — temps maximal de reprise visé.

**RPO** — perte de données maximale admissible.

**Circuit Breaker** — stoppe temporairement les appels vers une dépendance en échec.

**Bulkhead** — isolation visant à limiter la propagation d’une panne.

## Cloud / FinOps / GreenOps

**Landing Zone** — socle cloud gouverné : identité, réseau, sécurité, logs, politiques.

**Managed Identity** — identité Azure gérée sans secret applicatif classique.

**Workload Identity** — fédération permettant à un workload d’obtenir une identité cloud.

**Key Vault** — gestion de secrets/clefs/certificats Azure.

**FinOps** — discipline de visibilité, allocation et optimisation des coûts cloud.

**GreenOps** — optimisation de l’impact environnemental des workloads numériques.

**Right-sizing** — ajustement des ressources à l’utilisation réelle.

**Scale-to-zero** — arrêt/réduction à zéro lorsqu’un service n’est pas utilisé.

## Evidence

**DESIGNED** — architecture documentée.

**IMPLEMENTED** — artefact présent dans le code.

**TESTED** — test automatisé ou manuel réussi.

**DEPLOYED** — ressource effectivement installée.

**LIVE VERIFIED** — comportement observé sur l’environnement réel concerné.

Ces termes ne doivent jamais être utilisés comme synonymes.
