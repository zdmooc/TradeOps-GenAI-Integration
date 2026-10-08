# Scripts de présentation sans mutation de CRC

- `00-preflight.sh` : vérifie uniquement l'API CRC, le namespace, l'état enregistré PARK et les replicas visibles ; il n'effectue ni action Git ni mise à l'échelle.
- `01-capture-readonly.sh` : réexécute un sous-ensemble de diagnostics, inscrit les résultats dans `.runtime/tradeops-demo/<UTC>/` et émet un résumé sans publier d'archive ni consulter le contenu des Secrets.

```bash
cd /c/workspaces/TradeOps-GenAI-Integration
bash demo/scripts/00-preflight.sh
bash demo/scripts/01-capture-readonly.sh
```

Pas de mode `resume`, `deploy`, `chaos`, `self-heal` ou `R5` dans ce répertoire. Les vrais runners restent sous `scripts/`, avec leurs garde-fous et procédures dédiées.
