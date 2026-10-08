# Accès aux surfaces de démonstration — CRC

D'abord exécuter `bash demo/scripts/00-preflight.sh`. **La présence d'une Route n'implique pas que son Service réponde en mode PARK**. Vérifier la disponibilité effective avant de partager un écran.

| Surface | Adresse du lab / usage | Attention |
| --- | --- | --- |
| Console OpenShift | `https://console-openshift-console.apps-crc.testing` | Connexion privée ; pas de token affiché |
| TradeOps Web Cockpit | `https://tradeops-ui-tradeops.apps-crc.testing` | Peut ne pas répondre pendant PARK |
| Workflow API | `https://workflow-api-tradeops.apps-crc.testing/docs` | Swagger si Deployment Ready |
| Agent Controller | `https://agent-controller-tradeops.apps-crc.testing/docs` | Swagger si Deployment Ready |
| Grafana | `https://grafana-tradeops.apps-crc.testing` | Ne pas afficher d'identifiant |
| Argo CD | L'URL se lit via `oc -n openshift-gitops get routes` | Présenter état Synced/Healthy *observé*, pas supposé |

La liste étendue et les endpoints internes sont dans [docs/28-demo-urls.md](../docs/28-demo-urls.md). Les API `mcp-native`, Redpanda, PostgreSQL, Qdrant et IBM MQ ne sont **pas** à exposer en Route publique pour une démo.

## Commandes sûres

```bash
oc whoami --show-server
oc -n tradeops get deploy,pods,svc,route -o wide
oc -n openshift-gitops get applications.argoproj.io
oc -n tradeops get endpointslices.discovery.k8s.io
```

Pour expliquer un test R5, ouvrir sa **preuve assainie** plutôt que relancer le script, lire un Secret ou ouvrir un port-forward.

## Confidentialité

- Ne jamais exécuter `oc whoami -t` ou `oc get secret -o yaml` en partage d'écran.
- Jamais de bearer token, mot de passe, clé, valeur de Secret, commande exportant des credentials, ou `.runtime` brute dans un dépôt public.
- Ne pas sauvegarder de capture montrant l'onglet réseau du navigateur authentifié, des cookies ou des en-têtes Authorization.
- Les valeurs de `LIVE` dans le catalogue URLs se rapportent à une **capture datée** ; l'état au jour de l'entretien doit être observé séparément.
