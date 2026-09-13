# 02 — C4 et architecture logique

Cette page fournit les vues C4 essentielles : contexte, conteneurs logiques et déploiement.

## 1. C4 — System Context

```mermaid
flowchart LR
    TR[Trader / Analyst / Reviewer] --> T[TradeOps]
    OP[Platform / SRE] --> T
    DEV[Architect / Developer] --> T
    T --> MP[Market Data Provider / Replay Source]
    T --> IDP[Identity Provider - target]
    T --> AZ[Azure / ARO - target]
```

### Acteurs

- **Analyst** : consulte marché, signal et preuves.
- **Reviewer** : approuve/rejette les propositions éligibles.
- **SRE/Platform** : supervise OpenShift, métriques, traces et incidents.
- **Architect/Developer** : fait évoluer contrats, règles, modèles, manifests et evidence.

## 2. C4 — Container view

```mermaid
flowchart TB
    subgraph Presentation
      UI[tradeops-ui\nReact + TypeScript + Nginx]
    end

    subgraph APIs
      MD[market-data :8011]
      WF[workflow-api :8012]
      GA[genai-api :8013]
      RA[rag-api :8014]
      AC[agent-controller :8015]
      MCP[mcp-server :8016]
      RE[risk-engine]
      OMS[paper-oms]
      NT[notifier]
    end

    subgraph Data
      PG[(PostgreSQL)]
      Q[(Qdrant)]
      K[(Redpanda / Kafka API)]
    end

    subgraph Observability
      O[OTEL Collector]
      P[Prometheus]
      G[Grafana]
    end

    UI --> MD
    UI --> WF
    UI --> AC
    AC --> RA
    AC --> MCP
    AC --> RE
    AC --> WF
    MCP --> RE
    MCP --> OMS
    RA --> Q
    WF --> PG
    OMS --> PG
    MD --> K
    MD --> O
    WF --> O
    AC --> O
    O --> P
    P --> G
```

## 3. Responsabilités logiques

### Presentation

Le Web Cockpit présente le contexte métier et appelle uniquement trois backends autorisés via un reverse proxy same-origin. Il ne parle jamais directement à PostgreSQL, Redpanda, Qdrant ou MCP.

### Decision plane

`agent-controller` agrège les preuves et orchestre la décision, mais l’autorité finale reste distribuée :

- calculs déterministes dans les moteurs dédiés ;
- Risk Gate avec veto ;
- reviewer humain pour l’approbation ;
- Paper OMS pour l’exécution simulée.

### Knowledge plane

Le RAG apporte du contexte documentaire via Qdrant. Il ne devient pas une source d’autorité métier : une information récupérée peut être `UNKNOWN`, `CONFLICT` ou rejetée par la gouvernance RAG.

### Event plane

Redpanda fournit un bus Kafka compatible pour découpler la production et la consommation d’événements. Le bus transporte des faits/événements ; il ne doit pas devenir une base transactionnelle de substitution.

### Control plane

OpenShift, Helm, GitOps/Argo CD, NetworkPolicies, quotas, secrets, probes et observabilité constituent le plan de contrôle technique.

## 4. Architecture logique de décision

```mermaid
flowchart LR
    M[Market Evidence] --> F[Fusion]
    T[Technical Evidence] --> F
    P[Pattern Evidence] --> F
    X[Macro/RAG Evidence] --> F
    ML[ML Evidence] --> F
    R[Risk Evidence] --> F

    F -->|VETO / STALE / CONFLICT| N[NO_TRADE]
    F -->|SUPPORTED + gates OK| RR[REVIEW_REQUIRED]
    RR --> HR[Human Review]
    HR -->|REJECT| RJ[REJECTED]
    HR -->|APPROVE| EX{Mode}
    EX --> SH[EXECUTED_SHADOW]
    EX --> PA[EXECUTED_PAPER]
```

## 5. Vue de déploiement CRC

```mermaid
flowchart TB
    B[Browser] --> RTE[OpenShift Route\ntradeops-ui]
    RTE --> UI[tradeops-ui Pod]
    UI --> S1[market-data Service]
    UI --> S2[workflow-api Service]
    UI --> S3[agent-controller Service]

    subgraph CRC single node
      UI
      S1
      S2
      S3
      PG[(postgres-0)]
      Q[(qdrant-0)]
      RP[(redpanda-0)]
      OBS[Prometheus / Grafana / OTEL]
    end
```

Le CRC est un environnement de preuve mono-nœud. Il ne démontre pas une haute disponibilité de production ; il démontre la cohérence du packaging et du comportement applicatif.

## 6. Frontières de confiance

1. **Browser → UI** : frontière utilisateur.
2. **UI → APIs** : frontière applicative contrôlée par proxy et NetworkPolicy.
3. **Agent Controller → MCP** : frontière d’outillage gouvernée.
4. **MCP → Risk/OMS** : frontière d’action avec scopes.
5. **Reviewer → execution** : frontière humaine obligatoire.
6. **Namespace → infrastructure** : frontière OpenShift/RBAC/Secret/NetworkPolicy.

Ces frontières doivent rester visibles dans toute évolution vers Azure/ARO.
