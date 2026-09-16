# R4 — IBM MQ / Payments via MCP

Statut : **TESTED IN CI / CRC NETWORK EVIDENCE PENDING**

## 1. Pourquoi IBM MQ est ajouté

Kafka/Redpanda reste le bus événementiel de TradeOps. IBM MQ est ajouté pour démontrer une intégration d'entreprise avec un SI transactionnel de paiement existant.

R4 ne remplace pas Kafka par MQ :

```text
Kafka / Redpanda
= événements continus, streaming, signaux

IBM MQ
= messaging fiable du SI paiement
```

Le premier besoin n'est pas d'autoriser l'agent à modifier MQ. Il faut d'abord lui permettre d'observer un état opérationnel réel de façon gouvernée.

## 2. Architecture

```text
Agent Controller
      |
      | MCP client + agent bearer token
      v
TradeOps Native MCP
      |
      +-- OAuth/OIDC identity
      +-- scope mq.read
      +-- ToolGovernor
      +-- audit
      |
      | HTTP interne + service token
      v
MayaBank MQ Ops Adapter
      |
      | IBM MQ client, MQOO_INQUIRE only
      v
QM.MAYABANK
      |
      +-- PAYMENT.REQUEST.Q
      +-- PAYMENT.RESPONSE.Q
      +-- PAYMENT.DLQ
      +-- PAYMENT.BACKOUT.Q
```

Le code IBM MQ reste dans le dépôt `mayabank-ibm-mq-native-ha-openshift-eda-platform`. TradeOps ne reçoit pas les credentials du queue manager.

## 3. Tools MCP R4

### `mq.get_queue_status`

Entrée :

```json
{"queue": "PAYMENT.REQUEST.Q"}
```

Sortie attendue : profondeur courante, profondeur maximale, pourcentage d'occupation, handles input/output et inhibitions GET/PUT.

Le nom de queue est limité à l'allow-list des quatre queues paiement. Une queue système ou une queue de lab non autorisée est refusée.

### `payments.get_mq_health`

Pas d'argument.

Le tool lit les quatre queues puis applique une classification déterministe :

- `DEGRADED` si DLQ ou BACKOUT contient des messages ;
- `DEGRADED` si `PAYMENT.REQUEST.Q` atteint 80% de capacité ;
- `WARNING` à partir de 50% ;
- `WARNING` si REQUEST contient des messages mais aucun consumer ouvert ;
- sinon `HEALTHY`.

Le LLM ne décide pas de ces seuils : il reçoit le diagnostic déterministe et peut ensuite l'expliquer ou le corréler à d'autres faits.

## 4. Sécurité

R4 réutilise R3.

```text
agent bearer token
     |
     v
scope mq.read ?
   /       \
 NON       OUI
 DENY       |
            v
       ToolGovernor
            |
            v
       MQ adapter
```

Le scope `mq.read` est accordé à l'identité agent et reviewer dans le profil statique de démonstration. En OIDC, il doit venir du token/IdP.

Le token utilisé entre `mcp-native` et `mq-ops-api` est un secret de service séparé. Il n'est ni un token utilisateur ni le mot de passe IBM MQ.

## 5. API Host de démonstration

L'Agent Controller expose :

```text
GET /agent/mcp/mq/health
GET /agent/mcp/mq/queues/PAYMENT.REQUEST.Q
```

Ces routes ne parlent pas directement à IBM MQ. Elles suivent obligatoirement :

```text
Agent Controller -> MCP -> ToolGovernor -> MQ Ops Adapter -> IBM MQ
```

Cela permet de démontrer que MCP est bien la frontière d'intégration de l'agent.

## 6. Exemple métier

Situation : le traitement des paiements ralentit.

```text
PAYMENT.REQUEST.Q depth = 850 / 1000
open_input_count = 0
PAYMENT.DLQ = 0
PAYMENT.BACKOUT.Q = 0
```

Le diagnostic déterministe retourne :

```text
DEGRADED
- PAYMENT.REQUEST.Q >= 80%
- messages présents mais aucun consumer ouvert
```

L'agent pourra ensuite rapprocher ce constat d'OpenShift, du RAG/runbook et des événements du SI.

R4 ne redémarre rien et ne purge rien.

## 7. Preuve CI obtenue

La CI TradeOps est verte sur le code R4 :

- installation Python ;
- Ruff ;
- audit sécurité ;
- contrôle SBOM ;
- validation documentation ;
- build frontend ;
- Helm lint/template ;
- validateurs plateforme ;
- Terraform fmt/init/validate ;
- `pytest -q`, y compris les tests R4.

R4 est donc `TESTED IN CI` pour :

- allow-list de queues ;
- `mq.read` et refus sans scope ;
- classification HEALTHY/WARNING/DEGRADED ;
- câblage MCP/Host ;
- routes Agent Controller de démonstration.

La CI du dépôt MQ valide séparément la compilation Java réelle avec `com.ibm.mq.allclient 9.4.5.1` et les tests unitaires du MQ Ops Adapter.

R4 ne sera pas `DEPLOYED/VERIFIED` tant que CRC n'aura pas produit une preuve réelle de :

```text
Agent Controller
 -> mcp-native
 -> mq-ops-api.mayabank-mq-local.svc
 -> QM.MAYABANK
 -> CURDEPTH réel
```

Cette preuve appartient à R5.

## 8. Suite

```text
R1  MCP Server natif                         DONE
R2  Agent Controller = MCP Host              DONE
R3  OAuth/OIDC + scopes + HITL               DONE
R4  IBM MQ / Payment observability via MCP   TESTED IN CI
R5  CRC/OpenShift network + runtime evidence NEXT
```
