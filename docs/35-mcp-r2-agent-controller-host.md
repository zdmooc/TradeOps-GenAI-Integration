# R2 — Agent Controller comme MCP Host

Statut : **IMPLEMENTED ON BRANCH / CI EVIDENCE PENDING**

## 1. Le changement mental

R1 a créé un vrai serveur MCP. R2 apprend maintenant à l'Agent Controller à parler ce protocole.

```text
User
  |
  v
Agent Controller  = MCP Host
  |
  +-- LangGraph
  |
  +-- MCP Client officiel
          |
          v
     MCP Server natif
       +-- market.get_last_price
       +-- risk.check_trade
```

Le Host est l'application IA qui pilote l'expérience. Le Client MCP est la bibliothèque embarquée dans ce Host. Le Server MCP publie les capacités.

## 2. Ce que R2 fait réellement

L'Agent Controller peut maintenant :

1. découvrir les tools/resources/prompts du serveur MCP ;
2. vérifier que les tools requis sont présents ;
3. appeler `market.get_last_price` ;
4. appeler `risk.check_trade` ;
5. construire un contexte structuré pour la suite du raisonnement ;
6. refuser le chemin si `oms.place_order` apparaît prématurément dans le serveur natif.

Endpoints pédagogiques :

```text
GET  /agent/mcp/capabilities
POST /agent/mcp/context
```

Exemple :

```json
{
  "symbol": "CAC40",
  "side": "BUY",
  "qty": 10
}
```

Réponse logique :

```json
{
  "source": "native-mcp",
  "symbol": "CAC40",
  "side": "BUY",
  "qty": 10,
  "market": {"symbol": "CAC40", "last": 123.4},
  "risk": {"passed": true, "violations": []},
  "risk_status": "ACCEPT",
  "risk_reasons": [],
  "tools_used": ["market.get_last_price", "risk.check_trade"]
}
```

## 3. Pourquoi il n'y a toujours pas d'ordre via MCP natif

Analyser n'est pas agir.

```text
READ / EVALUATE
market.get_last_price
risk.check_trade
       |
       v
autorisé en R2

MUTATE
oms.place_order
       |
       v
interdit jusqu'à R3
```

Avant d'exposer une mutation, le chemin MCP natif doit recevoir :

- authentification OAuth/OIDC ;
- identité du caller ;
- scopes / least privilege ;
- réutilisation du ToolGovernor ;
- HITL ;
- audit et correlation ID ;
- tests négatifs.

## 4. Lancer localement

R2 fournit un override Compose pour ne pas perturber la stack historique :

```bash
docker compose -f docker-compose.yml -f docker-compose.mcp.yml up --build mcp-native agent-controller
```

Le serveur MCP natif écoute sur :

```text
http://localhost:8017/mcp
```

L'Agent Controller écoute sur :

```text
http://localhost:8015
```

Test de contexte :

```bash
curl -X POST http://localhost:8015/agent/mcp/context \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"CAC40","side":"BUY","qty":10}'
```

## 5. Ce que R2 prouve

Si les tests passent, R2 prouve :

- l'Agent Controller contient un client MCP officiel ;
- la découverte MCP fonctionne ;
- l'appel de tools structurés fonctionne ;
- le contrat HTTP du Host reste séparé du protocole MCP interne ;
- la mutation paper reste hors du chemin natif.

R2 ne prouve pas encore : OAuth/OIDC, identité propagée, ToolGovernor sur MCP natif, IBM MQ, OpenShift ou déploiement réseau réel.

## 6. Suite

```text
R1  MCP Server natif
R2  Agent Controller = MCP Host      <- ici
R3  OAuth/OIDC + ToolGovernor + HITL
R4  IBM MQ / Payments MCP
R5  OpenShift CRC + evidence
```
