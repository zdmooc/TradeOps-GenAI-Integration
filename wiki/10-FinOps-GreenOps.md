# 10 — FinOps et GreenOps

## 1. Pourquoi les traiter dans l’architecture ?

Le coût et l’empreinte environnementale sont des **qualités d’architecture**, au même titre que la disponibilité ou la sécurité. Ils dépendent directement des choix de compute, stockage, durée de vie, modèles IA, réplication et observabilité.

## 2. FinOps

FinOps vise à rendre la consommation cloud visible, attribuable et optimisable.

### Principes appliqués

- tags obligatoires ;
- environnements de lab éphémères ;
- coût autorisé explicitement ;
- destroy rapide après preuve ;
- séparation ressources de fondation / ressources coûteuses ;
- mesure fournisseur avant toute affirmation de coût réel.

## 3. GreenOps

GreenOps vise à réduire l’impact environnemental du SI en reliant :

```text
architecture -> ressources -> utilisation -> énergie -> carbone
```

Une baisse de coût n’est pas automatiquement une baisse de carbone. Les deux doivent être mesurés ou qualifiés séparément.

## 4. Levers d’optimisation

### Right-sizing

Éviter CPU/RAM surdimensionnés. Observer l’utilisation avant de modifier les requests/limits.

### Scale-to-zero / extinction des labs

Un environnement de démonstration n’a pas besoin de fonctionner 24/7.

### Scheduling

Créer les ressources coûteuses uniquement pendant la fenêtre de lab.

### Model/runtime choice

Un modèle plus petit ou un runtime plus spécialisé peut consommer moins de mémoire/compute pour une qualité suffisante.

### Data lifecycle

Limiter rétention, duplication et stockage inutile tout en respectant audit/compliance.

## 5. Mesure Azure cible

La cible prévoit :

- Azure Cost Management pour les coûts réels ;
- Azure Carbon Optimization pour les données carbone disponibles ;
- inventaire/tagging de la resource group ;
- runtime window explicite ;
- réponses fournisseur redacted avant commit.

Les données carbone fournisseur peuvent être différées dans le temps ; un cluster créé aujourd’hui ne doit pas être présenté comme ayant une mesure carbone fournisseur disponible aujourd’hui si l’API ne la fournit pas.

## 6. Evidence attendue

### FinOps

- scope subscription/resource group ;
- resources/tags ;
- durée de vie ;
- coût mesuré ;
- principaux cost drivers ;
- confirmation de teardown ;
- décision d’optimisation.

### GreenOps

- boundary workload/platform ;
- région ;
- durée ;
- CPU/GPU/RAM/storage ;
- source carbone ou méthode d’estimation ;
- hypothèses/incertitude ;
- action d’optimisation ;
- comparaison avant/après uniquement si mesurée.

## 7. Leçons du CRC

Le problème d’ephemeral-storage rencontré sur le build runtime est aussi un signal GreenOps/FinOps : une image de build trop lourde augmente temps, I/O, stockage temporaire et consommation.

Optimisations possibles :

- séparer dépendances runtime/ML ;
- multi-stage builds ;
- image de base préconstruite/versionnée ;
- supprimer packages de test du runtime ;
- cache maîtrisé ;
- externaliser model serving vers RHOAI/KServe ;
- mesurer taille image et durée de build avant/après.

## 8. Etat actuel du gate

La résilience CRC est mesurée sur un cas stateless avec récupération d’environ 14,3 s contre une cible lab de 30 s. En revanche, coût Azure et carbone fournisseur restent non mesurés.

Ainsi le critère global `RESILIENCE_FINOPS_GREENOPS_VERIFIED` reste **PARTIAL**.

## 9. Architecture responsable

Une architecture IA d’entreprise doit répondre simultanément à :

- est-ce fiable ?
- est-ce sécurisé ?
- est-ce explicable ?
- combien cela coûte ?
- combien de ressources cela consomme ?
- peut-on l’éteindre ou le réduire lorsqu’il n’est pas utilisé ?

TradeOps traite ces questions comme des gates de graduation plutôt que comme une annexe marketing.
