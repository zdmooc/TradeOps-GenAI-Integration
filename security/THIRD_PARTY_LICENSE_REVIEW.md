# Third-party dependency license review — TradeOps

**Date de contrôle : 2026-10-10**  
**Décision : revue incomplète, aucune conclusion de conformité juridique.**

## Périmètre et preuve

- Code et documentation originaux du dépôt : licence MIT restaurée dans `/LICENSE` ; attribution `Copyright (c) 2026 Zidane Djamal` seulement pour les créations dont il détient les droits.
- Source examinée : `security/sbom.spdx.json` (SPDX 2.3, générée le 2026-09-11) ; **23 dépendances Python répertoriées, 23 licences déclarées `NOASSERTION`**.
- `NOASSERTION` indique que la SBOM ne permet pas de conclure : ce n'est **pas** la preuve qu'une bibliothèque est sans licence ou incompatible.
- Aucune affirmation de compatibilité MIT ni d'autorisation de redistribution n'est déduite de cette SBOM.

## Inventaire à qualifier

| Dépendance | Version de la SBOM | Licence déclarée |
|---|---|---|
| `a2a-sdk` | `1.2.1` | `NOASSERTION` |
| `aiokafka` | `0.11.0` | `NOASSERTION` |
| `fastapi` | `0.115.0` | `NOASSERTION` |
| `httpx` | `0.28.1` | `NOASSERTION` |
| `langgraph` | `1.2.11` | `NOASSERTION` |
| `lightgbm` | `4.7.0` | `NOASSERTION` |
| `lightstreamer-client-lib` | `2.2.3` | `NOASSERTION` |
| `mcp` | `2.2.0` | `NOASSERTION` |
| `mlflow` | `3.16.0` | `NOASSERTION` |
| `numpy` | `2.0.2` | `NOASSERTION` |
| `opentelemetry-api` | `1.44.0` | `NOASSERTION` |
| `opentelemetry-exporter-otlp-proto-http` | `1.44.0` | `NOASSERTION` |
| `opentelemetry-sdk` | `1.44.0` | `NOASSERTION` |
| `prometheus-client` | `0.20.0` | `NOASSERTION` |
| `psycopg2-binary` | `2.9.9` | `NOASSERTION` |
| `pydantic-settings` | `2.4.0` | `NOASSERTION` |
| `PyJWT` | `2.13.0` | `NOASSERTION` |
| `pytest` | `8.3.3` | `NOASSERTION` |
| `python-multipart` | `0.0.9` | `NOASSERTION` |
| `ruff` | `0.6.9` | `NOASSERTION` |
| `scikit-learn` | `1.5.2` | `NOASSERTION` |
| `uvicorn` | `0.31.1` | `NOASSERTION` |
| `xgboost` | `3.2.0` | `NOASSERTION` |

## Gate de remédiation avant redistribution d'artefacts intégrant ces dépendances

1. Régénérer une SBOM à partir des fichiers de verrouillage/dépendances et artefacts réellement distribués ; conserver les versions et leurs sources de provenance.
2. Vérifier pour **chaque composant** la licence officielle correspondant à la version utilisée (métadonnées de distribution, fichier de licence du paquet et dépôt amont), sans la deviner.
3. Repérer les obligations de redistribution, attribution, `NOTICE`, publication de source et éventuelles incompatibilités ; préserver les notices des tiers.
4. Documenter les composants embarqués (copiés ou vendorizés), les images de conteneurs, actifs graphiques, modèles IA, poids des modèles, jeux de données et API/services externes séparément.
5. Faire une revue humaine des anomalies avant d'affirmer que la distribution commerciale est conforme ; attacher la preuve aux releases.

**Status : THIRD_PARTY_LICENSE_AUDIT_PENDING.** Ce document ne modifie ni les licences des dépendances, ni les autres gates de validation du projet.
