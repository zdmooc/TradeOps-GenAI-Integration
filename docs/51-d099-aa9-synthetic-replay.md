# D099 AA9 — replayable offline CI demonstration, SYNTHETIC

Command (TradeOps PR #27):
`python -m services.solution_architect.synthetic_demo`

The script runs a genuinely disposable local Git worktree and
tests the policy/configuration invariants and LangGraph HITL interrupt
with fictional data. It emits one JSON status per AA4-AA8 capability
and explicit false fields for all unproven real/runtime gates.

It uses no cloud, OpenHands container, live LLM, MCP network listener,
real identity, external repo, CRC, human review or authenticated approval.
It cannot be mistaken for formal AA9 evidence if downstream tooling
respects `AA9_REPRODUCIBLE_DEMO_VALIDATED=false`.

To close AA9: after prior gate approvals, capture a **real source-pinned
agent run**, valid source-grounding/evaluator and human review,
authorized scope-limited POC build, external immutable tool audit,
measured resource/latency, and an independent repeat of the end-to-end
scenario with sanitized artifact hashes and release/signature.
