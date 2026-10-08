# Checklist — 5 minutes avant la démo TradeOps

## Vérification rapide (aucune modification CRC)

```bash
cd /c/workspaces/TradeOps-GenAI-Integration
git status --short --branch
bash demo/scripts/00-preflight.sh
oc -n tradeops get deploy,statefulset,pods -o wide
oc adm top nodes
oc -n openshift-gitops get applications.argoproj.io
```

Interpréter les Deployments à `0/0` à la lumière du snapshot PARK ; en absence de preuve de PARK, ne pas annoncer `PARK confirmé`.

## Écrans à préparer

1. [demo/README.md](README.md) et [RUNBOOK-A-Z](RUNBOOK-A-Z.md) dans VS Code.
2. [Deux dossiers PDF](../docs/dossiers/README.md), onglets architecture + diagnostic.
3. Console OpenShift : nœud, `tradeops`, Routes et NetworkPolicies (pas de Secrets).
4. Argo CD / Grafana **uniquement s'ils répondent**.
5. [R5](../docs/38-mcp-r5-crc-runtime-evidence.md) et [D-090 G1/G2](../evidence/d090/20261007-g2-crc-runtime-proof.md) comme **preuves historiques**.

## Parcours de 15 minutes

Architecture -> cluster/PARK -> sécurité/GitOps -> architecture métier -> R5 MCP/MQ -> G1/G2 AI governance -> observabilité et écarts -> limites.

## Interdits pendant l'entretien

Pas de `resume` automatique, `delete`, `apply`, `scale`, `rollout restart`, de chaos, de build, de relecture de secrets, de `R5` en mode full-stack ou de présentation du `HITL E2E` comme prouvé.

## Après la démo

Si une capture read-only a été effectuée, examiner les fichiers sous `.runtime/tradeops-demo` avant tout partage. Le démonstrateur ne change ni le cluster ni ses replicas.
