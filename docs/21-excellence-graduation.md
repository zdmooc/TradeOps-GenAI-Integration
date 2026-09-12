# I12 — Excellence Graduation

## Purpose

I12 is an evidence gate, not a marketing label. It consolidates I0-I11 and prevents the portfolio from claiming `GRADUATED` until operational evidence exists for every mandatory criterion.

The governing rule remains:

`DESIGNED != IMPLEMENTED != TESTED != DEPLOYED != VERIFIED`.

CI success can prove code and configuration contracts. It cannot by itself prove a live market feed, a running OpenShift/ARO deployment, retained end-to-end telemetry, measured disaster recovery, measured cloud cost/carbon, or one hundred real paper/shadow outcomes.

## Executable graduation gate

The versioned manifest is `data/graduation/i12_graduation_manifest.json` and is evaluated by `services/graduation/gate.py` through `scripts/i12_graduation_check.py`.

Supported criterion states:

- `SATISFIED` — evidence meets the criterion;
- `PARTIAL` — substantial implementation/test evidence exists but required live/operational proof is incomplete;
- `PENDING` — required evidence has not yet been collected;
- `NOT_APPLICABLE` — allowed only for the conditional ML-calibration criterion when no production probability claim is made.

The gate fails closed on missing/duplicate criteria, invalid evidence states, missing repository evidence and false live claims.

## Current I12 assessment

The current expected status is **NOT_GRADUATED**.

Satisfied in code/CI/documentation:

- data-quality engine;
- deterministic technical/pattern/regime capability;
- reproducible backtest mechanics with OOS/walk-forward discipline;
- specialized agents and conflict handling;
- governed tool/MCP-shaped security boundary;
- deterministic risk gate plus HITL;
- interview/demo pack;
- banking/insurance transposition.

Conditional:

- production ML probability is not claimed, therefore real-market calibration is not required to graduate under the current claim set. If a production probability claim is introduced, the criterion becomes mandatory immediately.

## Graduation blockers

### 1. Live multi-source input + replay

I1 proves canonical replay and an IG adapter offline. Graduation requires at least two independent real input sources with source identity preserved, captured live evidence and deterministic replay of captured events.

### 2. One hundred paper/shadow outcomes

The gate requires at least 100 unique closed PAPER/SHADOW signals from live or recorded real-market input with finite realized-R metrics and evidence references. Synthetic I4/I5/I7 fixtures explicitly do not count.

### 3. Live observability/security evidence

I8 proves instrumentation/security mechanics in CI. Graduation additionally requires retained end-to-end trace/correlation evidence through the deployed target plus evidence that security controls are active in that environment.

### 4. OpenShift/RHOAI/Azure deployment verification

I9-I11 provide deployment contracts and CI validators. Graduation requires actual deployment/verification evidence for the selected OpenShift target, AI serving target and Azure/ARO architecture slice. A full production estate is not required, but the claimed deployment must actually have run.

### 5. Resilience + FinOps + GreenOps verification

Architecture and tagging are documented. Graduation requires measured evidence: at least one recovery/failure exercise with observed recovery values plus measured infrastructure cost/resource evidence and an explicitly scoped carbon/GreenOps measurement or documented measurement method/result.

## Controlled graduation

CI runs:

```bash
python scripts/i12_graduation_check.py --expect-status NOT_GRADUATED
```

This protects the repository against accidental status inflation. When all blockers have real evidence, the manifest must be reviewed, the expected CI state deliberately changed, and the strict gate must pass:

```bash
python scripts/i12_graduation_check.py --require-graduated
```

No live-money execution is required for graduation and none is enabled by I12.
