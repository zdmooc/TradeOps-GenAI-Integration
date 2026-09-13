# TradeOps — Catalogue des URLs de démonstration

Ce document centralise les URLs utiles pour une démonstration TradeOps. Chaque entrée est classée `LIVE`, `INTERNAL`, `PLANNED` ou `REFERENCE` afin d'éviter de présenter comme déployé ce qui ne l'est pas encore.

## CRC / OpenShift platform

| Status | Usage | URL |
|---|---|---|
| LIVE | OpenShift Web Console | `https://console-openshift-console.apps-crc.testing` |
| LIVE | OpenShift API | `https://api.crc.testing:6443` |

Validated CRC baseline: CRC 2.63.0, OpenShift 4.22.7.

## TradeOps Routes — CRC

Verified Routes captured in live CRC evidence:

| Status | Component | URL |
|---|---|---|
| LIVE | Agent Controller | `https://agent-controller-tradeops.apps-crc.testing` |
| LIVE | Grafana | `https://grafana-tradeops.apps-crc.testing` |
| LIVE | Workflow API | `https://workflow-api-tradeops.apps-crc.testing` |
| LIVE | TradeOps Web Cockpit | `https://tradeops-ui-tradeops.apps-crc.testing` |

The cockpit Route was live-verified on 2026-09-13 with its Deployment Ready, `/healthz` reachable, the market/workflow/agent proxy health endpoints returning HTTP 200, and `scripts/i9_crc_verify.sh` ending with `I9_CRC_VERIFY_PASS`.

## Agent Controller — browser/demo endpoints

Base URL:

`https://agent-controller-tradeops.apps-crc.testing`

| Status | Purpose | URL |
|---|---|---|
| LIVE | Health | `https://agent-controller-tradeops.apps-crc.testing/health` |
| LIVE | Swagger UI | `https://agent-controller-tradeops.apps-crc.testing/docs` |
| LIVE | OpenAPI | `https://agent-controller-tradeops.apps-crc.testing/openapi.json` |
| LIVE | Prometheus metrics | `https://agent-controller-tradeops.apps-crc.testing/metrics` |
| LIVE/API | Agent assessment | `POST https://agent-controller-tradeops.apps-crc.testing/agent/assessment` |
| LIVE/API | Decision proposal | `POST https://agent-controller-tradeops.apps-crc.testing/decision/propose` |
| LIVE/API | Decision read | `GET https://agent-controller-tradeops.apps-crc.testing/decision/{proposal_id}` |
| LIVE/API | Human review | `POST https://agent-controller-tradeops.apps-crc.testing/decision/{proposal_id}/review` |
| LIVE/API | Approved SHADOW/PAPER execution | `POST https://agent-controller-tradeops.apps-crc.testing/decision/{proposal_id}/execute` |

`/agent/trade` remains intentionally disabled for autonomous execution.

## Workflow API — browser/demo endpoints

Base URL:

`https://workflow-api-tradeops.apps-crc.testing`

| Status | Purpose | URL |
|---|---|---|
| LIVE | Health | `https://workflow-api-tradeops.apps-crc.testing/health` |
| LIVE | Swagger UI | `https://workflow-api-tradeops.apps-crc.testing/docs` |
| LIVE | OpenAPI | `https://workflow-api-tradeops.apps-crc.testing/openapi.json` |
| LIVE | Prometheus metrics | `https://workflow-api-tradeops.apps-crc.testing/metrics` |
| LIVE | Audit view API | `https://workflow-api-tradeops.apps-crc.testing/audit` |
| LIVE/API | Create trade request | `POST https://workflow-api-tradeops.apps-crc.testing/trade-requests` |
| LIVE/API | Read trade request | `GET https://workflow-api-tradeops.apps-crc.testing/trade-requests/{workflow_id}` |
| LIVE/API | Approve classical workflow | `POST https://workflow-api-tradeops.apps-crc.testing/trade-requests/{workflow_id}/approve` |

## Grafana

| Status | Purpose | URL |
|---|---|---|
| LIVE | Grafana home | `https://grafana-tradeops.apps-crc.testing` |

Provisioned dashboards currently include:

- `TradeOps API`;
- `TradeOps I8 - Observability, Security and LLMOps`.

The dashboard JSON does not pin a stable public UID in this repository, so the demo catalog deliberately records the stable Grafana Route rather than inventing deep-link URLs.

## Cluster-internal service URLs

These endpoints are valid **inside the `tradeops` namespace / cluster network** and are not browser demo Routes.

| Status | Service | Internal URL |
|---|---|---|
| INTERNAL | Market Data | `http://market-data:8011` |
| INTERNAL | Workflow API | `http://workflow-api:8012` |
| INTERNAL | GenAI API | `http://genai-api:8013` |
| INTERNAL | RAG API | `http://rag-api:8014` |
| INTERNAL | Agent Controller | `http://agent-controller:8015` |
| INTERNAL | MCP Server | `http://mcp-server:8016` |
| INTERNAL | Grafana | `http://grafana:3000` |
| INTERNAL | Prometheus | `http://prometheus:9090` |
| INTERNAL | Qdrant | `http://qdrant:6333` |
| INTERNAL | OpenTelemetry Collector | `http://otel-collector:4318` |
| INTERNAL | PostgreSQL | `postgres:5432` |
| INTERNAL | Redpanda / Kafka API | `redpanda:9092` |

Do not expose MCP, PostgreSQL, Redpanda, Qdrant or the risk/execution internals publicly just to simplify a demo.

## Web Cockpit navigation

Main LIVE entry point:

`https://tradeops-ui-tradeops.apps-crc.testing`

The cockpit Demo/Platform page links to:

- Agent Controller `/docs`;
- Workflow API `/docs`;
- Grafana Route;
- OpenShift Web Console;
- the current environment/mode (`CRC`, `SHADOW` or `PAPER`);
- deployment/evidence commit IDs where useful.

The platform/route proof is LIVE. The complete interactive HITL sequence `REVIEW_REQUIRED -> APPROVE/REJECT -> SHADOW/PAPER -> audit` is tracked separately until a dedicated live business-flow evidence capture is added.

## GitHub repositories used during a demonstration

| Status | Purpose | URL |
|---|---|---|
| REFERENCE | Architecture/roadmap master | `https://github.com/zdmooc/maya-ai-agentic-architecture-reference` |
| REFERENCE | Executable TradeOps implementation | `https://github.com/zdmooc/TradeOps-GenAI-Integration` |
| REFERENCE | Azure reusable architecture patterns | `https://github.com/zdmooc/mayabank-azure-cloud-ai-platform` |

## Suggested interview/demo path

```text
1. Open TradeOps Web Cockpit
2. Show market/signal/agent/risk evidence
3. Demonstrate REVIEW_REQUIRED
4. Approve SHADOW or PAPER with human reviewer
5. Show outcome/audit
6. Open Grafana for technical observability
7. Open Agent Controller Swagger for API contract
8. Open OpenShift Console for runtime/GitOps evidence
9. Open GitHub architecture master for roadmap/ADR/evidence lineage
```

## Evidence source

CRC live evidence:

- 2026-09-12 baseline: Agent Controller, Grafana and Workflow API Routes;
- 2026-09-13 Web Cockpit: `evidence/graduation/live/ui/20260913/README.md`.

Verified cockpit Route:

```text
tradeops-ui-tradeops.apps-crc.testing
```

Future Routes must be added here only after their deployed status has been verified.
