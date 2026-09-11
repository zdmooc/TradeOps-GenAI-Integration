# I7 — Decision Fusion and Human-in-the-Loop

Iteration 7 converts the I6 analysis-only result into a governed decision workflow without enabling autonomous execution.

## Fusion contract

The fusion policy is deterministic and gate-based. It does not use majority voting and the evidence score is informational only.

Required gates:

- I6 assessment is `SUPPORTED`;
- I3 deterministic risk is `ACCEPT`;
- market evidence is fresh;
- evidence quality meets the policy threshold;
- regime is explicitly allowlisted;
- R/R meets the minimum;
- historical sample size is sufficient;
- historical expectancy is positive enough;
- entry/stop/target geometry is directionally valid;
- a real-market calibrated ML probability, when explicitly qualified, must meet its threshold.

Synthetic I5 calibration never becomes a probability gate for I7. A synthetic or `SCORE_ONLY` output is recorded as non-decisive.

A fully eligible setup becomes `REVIEW_REQUIRED`, never `APPROVED`.

## HITL lifecycle

`NO_TRADE` is terminal.

Eligible cases follow:

`PENDING_REVIEW -> APPROVED|REJECTED|EXPIRED`

Approved cases can then become:

- `EXECUTED_SHADOW`: records the approved decision without placing an order;
- `EXECUTED_PAPER`: calls the governed tool boundary using the reviewer identity and `human_approved=true`.

A case cannot be reviewed twice or executed twice. Expired cases fail closed. Risk must still be `ACCEPT` at review and execution.

## Persistence and audit

I7 reuses the existing `workflows` table. The full I7 case is stored under `payload.i7`, while workflow status, decision and reviewer remain searchable columns.

Audit kinds:

- `decision.proposed`;
- `decision.reviewed`;
- `decision.executed`.

The paper OMS now accepts an optional `workflow_id` so the order can retain the exact I7 proposal/workflow identifier rather than a generated placeholder.

## Identity boundary

- agent token: may propose a decision;
- reviewer token: may approve/reject and execute an approved SHADOW/PAPER case;
- the general agent still cannot call `oms.place_order` because it lacks `paper.execute`.

Static bearer tokens remain a local demonstrator. Production OIDC/RBAC is deferred to I8.

## Non-claims

I7 does not enable real-money execution. It does not claim real-market ML calibration, live IG execution, production identity federation, or end-to-end OpenTelemetry. Those remain later capability gates.
