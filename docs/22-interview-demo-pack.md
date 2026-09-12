# I12 — 30-minute interview / architecture demonstration pack

## Goal

Demonstrate an enterprise AI Solution Architect approach using real-time trading as a demanding reference workload while making the architecture transferable to banking, payments, insurance, fraud, risk and cyber/IT supervision.

## 0-3 min — Business problem and safety boundary

Explain the objective: trustworthy real-time decision support with deterministic controls, ML where measurable, agents where orchestration/reasoning adds value, and HITL before execution.

State the non-negotiable boundaries:

- deterministic calculations stay deterministic;
- ML scores are not called probabilities without real calibration evidence;
- deterministic risk can veto;
- agents cannot bypass risk or HITL;
- current scope is analysis/replay/paper/shadow, not autonomous real-money execution.

## 3-7 min — End-to-end architecture

Walk through:

`Sources -> Data Quality -> Canonical Events -> Kafka-compatible backbone -> Technical/Pattern -> Regime -> ML -> Agents/RAG/Tools -> Fusion -> Risk -> HITL -> Paper/Shadow -> Evidence`.

Show how source identity, timestamps, latency, spread and staleness are preserved instead of averaging feeds blindly.

## 7-10 min — Data trust and replay

Use I1 to explain canonical `MarketEvent`, stale/duplicate/out-of-order controls and deterministic replay. Explicitly state that live multi-source graduation evidence is still pending.

## 10-14 min — Deterministic market intelligence and risk

Use I2/I3 to show indicators, structure, patterns, regimes and `ACCEPT | VETO | REVIEW`. Demonstrate that `VETO` is terminal and explain why this is an enterprise policy pattern, not only a trading pattern.

## 14-18 min — Backtesting and ML discipline

Use I4 to explain next-bar execution, costs, no-lookahead, OOS and walk-forward. Use I5 to explain feature contracts, leakage prevention, champion selection, calibration and drift.

State explicitly: synthetic calibration proves mechanics, not real-market probability or alpha.

## 18-23 min — Agentic AI, RAG, governed tools and HITL

Use I6/I7 to show specialized agents, `UNKNOWN / DATA_STALE / CONFLICT / VETO`, governed RAG/tool access, separate agent/reviewer identities and the SHADOW/PAPER lifecycle.

Explain why agent agreement can never override deterministic risk.

## 23-26 min — Observability and security

Use I8 to show OpenTelemetry correlation, Prometheus/Grafana/SLO concepts, OIDC-compatible identity, SBOM and security gates. Distinguish CI-tested controls from still-pending live retained telemetry.

## 26-29 min — OpenShift AI and Azure enterprise target

Use I9/I10 for OpenShift/CRC, GitOps, policies, RHOAI/KServe/vLLM and model qualification. Use I11 for ARO private networking, managed/workload identity, Key Vault, Azure Monitor and optional Microsoft Foundry.

Do not claim live CRC/RHOAI/ARO deployment until evidence is captured.

## 29-30 min — Enterprise transposition and close

Translate the same control plane to payment fraud, claims, underwriting, AML/fraud triage, cyber events or real-time operational decisions.

Close with the I12 graduation dashboard: what is already tested, what remains operationally unverified, and how the evidence gate prevents architecture theatre.

## Suggested interviewer questions

Be ready to answer:

- Why not let the LLM compute technical indicators or risk?
- Why preserve price-source identity rather than averaging feeds?
- How do you prevent data leakage in ML experiments?
- What is the difference between a score and a calibrated probability?
- How does a deterministic veto survive an agentic workflow?
- Why is HITL identity separate from agent identity?
- How do you trace one decision from input event to paper outcome?
- What would change for payments/fraud/insurance?
- What is still not verified live?
- What exact evidence would be required before declaring production readiness?
