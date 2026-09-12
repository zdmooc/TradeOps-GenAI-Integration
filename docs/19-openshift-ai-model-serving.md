# I10 — OpenShift AI production-serving architecture

## Scope

I10 packages an OpenShift AI 3.4 target for governed model serving. It does not claim a live RHOAI
cluster deployment from CI. The target separates CPU signal-quality inference from GPU LLM serving.

## Current platform choices

- Red Hat OpenShift AI Self-Managed 3.4 is the versioned target.
- KServe `InferenceService` is the serving lifecycle contract.
- The platform-provided `vllm-runtime` is preferred for GPU LLM inference instead of building a
  second unmanaged vLLM image.
- RHOAI-managed MLflow is the experiment/model lifecycle target. The repository does not deploy a
  parallel standalone MLflow server.
- MLflow access from the custom signal-quality runtime uses Kubernetes service-account identity and
  the `mlflow-operator-mlflow-integration` ClusterRole.

## Signal-quality serving

The I5 model now has an explicit online-serving boundary in `services/model_serving/`.

The request contract accepts dictionaries keyed by the exact I5 feature contract. The server orders
features canonically, rejects missing/extra/non-finite features, calls `predict_proba`, validates the
N x 2 output and exposes the qualification in every result.

A hard production guard is intentional: `MODEL_SERVING_MODE=PRODUCTION` is accepted only when
`MODEL_QUALIFICATION=CALIBRATED_OUT_OF_SAMPLE_REAL_MARKET`. The existing I5 synthetic
qualification therefore remains lab-only and cannot silently become a production probability claim.

The FastAPI serving surface provides:

- `/health/live`;
- `/health/ready`;
- `/v1/models/{model}:predict`;
- `/metrics`.

## KServe resources

`tradeops-signal-quality` uses a custom `ServingRuntime` backed by the OpenShift-compatible TradeOps
image. Its model URI, qualification and MLflow tracking URI are supplied through a runtime-created
Secret rather than committed to Git.

The InferenceService has an initial two-replica HA floor and a four-replica ceiling. Requests/limits,
readiness and liveness probes are explicit.

The versioned vLLM example uses the RHOAI-provided `vllm-runtime`, one NVIDIA GPU per replica and an
intentional `s3://REPLACE-ME/...` storage placeholder. It is an example until a real approved model,
object-storage path and measured GPU sizing are available.

## MLflow lifecycle

The target lifecycle is:

1. train/evaluate with the I5 point-in-time contract;
2. log experiment evidence to RHOAI MLflow;
3. register and version the model;
4. attach qualification metadata;
5. supply an explicit model URI to the serving Secret;
6. load the model through the MLflow SDK using Kubernetes namespaced authentication;
7. expose KServe readiness only after the model is loaded;
8. collect request/error/latency metrics and correlate them with I8 telemetry.

No synthetic I5 model is promoted to production by I10.

## SLO and capacity

The PrometheusRule defines initial engineering targets, not measured achievements:

- zero sustained serving-unavailable responses;
- error budget alert above 1 percent over 10 minutes;
- signal-quality p95 latency target of 250 ms over 10 minutes.

`scripts/i10_capacity_plan.py` converts peak RPS, measured p95 service time, safe per-replica
concurrency and target utilization into an initial replica estimate. It enforces a two-replica floor.
The calculator output is explicitly an estimate until backed by a load test on the target cluster.

## HA and failure modes

Fail-closed behavior:

- MLflow/model load failure -> readiness false;
- wrong/missing feature contract -> HTTP 422;
- unknown model -> HTTP 404;
- synthetic/SCORE_ONLY qualification in PRODUCTION -> startup/readiness failure;
- invalid probability output -> request rejected;
- KServe or MLflow component absent -> preflight failure.

The two-replica floor covers a single serving-pod failure, subject to actual scheduler capacity. True
node-level HA, GPU anti-affinity, storage HA and disaster recovery require target-cluster measurements.

## Operational sequence

1. Enable the RHOAI KServe and MLflow Operator components in `default-dsc` as cluster admin.
2. Run `scripts/i10_rhoai_preflight.sh`.
3. Set `MLFLOW_TRACKING_URI`, `MODEL_URI`, `MODEL_QUALIFICATION` and optionally
   `MODEL_SERVING_MODE`.
4. Run `scripts/i10_rhoai_deploy.sh`.
5. Run `scripts/i10_rhoai_verify.sh`.
6. Capture model load time, cold/warm p50/p95/p99 latency, throughput, saturation, CPU/RAM/GPU,
   restart behavior and replica-failure recovery before upgrading the evidence state to DEPLOYED.

## Explicit non-claims

- no live RHOAI 3.4 deployment is claimed by repository CI;
- no GPU benchmark is claimed;
- the vLLM resource sizing is a starting point, not measured capacity;
- no synthetic I5 calibration is relabeled as real-market probability;
- no production MLflow workspace/model version is claimed until cluster evidence exists;
- no automated real-money execution is enabled;
- I11 Azure/ARO work is not started by I10.
