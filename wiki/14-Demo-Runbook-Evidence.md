# 14 — Demo Runbook, exploitation et Evidence

## 1. Objectif

Cette page décrit comment démontrer TradeOps sans sur-vendre ce qui n’est pas prouvé.

## 2. Pré-check CRC

Vérifier :

```text
CRC VM: Running
OpenShift: Running
namespace: tradeops
DiskPressure: False
```

Puis exécuter le script officiel :

```bash
bash scripts/i9_crc_verify.sh
```

Résultat attendu :

```text
TRADEOPS_UI_URL=https://tradeops-ui-tradeops.apps-crc.testing
I9_CRC_VERIFY_PASS
```

## 3. URLs LIVE

| Composant | URL |
|---|---|
| Web Cockpit | `https://tradeops-ui-tradeops.apps-crc.testing` |
| Agent Controller | `https://agent-controller-tradeops.apps-crc.testing` |
| Workflow API | `https://workflow-api-tradeops.apps-crc.testing` |
| Grafana | `https://grafana-tradeops.apps-crc.testing` |
| OpenShift Console | `https://console-openshift-console.apps-crc.testing` |

Les autres services sensibles restent internes.

## 4. Parcours de démonstration architecture

### Etape A — Cockpit

Montrer :

- données/context marché ;
- signal et R/R ;
- provenance DEMO/API ;
- evidence agents ;
- Risk Gate.

### Etape B — HITL

Objectif de preuve restant :

```text
Create proposal
  -> REVIEW_REQUIRED
  -> human APPROVE or REJECT
  -> if approved: SHADOW or PAPER
  -> audit visible
```

Ne jamais coller les tokens Agent/Reviewer dans un ticket, capture publique ou fichier evidence.

### Etape C — Observabilité

Ouvrir Grafana et montrer que l’interface SRE est séparée de l’interface métier.

### Etape D — API contracts

Ouvrir Swagger Agent/Workflow pour présenter les contrats et le lifecycle.

### Etape E — OpenShift

Montrer Deployments, StatefulSets, Routes, NetworkPolicies, Secrets (métadonnées uniquement) et quotas.

### Etape F — Git / Architecture

Montrer :

- Wiki ;
- `docs/` ;
- `infra/helm` ;
- `gitops/` ;
- `evidence/` ;
- CI.

## 5. Evidence model

Une preuve doit répondre à :

- **quoi** a été testé ?
- **où** ?
- **quand** ?
- **sur quel commit/image** ?
- **quelle commande/action** ?
- **quel résultat observé** ?
- **quelle limite** ?

## 6. Structure recommandée

```text
evidence/
  graduation/
    live/
      crc/<timestamp>/
      ui/<timestamp>/
      resilience/<timestamp>/
      azure/<timestamp>/
```

Chaque dossier doit contenir un résumé lisible et, si utile, sorties redacted.

## 7. Règles de claims

| Preuve | Claim autorisé |
|---|---|
| code présent | IMPLEMENTED |
| tests CI verts | TESTED IN CI |
| ressource déployée | DEPLOYED |
| endpoint/flow observé | LIVE VERIFIED |
| architecture documentée seulement | TARGET/DESIGNED |

Ne jamais passer directement de `DESIGNED` à `VERIFIED`.

## 8. Evidence Web Cockpit actuelle

Le 2026-09-13 :

- UI Build `Complete` ;
- image publiée ;
- Helm deployed revision 5 ;
- Deployment Ready ;
- Route créée ;
- UI et health/proxies HTTP 200 ;
- `I9_CRC_VERIFY_PASS`.

Limite : le parcours HITL métier complet reste à capturer.

## 9. Incident de build runtime — leçon opérationnelle

Deux rebuilds du runtime ont été évincés par manque d’ephemeral-storage. La bonne réaction a été :

1. identifier `BuildPodEvicted` ;
2. vérifier `DiskPressure` ;
3. supprimer les builds ratés ;
4. réutiliser l’image runtime existante saine ;
5. construire uniquement l’IHM nécessaire ;
6. documenter la dette d’optimisation.

Leçon : **ne pas relancer aveuglément un build qui viole une contrainte de capacité**.

## 10. CI finale

Après changement documentaire ou fonctionnel important :

- frontend build ;
- Helm lint/render ;
- validators I9/I10/I11/I13 ;
- security/SBOM ;
- pytest ;
- graduation checker.

## 11. Graduation

Le cockpit CRC n’ajoute pas de blocker I12. Les blockers globaux restent :

- `OPENSHIFT_AZURE_DEPLOYMENT` ;
- `RESILIENCE_FINOPS_GREENOPS_VERIFIED`.

Le HITL live CRC reste néanmoins une preuve souhaitée pour fermer fonctionnellement la démonstration locale.
