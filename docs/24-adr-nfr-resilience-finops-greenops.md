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
| Availability | probes, bounded replicas, policy/GitOps contracts | live single-pod recreation recovery verified on CRC; no HA/failover claim |
| Model governance | feature contract + qualification gate | tested in CI |
| Recovery | lab RTO 30 s for the measured stateless pod-recreation drill; RPO only where state loss is applicable | baseline 15.301 s; verified run 14.302 s and RTO PASS |
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

## Measured CRC resilience evidence — 2026-09-12

Two controlled local CRC drills are retained as live operational evidence.

### Baseline drill

Evidence: `evidence/graduation/live/resilience/20260912T202019Z/`

- workload: `tradeops/agent-controller`;
- failure: deletion of exactly one running pod with `--wait=false`;
- old pod UID: `3d74507e-5587-448f-b327-938ee39452cf`;
- replacement pod UID: `36852c97-db41-46ae-b8e2-754493446a60`;
- observed recovery: **15.301 s**;
- no RTO target was set for this first run, so the result is explicitly `NOT_EVALUATED` against a target;
- secret scan: `O5_SECRET_SCAN_PASS`.

This first run is the measured baseline and is not retroactively used to invent a target.

### Predeclared-RTO verification drill

Evidence: `evidence/graduation/live/resilience/20260912T202740Z/`

Before the second failure injection, the lab RTO target was set to **30 seconds**.

- old pod UID: `36852c97-db41-46ae-b8e2-754493446a60`;
- replacement pod UID: `eb799a0e-b21a-4348-8f75-47bdf0cfdcba`;
- observed recovery: **14.302 s**;
- declared lab RTO: **30 s**;
- RTO result: **PASS**;
- route probes observed HTTP `503` during recreation and HTTP `200` once the replacement pod was Ready;
- secret scan: `O5_SECRET_SCAN_PASS`.

The two drills demonstrate repeatable recovery around 15 seconds for this specific single-pod stateless failure mode. They do **not** prove multi-node HA, zone failure recovery, database recovery, broker recovery, or disaster recovery.

### RPO and data-loss scope

RPO is not applicable to this specific drill because the injected failure only recreated a stateless application pod and did not fail a persistent store. No claim of measured persistent-data loss or zero-data-loss recovery is made.

The evidence summaries intentionally retain:

- `rpo_applicable=false`;
- `data_loss_claim=NOT_MEASURED_NOT_APPLICABLE_TO_THIS_DRILL`;
- `provider_cost_claim=NOT_MEASURED_ON_LOCAL_CRC`;
- `carbon_claim=NOT_MEASURED`;
- `full_resilience_finops_greenops_gate_claim=false`.

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

Measured local CRC resilience evidence is now operationally verified: baseline recovery was 15.301 s and the second controlled failure recovered in 14.302 s against a predeclared 30 s lab RTO, which passed. The exercise is intentionally scoped to a stateless single-pod recreation, so RPO is not applicable and no persistent-data recovery claim is made.

Azure provider cost and carbon evidence are still unmeasured. Therefore `RESILIENCE_FINOPS_GREENOPS_VERIFIED` remains `PARTIAL`; the resilience portion is evidenced, while FinOps and GreenOps remain graduation blockers within the combined criterion.
