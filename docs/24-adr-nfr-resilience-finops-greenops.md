# I12 — ADR, NFR, resilience, FinOps and GreenOps pack

## Architecture decisions consolidated

The program's main decisions are:

1. One primary executable runtime; architecture/reference repositories do not become competing runtimes.
2. Deterministic calculations, pattern/risk policy and hard veto remain outside LLM reasoning.
3. Canonical events preserve source, event time, ingest time, spread, latency and data-quality state.
4. Backtests use explicit execution timing/cost assumptions and chronological OOS/walk-forward discipline.
5. ML probability claims require dedicated calibration and qualification; synthetic calibration is not production evidence.
6. LangGraph is the implemented orchestration choice; alternative agent frameworks remain references unless deliberately adopted.
7. Tool access is a security boundary with identity/scopes/allowlists/validation/timeouts/rate limits/audit.
8. HITL identity is separate from agent identity; deterministic veto cannot be overridden.
9. OpenTelemetry is the cross-environment telemetry contract.
10. OpenShift/GitOps is the runtime platform model; RHOAI/KServe is the AI-serving model.
11. Azure target is ARO-first to preserve OpenShift contracts; Microsoft Foundry is optional and cannot bypass risk/HITL/model qualification.
12. Evidence status is explicit: designed, implemented, tested, deployed and verified are not interchangeable.

## NFR baseline

| NFR | Target/contract | Current evidence |
|---|---|---|
| Data freshness | fail closed on stale market evidence | tested in CI |
| Deterministic risk | terminal veto with explicit reasons | tested in CI |
| Auditability | correlation/proposal/review/order lineage | tested in CI |
| Security | least privilege, scope validation, secret hygiene, SBOM | tested in CI; live federation pending |
| Availability | probes, bounded replicas, policy/GitOps contracts | configured/tested; live failover pending |
| Model governance | feature contract + qualification gate | tested in CI |
| Recovery | explicit RTO/RPO to be business-set and measured | pending measurement |
| Performance | no invented p95/p99/throughput | pending live benchmark |
| Cost | tagged/scoped Azure foundation, explicit teardown discipline | design/CI only; measured spend pending |
| Carbon | GreenOps measurement required before claim | pending measurement |

## Resilience evidence required for graduation

At least one controlled deployed-environment exercise must capture:

- failure injected or dependency lost;
- start/end timestamps;
- service impact;
- observed recovery time;
- data-loss/replay result;
- reconciliation result;
- trace/log evidence references;
- comparison with the declared RTO/RPO for that lab.

The repository must not invent an RTO/RPO value merely to satisfy the gate.

## FinOps evidence required

Capture for the selected lab window:

- subscription/project scope;
- tagged resources;
- runtime duration;
- measured or provider-reported cost;
- major cost drivers;
- teardown confirmation;
- optimization decision and expected/observed effect where available.

## GreenOps evidence required

Use a clearly identified method and scope. Record:

- workload/platform boundary;
- region and runtime window;
- CPU/GPU/memory/storage utilization where available;
- provider carbon data or an explicitly documented estimation method;
- assumptions and uncertainty;
- optimization action such as right-sizing, scale-to-zero, scheduling, model/runtime choice or reduced retention;
- before/after comparison only when actually measured.

Cost reduction must not automatically be relabelled as carbon reduction.

## Current status

The design, IaC tags, resource limits and teardown discipline are present, but measured resilience, cost and carbon evidence are not. Therefore `RESILIENCE_FINOPS_GREENOPS_VERIFIED` remains `PARTIAL` in I12.
