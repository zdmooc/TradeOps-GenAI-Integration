# R3 — MCP natif sécurisé : identité, scopes et HITL

Statut : **IMPLEMENTED ON BRANCH / CI EVIDENCE PENDING**

## 1. Le problème métier

R1 et R2 ont appris à la plateforme à parler MCP. Mais un agent capable de découvrir un tool ne doit pas automatiquement avoir le droit de l'exécuter.

Il faut répondre à quatre questions :

1. **Qui appelle ?**
2. **Quels droits possède cet appelant ?**
3. **L'action nécessite-t-elle une validation humaine ?**
4. **Peut-on prouver après coup ce qui a été exécuté ?**

R3 apporte cette frontière.

```text
Utilisateur / service
        |
        v
Identity Provider
(Keycloak / Entra / autre)
        |
        | access token
        v
Agent Controller
   = MCP Host
        |
        | Bearer token
        v
Native MCP Server
   = OAuth Resource Server
        |
        +--> identité
        +--> scopes
        +--> ToolGovernor
        +--> HITL workflow check
        +--> audit
        |
        v
Tool métier
```

## 2. OAuth/OIDC : qui fait quoi ?

Le serveur MCP n'est pas le système qui connecte l'utilisateur et n'émet pas les tokens.

```text
Authorization Server / IdP
= authentifie et émet le token

MCP Server
= Resource Server
= vérifie le token

MCP Client
= présente le bearer token
```

Le SDK MCP publie aussi le Protected Resource Metadata nécessaire à la découverte OAuth sur le transport HTTP.

Dans le démonstrateur :

- `TRADEOPS_AUTH_MODE=static` permet un mode local simple ;
- `TRADEOPS_AUTH_MODE=oidc` réutilise la vérification JWT/JWKS existante ;
- `TradeOpsTokenVerifier` adapte cette identité au contrat `TokenVerifier` du SDK MCP v2.

## 3. Authentification n'est pas autorisation

Un token valide prouve une identité, mais le droit dépend du scope du tool.

### Agent Controller

Scopes typiques :

```text
market.read
risk.evaluate
workflow.read
```

Il peut analyser mais pas exécuter.

### Human Reviewer

Scopes supplémentaires :

```text
audit.read
paper.execute
```

Le `ToolGovernor` existant reste l'autorité déterministe :

```text
market.get_last_price -> market.read
risk.check_trade      -> risk.evaluate
oms.place_order       -> paper.execute + HITL
```

## 4. La règle la plus importante de R3

On ne fait PAS ceci :

```text
Agent -> oms.place_order(symbol, side, qty, human_approved=true)
```

`human_approved=true` est seulement une donnée envoyée par le caller. Un agent pourrait tenter de la fabriquer.

R3 fait ceci :

```text
Agent / Reviewer
       |
       | workflow_id uniquement
       v
oms.place_order(workflow_id)
       |
       v
Decision Store
       |
       +-- status == APPROVED ?
       +-- review == APPROVE ?
       +-- execution_mode == PAPER ?
       +-- risk_status == ACCEPT ?
       +-- approval non expirée ?
       |
       v
reconstruit côté serveur :
  symbol
  side
  qty
       |
       v
ToolGovernor
       |
       v
Paper OMS
```

Ainsi le modèle ne peut pas faire approuver :

```text
BUY DAX qty=2
```

puis modifier après approbation en :

```text
BUY DAX qty=200
```

Le tool MCP ne lui permet même pas de fournir `qty`.

## 5. Flux métier complet

```text
1. Agent analyse le marché
        |
2. risk.check_trade
        |
3. proposition de décision
        |
4. statut PENDING_REVIEW
        |
5. humain APPROVE / REJECT
        |
6. statut APPROVED
        |
7. endpoint /decision/{id}/execute
        |
8. Agent Controller utilise reviewer identity
        |
9. MCP oms.place_order(workflow_id)
        |
10. MCP relit le workflow APPROVED
        |
11. ToolGovernor vérifie paper.execute + HITL
        |
12. Paper OMS exécute
        |
13. workflow -> EXECUTED_PAPER
        |
14. audit
```

## 6. Découverte d'un tool != droit de l'utiliser

En R3 le serveur sécurisé peut annoncer :

```text
market.get_last_price
risk.check_trade
security.whoami
oms.place_order
```

Cela ne veut pas dire que l'Agent Controller peut appeler les quatre.

Un token agent sans `paper.execute` reçoit un refus déterministe pour `oms.place_order`.

C'est le même principe qu'un utilisateur qui voit qu'une API existe sans avoir le rôle permettant son utilisation.

## 7. Identité propagée

Le serveur MCP peut lire le principal validé par le bearer boundary avec `get_access_token()`.

Le tool `security.whoami` rend démontrable :

```text
subject
client_id
scopes
roles
authn_method
```

Cela permettra ensuite d'envoyer la même identité vers IBM MQ, OpenShift ou un SI métier sous une forme adaptée au système cible.

## 8. Audit

Chaque décision du `NativeMcpGovernor` écrit :

```text
tool
principal
allowed
policy_code
arguments redacted
result redacted
timestamp
correlation_id
```

Les secrets/tokens restent soumis au mécanisme de redaction existant.

## 9. Tests R3

`tests/test_mcp_security_r3.py` vérifie notamment :

- token agent valide ;
- token reviewer valide ;
- mauvais token rejeté ;
- agent sans `paper.execute` refusé ;
- workflow non approuvé refusé ;
- workflow approuvé accepté ;
- paramètres d'ordre dérivés du workflow et non fournis par le caller ;
- serveur pédagogique R1/R2 reste non mutateur ;
- serveur réseau sécurisé expose la mutation gouvernée.

## 10. Ce que R3 prouve / ne prouve pas encore

Après CI verte, R3 prouve au niveau code/test :

- intégration du `TokenVerifier` MCP v2 ;
- mapping identité TradeOps -> identité MCP ;
- scopes par tool ;
- séparation agent/reviewer ;
- HITL lié au workflow stocké ;
- mutation paper via MCP natif ;
- audit des décisions de gouvernance.

R3 ne prouve pas encore :

- Keycloak réellement déployé ;
- flux OAuth interactif complet ;
- rotation JWKS de production ;
- transport réseau MCP réellement exécuté sur CRC/OpenShift ;
- IBM MQ via MCP.

Ces preuves appartiennent à R4/R5.

## 11. Suite

```text
R1  MCP Server natif                    DONE
R2  Agent Controller = MCP Host         DONE
R3  OAuth/OIDC + scopes + HITL           <- ici
R4  IBM MQ / Payments MCP
R5  OpenShift CRC + evidence runtime
```
