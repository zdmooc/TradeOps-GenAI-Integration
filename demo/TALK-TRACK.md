# Présentation orale TradeOps — 15 minutes

## 0–2 min : pourquoi TradeOps ?

« TradeOps démontre une architecture de décision assistée pour un environnement de marché exigeant : flux événementiels, composantes déterministes, GenAI supervisée, Risk Gate et Human-in-the-Loop. Aucun ordre en argent réel n'est déclenché. »

Montrer les deux dossiers [OpenShift N3 et GenAI](../docs/dossiers/README.md).

## 2–5 min : plateforme CaaS / Day-2

« Le lab repose sur CRC mono-nœud. Aujourd'hui le produit est présenté dans son état PARK : les Deployments à zéro sont volontairement arrêtés ; les stores stateful sont conservés pour ne pas perdre les données du profil éphémère. Je sépare état souhaité, capacité, santé cluster et santé métier. »

Montrer le préflight, `oc get nodes` et les ressources `tradeops`. Ne pas annoncer les requests historiques comme métriques live.

## 5–7 min : GitOps et sécurité

« L'architecture combine namespaces, quotas, RBAC, SCC, NetworkPolicies, GitOps et observation d'un consumer Shared. Le consumer D-093 reste en Observe : pas de prise de contrôle implicite des objets brownfield. »

Montrer les CR et Applications sans drift artificiel.

## 7–10 min : chaîne métier

« Market Data -> événements -> signaux / analyse -> agents et RAG -> moteur de risque déterministe -> revue humaine -> SHADOW/PAPER -> audit. Le Risk Gate garde la décision de veto. La preuve de bout en bout HITL live doit encore être obtenue. »

Montrer le diagramme du dossier GenAI et `docs/22-interview-demo-pack.md`.

## 10–12 min : MCP IBM MQ

« Une campagne réelle R5 sur CRC a prouvé Agent Controller -> MCP natif -> mq-ops-api -> IBM MQ QM.MAYABANK, en lecture seule. La queue d'administration interdite a répondu 403. Le run s'est achevé en re-PARK. »

Ouvrir la preuve R5 du 08/10 ; ne pas relancer R5.

## 12–14 min : accès IA gouverné / observabilité

« En fenêtres distinctes, G1 a validé le modèle réel derrière OIDC/Kong/AI Access/LiteLLM/Ollama ; G2 a validé les refus de modèle/quota/budget et les traces/métriques. Cela ne prouve pas l'isolation multi-consommateurs G3/G4. »

Montrer les documents G1/G2 ; métriques instantanées uniquement si disponibles.

## 14–15 min : limites et synthèse

« J'expose des résultats reproductibles et leur périmètre, pas des claims de production : CRC mono-nœud, stockage local éphémère, HITL live incomplet, A2A live et D-090 G3/G4 non validés. »

Version longue : [I12 entretien 30 min](../docs/22-interview-demo-pack.md).
