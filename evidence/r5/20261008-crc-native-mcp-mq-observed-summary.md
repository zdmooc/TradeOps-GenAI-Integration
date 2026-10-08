# MCP-R5 — résumé des preuves runtime CRC du 8 octobre 2026

**Nature :** résumé traçable de l'exécution locale fourni par le journal terminal. Ce document ne remplace pas le bundle de preuves brut ni une capture indépendante.

## Référence reproductible

- Projet : `TradeOps-GenAI-Integration` ; commit applicatif `33a1faf1cd5ee4779b7ce717fe5c41bc8bd3a79b` (PR #21).
- CI PR #21 : `ci / lint-test` **SUCCESS**, GitHub Actions run `37796874524`.
- Build CRC : `tradeops-runtime-16` depuis ce commit.
- Image du run final : `image-registry.openshift-image-registry.svc:5000/tradeops/tradeops-runtime@sha256:5a174f53bf895ddf6f458bb37d64e5de76f74b79749b8865156cf2651b58df34`.
- Namespace applicatif : `tradeops`. IBM MQ : `mayabank-mq-local`, QM `QM.MAYABANK`.
- Entrée : `R5_NO_AUTO_REBUILD=true bash scripts/r5_crc_mcp_mq_run.sh`, mode `BOUNDED_FROM_PARK`.
- Dossier produit localement (UTC) : `evidence/r5/live/crc/20261008T154626Z/`.
- Dossier de fenêtre bornée : `.runtime/tradeops-park/20261007T103947Z/r5-20261008T154400Z`.

## Marqueurs effectivement remontés au terminal

```text
R5_CRC_RUN_MODE=BOUNDED_FROM_PARK
R5_CRC_PARK_PRECONDITION=PASS
R5_CRC_D093_OBSERVE_GUARD=PASS
R5_CRC_MQ_SERVICE_TOKEN=REUSED
R5_CRC_SECRET_MERGE=PASS
R5_MQ_IMAGE_REUSE_PROBE=PASS
R5_MQ_IMAGE=REUSED_EXISTING_DIGEST
R5_MQ_OPS_PINNED_APPLY=PASS
R5_MQ_OPS_DEPLOY_PASS
R5_CRC_RUNTIME_IMAGE=REUSED
R5_CRC_RUNTIME_IMAGE_READY=PASS
R5_CRC_BOUNDED_WINDOW_ACTIVE=PASS
MCP_TOOLS_PASS
MQ_HEALTH_PAYLOAD_PASS
R5_FORBIDDEN_QUEUE_POLICY_PASS
R5_CRC_MCP_MQ_VERIFY_PASS
R5_CRC_FROM_PARK=PASS
R5_CRC_WINDOW_REPARK=PASS
```

La réussite du script final implique qu'il a traversé ses assertions positives et négatives : existence des outils MCP, charge utile santé MQ, profondeur `PAYMENT.REQUEST.Q` cohérente avec `runmqsc`, refus explicite **HTTP 403** de `SYSTEM.ADMIN.COMMAND.QUEUE` avec corps de refus attendu, échec du bypass TCP vers `mq-ops-api`, et retour en PARK.

## Limites et archive

- **Claim permis :** `CRC_RUNTIME_PROVEN / LIVE_OPERATIONAL` pour cette intégration read-only MCP → MQ sur OpenShift Local mono-nœud, avec restauration du PARK.
- **Non prouvé :** production/HA, A2A live, isolation AI Access G3/G4 ou adoption D-093 `Manage`. Le consumer reste en `Observe`.
- Le répertoire local `evidence/r5/live/crc/20261008T154626Z/` **n'est pas embarqué ici**. Le conserver et n'archiver que les pièces contrôlées après vérification des données sensibles ; ne jamais ajouter aveuglément des exports Secret, tokens, mots de passe ou journaux non assainis.
