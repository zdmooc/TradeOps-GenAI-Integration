# D-090 G3/G4 — shared gateway runtime closure

## Goal

Prove on the same deployed AI Access path:

- `tradeops-ai -> tradeops-default` = allow;
- `odm-ai -> odm-extraction` = allow;
- `tradeops-ai -> odm-extraction` = deny;
- `odm-ai -> tradeops-default` = deny.

The two clients use the shared Keycloak realm and the same canonical Kong/AI Access/LiteLLM path.

## Secret handling

The wrapper:

- creates/synchronizes Keycloak client secrets into Kubernetes Secrets;
- never prints the values;
- uses environment variables only for the short probe process;
- writes evidence with status/consumer/provider/model only;
- unsets secret variables on exit.

## Preferred bounded CRC execution

When TradeOps is parked:

~~~bash
export D090_LITELLM_API_BASE='<existing reachable Ollama endpoint>'
export D090_RUN_G3_G4_SHARED_ISOLATION=yes
bash scripts/crc/d090-g1-live-from-park.sh
~~~

This temporarily restores only the required deployments, proves G1 and G3/G4, then returns them to the parked state.

Expected final markers:

~~~text
D090_G1_LIVE=PASS
D090_TRADEOPS_CONSUMER=PASS
D090_ODM_CONSUMER=PASS
D090_CROSS_MODEL_ISOLATION=PASS
D090_SHARED_ISOLATION=PASS
D090_G3_SHARED_GATEWAY=PASS
D090_G4_CROSS_CONSUMER_ISOLATION=PASS
D090_SHARED_RUNTIME_RESULT=PASS
D090_G1_WINDOW_REPARK=PASS
~~~

This proves bounded single-node CRC shared-consumer isolation. It does not prove production multi-tenancy or HA.
