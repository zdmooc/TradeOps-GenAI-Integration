# D099 AA6 — LangGraph review interrupt, in-memory only

This capability reuses **existing** `langgraph==1.2.11` from the TradeOps
repository. It is isolated under `services/solution_architect`, leaving
`services/agent_controller/graph.py` (trading domain) untouched.

Flow:
`preflight` checks host-provided boolean facts, design, policy and
adapter-audit summaries, then either STOP on any failure or raise a
LangGraph `interrupt()`. The workflow compiles with `MemorySaver`
and requires explicit `thread_id` to demonstrate checkpoint/resume.
A resume payload only acknowledges that review was requested:
**NO resume value may grant authority to build or mutate runtime**.
All statuses preserve `build_authorized=false` and
`runtime_mutation_authorized=false`.

`MemorySaver` is transient and untrusted for enterprise durability.
Host booleans in synthetic CI are NOT independently attested.
Pending genuine AA6: persistent encrypted checkpoint store,
authenticated independent reviewer, nonce/approval action-hash
binding, no self-approval, durable audit, recovery after process
restart, coupled AA2 tool-policy server gateway and formal HITL
evidence. No OpenHands or CRC actions here.
