# R1 — MCP natif : fondamentaux et première implémentation

Statut : **IMPLEMENTED ON BRANCH / CI EVIDENCE PENDING**

## 1. Le problème que MCP résout

Un LLM sait traiter du langage mais ne doit pas accéder directement et librement au SI.
Un agent ajoute un objectif, un état, des règles et une capacité à utiliser des outils.
MCP standardise la frontière entre l'application agentique et les outils/données.

```text
User
  |
  v
Agent / LangGraph
  |
  | MCP Client
  v
MCP Server
  +-- tools
  +-- resources
  +-- prompts
  |
  v
Enterprise systems / APIs / data
```

Analogie : MCP joue le rôle d'une prise standard. Le système métier peut changer derrière le serveur MCP sans obliger chaque agent à réinventer une API propriétaire.

## 2. Les rôles

### MCP Host

L'application IA qui orchestre l'expérience. Dans notre cible, `agent-controller` joue ce rôle logique.

### MCP Client

Le composant du host qui parle le protocole MCP à un serveur. Le SDK officiel Python fournit `mcp.Client`.

### MCP Server

Le service qui publie des capacités standardisées. R1 ajoute `services/mcp_native/server.py`.

## 3. Les trois primitives serveur

### Tool

Action que le modèle peut demander.

R1 :

- `market.get_last_price(symbol)`
- `risk.check_trade(symbol, side, qty)`

Un tool ressemble conceptuellement à une opération API. Il peut être read-only ou avoir des effets de bord. Les outils mutateurs demandent davantage de contrôles.

### Resource

Information chargée comme contexte par l'application.

R1 :

- `tradeops://policy/risk`

Cette ressource expose la politique de risque de démonstration sous forme de données, pas comme une action.

### Prompt

Modèle de consigne réutilisable.

R1 :

- `analyze_trade(symbol, side, qty)`

Le prompt n'exécute pas lui-même un trade. Il prépare une consigne gouvernée.

## 4. Ancien chemin vs MCP natif

Avant R1 :

```text
agent-controller
  -> HTTP POST /call
  -> JSON maison {tool, arguments, human_approved, ...}
  -> FastAPI mcp-server
  -> ToolGovernor
  -> fonction Python
```

Ce chemin est utile et sécurisé mais le contrat réseau est spécifique à TradeOps.

R1 :

```text
MCP Client
  -> protocole MCP officiel
  -> tools/list / tools/call / resources/read / prompts/get
  -> MCPServer
  -> fonctions Python existantes
```

Le protocole, la découverte et les schémas ne sont plus inventés par TradeOps.

## 5. Pourquoi R1 reste read-only/evaluate

`oms.place_order` n'est volontairement PAS publié par le serveur MCP natif R1.

Raison : une capacité mutatrice ne doit pas être rendue disponible avant d'avoir branché sur le chemin MCP natif :

1. authentification OAuth/OIDC ;
2. identité du caller ;
3. scopes/least privilege ;
4. ToolGovernor ;
5. HITL ;
6. audit/correlation ;
7. tests négatifs.

Le système existant garde son chemin gouverné pour le paper order jusqu'à R2/R3.

## 6. Transport

R1 expose le serveur sur :

```text
http://localhost:8017/mcp
```

avec **Streamable HTTP**.

Le transport est la façon dont les messages MCP circulent. Il ne change pas la sémantique des tools/resources/prompts.

## 7. Comment le tester manuellement

Installer les dépendances puis lancer :

```bash
python -m services.mcp_native.server
```

Dans un deuxième terminal :

```bash
python -m services.mcp_native.client_smoke
```

Le client doit :

1. découvrir les tools ;
2. découvrir les resources ;
3. découvrir les prompts ;
4. appeler `market.get_last_price` ;
5. appeler `risk.check_trade` ;
6. lire la politique de risque ;
7. récupérer le prompt `analyze_trade`.

## 8. Ce que le test automatique prouve

`tests/test_mcp_native_r1.py` utilise `Client(mcp)` directement en mémoire.

Cela prouve :

- serveur importable ;
- protocole MCP géré par le SDK officiel ;
- découverte des primitives ;
- invocation structurée des tools ;
- lecture d'une resource ;
- récupération d'un prompt ;
- absence de `oms.place_order` dans R1.

Cela ne prouve PAS encore :

- déploiement HTTP réel ;
- OAuth/OIDC ;
- OpenShift ;
- identité propagée ;
- IBM MQ via MCP ;
- mutation/HITL via MCP natif.

## 9. Roadmap pédagogique suivante

### R2 — MCP client dans Agent Controller

Remplacer un premier appel HTTP propriétaire par le client MCP officiel et expliquer le flux complet.

### R3 — OAuth/OIDC et ToolGovernor

Protéger le MCP natif comme Resource Server, récupérer l'identité du caller et réutiliser les politiques existantes.

### R4 — MCP Payments / IBM MQ

Publier des outils métier read-only tels que profondeur de queue, statut channel et lookup paiement, puis une mutation contrôlée uniquement après HITL.

### R5 — OpenShift + evidence

Déployer le chemin natif sur CRC/OpenShift, capturer pods/routes/tests/audit et produire le scénario d'entretien.
