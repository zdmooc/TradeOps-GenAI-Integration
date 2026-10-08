# TradeOps — parcours de démonstration CRC / architecture / Day-2

**Dossier canonique de démonstration.** Même principe de parcours guidé que le `demo/` du Lakehouse (branche `runtime/kind-edl-lab`), mais cible **TradeOps sur OpenShift Local / CRC**, et non le Lakehouse Kind. Aucun nouveau dépôt, aucun script métier dupliqué.

## Choisir un mode

| Mode | État attendu | Ce qui est permis |
| --- | --- | --- |
| `PARK / lecture seule` (par défaut) | Deployments TradeOps volontairement arrêtés, StatefulSets préservés ; observé le 08/10/2026 | Architecture, cluster, capacité, Security, GitOps, Operators, evidence antérieure, diagnostic N3 |
| `ACTIVE / présentation supervisée` | Ne se prépare qu'après une décision explicite et vérification des ressources | Afficher les surfaces réellement Ready et les checks non mutateurs |
| `Fenêtre R5 / G1 / G2` | Campagnes bornées historiques, re-PARK attesté | **Expliquer les preuves** ; ne pas les relancer pour une simple démonstration |

**Ne jamais exécuter automatiquement** `resume-tradeops.sh`, `r5_crc_mcp_mq_run.sh`, `i9_crc_deploy.sh`, de build, de chaos, de tests négatifs mutateurs ou de `rollout restart`.

## Démarrage rapide (Git Bash Windows)

```bash
cd /c/workspaces/TradeOps-GenAI-Integration
git status --short --branch
bash demo/scripts/00-preflight.sh
bash demo/scripts/01-capture-readonly.sh
```

Les sorties restent dans `.runtime/tradeops-demo/<timestamp-UTC>/` (ignoré de Git). **Revoir et expurger avant tout partage** ; le script n'exporte ni Secret ni token et ne produit aucun push.

## Navigation

- [CHECKLIST-5-MINUTES.md](CHECKLIST-5-MINUTES.md) : 5 minutes avant entretien.
- [RUNBOOK-A-Z.md](RUNBOOK-A-Z.md) : déroulé Windows/CRC, PARK/ACTIVE et gestion des preuves.
- [ACCESS.md](ACCESS.md) : interfaces, accès, règles de confidentialité.
- [TALK-TRACK.md](TALK-TRACK.md) : présentation orale 15 min ou 30 min.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) : diagnostic sans mutation.
- [scenarios/](scenarios/) : cinq scénarios techniques et métier ; statuts de preuves individualisés.
- [scripts/](scripts/) : contrôles **read-only** ; les commandes mutatrices historiques restent dans leurs runbooks canoniques.
- [presentation/PLAN-SLIDES.md](presentation/PLAN-SLIDES.md) : support d'animation et deux PDF.
- [Les deux dossiers PDF du 08/10/2026](../docs/dossiers/README.md) : 29 pages chacun.

## Vérité technique à annoncer

- **CRC mono-nœud** : preuve locale, ni HA, ni PRA, ni readiness de production.
- Capture du 08/10 : **89 commandes, 12 sections, 0 erreur d'exécution** sur TradeOps **en PARK** ; ces chiffres ne prouvent pas que tous les services sont disponibles.
- **MCP-R5** : chemin réel `Agent Controller -> mcp-native -> mq-ops-api -> QM.MAYABANK` vérifié séparément le 08/10 avec queue interdite HTTP 403 puis re-PARK.
- **D-090 G1/G2** : authentification et gouvernance IA mono-consommateur vérifiées en fenêtres historiques séparées ; **G3/G4 non promus**.
- **Web Cockpit** : infrastructure/health CRC prouvés ; scénario complet `REVIEW_REQUIRED -> humain -> SHADOW/PAPER -> audit` encore à démontrer live de bout en bout.
- **D-093** : `CapabilityConsumption/tradeops-crc` reste en `Observe`, jamais `Manage` implicite.
- Les captures locales et les preuves historiques restent distinctes ; ne jamais transformer une hypothèse ou un manifest Git en `LIVE VERIFIED`.

## Sources de vérité sans duplication

- [Runbook PARK / RESUME](../docs/runbooks/CRC_TRADEOPS_PARK_RESUME.md)
- [R5 MCP/MQ](../docs/38-mcp-r5-crc-runtime-evidence.md)
- [I12 pack d'entretien](../docs/22-interview-demo-pack.md)
- [URLs de démonstration](../docs/28-demo-urls.md)
- [Wiki démo / evidence](../wiki/14-Demo-Runbook-Evidence.md)
- Méthodes externes : [Shared CaaS/N3](https://github.com/zdmooc/shared-platform-services-openshift/blob/main/docs/runbooks/OPENSHIFT_CAAS_DAY2_N3_DEMO.md) et [Lakehouse demo](https://github.com/zdmooc/enterprise-data-lakehouse-kubernetes-openshift/tree/runtime/kind-edl-lab/demo).
