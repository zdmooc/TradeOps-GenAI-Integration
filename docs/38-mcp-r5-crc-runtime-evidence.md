# R5 — CRC runtime : MCP natif -> IBM MQ réel

Statut : **CRC_RUNTIME_PROVEN / LIVE_OPERATIONAL — R5 functional gates CLOSED (2026-10-08)**. L'archivage du bundle brut de preuve, actuellement local, reste une tâche documentaire séparée.

## 1. But

R1 à R4 ont prouvé le protocole, le Host MCP, la sécurité et le contrat IBM MQ en CI. R5 doit prouver la chaîne réellement déployée sur OpenShift Local/CRC :

```text
Utilisateur / curl
      |
      v
Agent Controller :8015
      |
      | MCP client + bearer agent
      v
mcp-native :8017/mcp
      |
      +-- OAuth/static identity
      +-- scope mq.read
      +-- ToolGovernor
      +-- audit
      |
      | HTTP interne + service token
      v
mq-ops-api.mayabank-mq-local.svc:8080
      |
      | IBM MQ INQUIRE only
      v
QM.MAYABANK
      |
      +-- PAYMENT.REQUEST.Q
      +-- PAYMENT.RESPONSE.Q
      +-- PAYMENT.DLQ
      +-- PAYMENT.BACKOUT.Q
```

Kafka/Redpanda reste le bus de streaming de TradeOps. IBM MQ reste le SI de messaging paiement. MCP est la frontière standard utilisée par l'agent.

## 2. Corrections de déploiement apportées par R5

R5 matérialise ce qui n'existait auparavant qu'au niveau code :

- `mcp-native` devient un workload Helm/OpenShift réel ;
- l'Agent Controller reçoit `MCP_NATIVE_URL=http://mcp-native:8017/mcp` ;
- le serveur MCP reçoit le service token de l'adaptateur MQ depuis Secret ;
- le chart utilise un probe TCP pour le serveur MCP plutôt qu'un faux `/health` ;
- une NetworkPolicy TradeOps autorise uniquement `mcp-native` vers `mq-ops-api:8080` ;
- la NetworkPolicy MayaBank accepte exactement le label Helm `app.kubernetes.io/name: mcp-native` ;
- l'image Java MayaBank est reconstruite depuis le code courant avant déploiement de `mq-ops-api`.

## 3. Secrets

Aucun secret R5 n'est commité.

Le lanceur réutilise d'abord les Secrets déjà présents dans CRC :

```text
tradeops/tradeops-runtime-secrets
mayabank-mq-local/mq-ops-api-credentials
```

S'il manque une valeur strictement locale, il la génère avec `openssl rand` sans l'afficher. Le même service token est propagé des deux côtés :

```text
TradeOps Secret key: MQ_OPS_API_TOKEN
MayaBank Secret key: token
```

Le mot de passe IBM MQ n'est jamais transmis à TradeOps.

Le Secret `tradeops-runtime-secrets` est traité par **merge**, jamais recréé intégralement : les clés D-090 AI/OIDC/LiteLLM déjà prouvées par G1/G2 doivent rester intactes.

## 4. Preuve CI acquise

Le head R5 a passé :

- installation Python ;
- Ruff ;
- audit sécurité ;
- contrôle SBOM ;
- validation documentation ;
- syntaxe de tous les scripts CRC R5 avec `bash -n` ;
- build frontend ;
- `helm lint` ;
- `helm template` avec les valeurs CRC ;
- validation plateforme I9 incluant désormais `mcp-native` ;
- validateurs I10/I13 ;
- Terraform fmt/init/validate ;
- validateurs I11/I12 ;
- totalité de `pytest -q`, y compris les tests de packaging R5.

Cette preuve justifie **TESTED IN CI**. Elle ne prouve pas que ton CRC local a déjà exécuté la chaîne.

## 5. Une commande pour déployer et vérifier

Préconditions : CRC/OpenShift déjà démarré et les deux dépôts présents côte à côte, par exemple :

```text
C:/workspaces/TradeOps-GenAI-Integration
C:/workspaces/mayabank-ibm-mq-native-ha-openshift-eda-platform
```

Depuis `TradeOps-GenAI-Integration` :

```bash
bash scripts/r5_crc_mcp_mq_run.sh
```

Si un snapshot PARK actif existe, le lanceur sélectionne automatiquement :

```text
R5_CRC_RUN_MODE=BOUNDED_FROM_PARK
```

et délègue à `scripts/crc/r5_crc_mcp_mq_from_park.sh`.

Dans ce mode, R5 :
- exige que `CapabilityConsumption/tradeops-crc` reste en `Observe` ;
- ne fait **aucun Helm upgrade complet** de TradeOps ;
- réutilise l'image `tradeops-runtime:i9` si elle contient déjà `services.mcp_native`, sinon ne reconstruit que cette image runtime ;
- rend/applique uniquement `mcp-native` depuis le chart ;
- réveille temporairement seulement `agent-controller` + `mcp-native` ;
- merge uniquement la clé `MQ_OPS_API_TOKEN` dans le Secret TradeOps et vérifie que toutes les autres clés restent bit-à-bit identiques ;
- laisse PostgreSQL, Redpanda/Kafka, Qdrant, RAG, UI, Grafana et les autres Deployments dans leur état PARK ;
- exécute la preuve R5 ;
- re-PARK `agent-controller` et retire `mcp-native` s'il n'existait pas dans le snapshot initial.

Le marqueur de sécurité final du mode borné est :

```text
R5_CRC_WINDOW_REPARK=PASS
```

Si le dépôt MQ est ailleurs :

```bash
MQ_REPO=/c/workspaces/mayabank-ibm-mq-native-ha-openshift-eda-platform \
  bash scripts/r5_crc_mcp_mq_run.sh
```

## 6. Ce que la vérification exige réellement

Le script ne valide pas seulement la disponibilité des pods.

### Gate A — MCP natif

`GET /agent/mcp/capabilities` doit annoncer :

```text
mq.get_queue_status
payments.get_mq_health
```

### Gate B — diagnostic IBM MQ via MCP

`GET /agent/mcp/mq/health` doit produire un payload :

```text
source = ibm-mq
qmgr = QM.MAYABANK
status = HEALTHY | WARNING | DEGRADED
```

### Gate C — vérité indépendante du CURDEPTH

Le même `PAYMENT.REQUEST.Q` est lu deux fois par deux chemins différents :

```text
Agent Controller -> MCP -> mq-ops-api -> IBM MQ
```

et :

```text
oc exec deployment/mq -> runmqsc QM.MAYABANK
```

Le script exige un `CURDEPTH` identique. Il réessaie jusqu'à trois observations rapprochées pour éviter qu'une queue active ne change entre deux lectures.

### Gate D — queue interdite

Une tentative vers :

```text
SYSTEM.ADMIN.COMMAND.QUEUE
```

doit être refusée.

### Gate E — impossible de contourner MCP

`agent-controller` tente directement une connexion TCP vers `mq-ops-api:8080`. Elle doit échouer par NetworkPolicy. Seul `mcp-native` possède l'egress inter-namespace.

## 7. Evidence bundle

En cas de succès :

```text
evidence/r5/live/crc/<timestamp>/
```

contient notamment :

```text
00-summary.txt
04-tradeops-runtime.txt
05-mayabank-runtime.txt
06-tradeops-networkpolicies.yaml
07-mayabank-networkpolicies.yaml
11-mcp-capabilities.json
12-mq-health-via-mcp.json
13-request-queue-via-mcp.json
14-request-queue-runmqsc.txt
15-depth-comparison.txt
17-negative-tool-policy.txt
18-direct-bypass-attempt.txt
19-mcp-native.log
20-agent-controller.log
21-mq-ops-api.log
```

Le marqueur final attendu est :

```text
R5_CRC_MCP_MQ_VERIFY_PASS
```

et `00-summary.txt` doit contenir :

```text
verification=R5_CRC_MCP_MQ_VERIFY_PASS
evidence_class=LIVE_OPERATIONAL
```

## 8. Preuve live observée — 8 octobre 2026

**Périmètre : OpenShift Local/CRC 4.22.7 mono-nœud, scénario R5 borné depuis PARK.** La sortie de la campagne finale exécutée localement rapporte :

- base Git vérifiée : `33a1faf1cd5ee4779b7ce717fe5c41bc8bd3a79b`, fusion de la PR #21 ;
- CI de la PR #21 : workflow `ci` / job `lint-test` **SUCCESS**, run `37796874524` ;
- build OpenShift `tradeops-runtime-16` depuis ce commit, image `tradeops-runtime:i9` publiée avec digest `sha256:5a174f53bf895ddf6f458bb37d64e5de76f74b79749b8865156cf2651b58df34` ;
- réutilisation de l'image publiée lors de la campagne finale (pas de nouveau build automatique) ;
- `MCP_TOOLS_PASS` et `MQ_HEALTH_PAYLOAD_PASS` : invocation MCP réelle vers l'adaptateur MayaBank `mq-ops-api` puis `QM.MAYABANK` ;
- `R5_FORBIDDEN_QUEUE_POLICY_PASS` : `SYSTEM.ADMIN.COMMAND.QUEUE` reçoit **HTTP 403** avec message explicite `queue is not allowed` (PR #21) ;
- comparaison `PAYMENT.REQUEST.Q` via MCP et `runmqsc` : contrôle de parité obligatoire franchi ;
- contournement TCP direct `agent-controller -> mq-ops-api` : test négatif franchi, sans autorisation d'un accès direct ;
- `R5_CRC_MCP_MQ_VERIFY_PASS`, `R5_CRC_FROM_PARK=PASS`, `R5_CRC_WINDOW_REPARK=PASS` ;
- D-093 `CapabilityConsumption/tradeops-crc` maintenu en **Observe**, sans autoriser `Manage`.

Bundle local déclaré par la commande : `evidence/r5/live/crc/20261008T154626Z/`.
Ce dossier **n'est pas automatiquement présent dans Git** : son archivage contrôlé requiert une inspection/redaction des logs, manifeste Secret, éventuels tokens et identifiants avant tout commit. La présente note versionnée documente les résultats observés, sans prétendre embarquer le bundle brut.

**Limites des claims :** intégration read-only MCP → IBM MQ prouvée sur CRC mono-nœud seulement. Ni haute disponibilité, ni production, ni déploiement multi-cluster, ni interopérabilité A2A live, ni isolation D-090 G3/G4, ni promotion D-093 `Manage` ne sont revendiquées. Le `R5_CRC_WINDOW_REPARK=PASS` atteste le retour en PARK prévu par le script.

## 9. Suite après R5

Une fois cette lecture IBM MQ réellement prouvée, l'itération suivante pourra enrichir le diagnostic avec OpenShift et RAG :

```text
MQ backlog
 +
OpenShift pod/metrics
 +
runbook RAG
 ->
Agentic incident diagnosis
 ->
proposition de remédiation
 ->
HITL
```

Aucune mutation IBM MQ n'est ajoutée par R5.
