# Scénario 04 — MCP natif / IBM MQ QM.MAYABANK

**Mode : preuve historique R5 du 08/10 ; aucun nouveau runtime.** Durée : 2–3 min.

## Flux réellement démontré dans R5

```text
Agent Controller :8015
 -> mcp-native :8017/mcp (scope mq.read, ToolGovernor, audit)
 -> mq-ops-api.mayabank-mq-local.svc:8080
 -> IBM MQ QM.MAYABANK -> PAYMENT.REQUEST.Q
```

## Assertions observées

- Outils `mq.get_queue_status` et `payments.get_mq_health` exposés.
- Payload de santé valide et parité de profondeur `PAYMENT.REQUEST.Q` avec `runmqsc`.
- `SYSTEM.ADMIN.COMMAND.QUEUE` explicitement refusée : **HTTP 403** avec `queue is not allowed`.
- Échec du bypass direct Agent Controller -> mq-ops-api conformément à NetworkPolicy.
- `R5_CRC_MCP_MQ_VERIFY_PASS` suivi de `R5_CRC_WINDOW_REPARK=PASS`.

## Références

- [R5 evidence](../../docs/38-mcp-r5-crc-runtime-evidence.md)
- [R5 résumé public expurgé](../../evidence/r5/20261008-crc-native-mcp-mq-observed-summary.md)

Le répertoire brut de preuves R5 reste local jusqu'à assainissement. Ne jamais relancer `scripts/r5_crc_mcp_mq_run.sh` pour cette démo : ce runner peut faire des déploiements et reconstructions suivant le mode.
