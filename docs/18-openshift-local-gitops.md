# I9 — OpenShift Local / CRC and GitOps

Iteration 9 packages the I8 target slice for OpenShift Local/CRC without claiming a live deployment from CI.

## Runtime boundary

The target CRC runtime deploys one shared `tradeops-runtime:i9` application image with different module commands for:

- market-data, workflow-api, genai-api, rag-api, agent-controller and mcp-server;
- deterministic risk-engine;
- paper-oms and notifier.

The legacy `signal-engine` is deliberately excluded because its pre-I2 demonstration signal rule is not part of the target architecture. Deterministic I2/I3/I4/I5 capabilities remain invoked through the governed target paths rather than reviving that demo worker.

Core local dependencies are PostgreSQL, Redpanda and Qdrant. I8 observability is represented by OpenTelemetry Collector, Prometheus and Grafana. Kong and the developer `tools` container remain compose-only utilities, not dependencies of the I9 target decision path.

## Resource and security profile

`infra/helm/tradeops` now defines explicit requests/limits for every application and platform container. HTTP APIs use startup, readiness and liveness probes. Stateful dependencies use readiness checks. The pod/container baseline disables privilege escalation, drops Linux capabilities and requests RuntimeDefault seccomp behavior while avoiding a fixed UID so OpenShift restricted SCC can assign an arbitrary UID.

The CRC overlay adds a ResourceQuota and LimitRange. NetworkPolicy starts from default-deny, then permits intra-namespace traffic, DNS, OpenShift router ingress to the exposed services and TCP/443 egress only for components which need external market/LLM endpoints. FQDN-level egress control is outside standard Kubernetes NetworkPolicy and is not claimed.

## Image strategy

`Dockerfile.openshift` builds one reusable application image instead of one almost-identical Python image per service. This is intentional for CRC disk/RAM economics. The RAG-only dependencies are pinned in that image. The OpenShift BuildConfig publishes `tradeops-runtime:i9` to the namespace ImageStream.

## GitOps

Argo CD resources under `gitops/argocd` are split by responsibility:

1. `tradeops-platform` — namespace, quotas, NetworkPolicies, ImageStream and BuildConfig through Kustomize;
2. `tradeops-kyverno-policies` — CEL-based Kyverno policies;
3. `tradeops-runtime` — Helm runtime chart.

All Applications point to the actual GitHub repository and `main`; the old example repository placeholder is removed.

## Kyverno

The policies intentionally use `policies.kyverno.io/v1` `ValidatingPolicy`, not legacy `kyverno.io/v1` `ClusterPolicy`. They deny missing CPU/memory resources, `:latest` images and containers which permit privilege escalation or fail to drop `ALL` capabilities.

Kyverno itself must already be installed for those policies to become active. The direct CRC script detects the CRD and applies the policies only when available.

## CRC execution

Prerequisites: running CRC/OpenShift, `oc`, Helm, enough disk/RAM and two locally supplied secret values.

```bash
./scripts/i9_crc_preflight.sh
export POSTGRES_PASSWORD='...'
export GRAFANA_ADMIN_PASSWORD='...'
./scripts/i9_crc_deploy.sh
./scripts/i9_crc_verify.sh
```

For Argo CD management after the image build:

```bash
DEPLOY_MODE=gitops ./scripts/i9_crc_deploy.sh
```

The script requires an existing `argocd` namespace and Application CRD in GitOps mode; it does not silently install Argo CD.

## Image vulnerability scan

`i9_image_scan.sh` provides a fail-closed Trivy HIGH/CRITICAL gate for a reachable image reference. CI does not claim that scan because CI does not build/publish the CRC internal image. A scan result becomes deployment evidence only after executing the script against the built image.

## CI evidence vs deployment evidence

CI validates Python tests, security/SBOM gates, Helm lint/template rendering and I9 platform invariants. This proves the manifests render and the architecture constraints remain versioned. It does **not** prove the user's local CRC successfully pulled/built every image, bound storage, rendered Routes, delivered traces, or passed live health checks. Those require `i9_crc_deploy.sh` plus `i9_crc_verify.sh` on the actual CRC cluster.
