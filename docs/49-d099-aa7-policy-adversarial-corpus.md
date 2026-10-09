# D099 AA7 — synthetic policy adversarial corpus

Eight lower-trust strings model common instruction-in-data attacks:
forged system/developer authority, forged human approval, malicious
MCP metadata, sensitive-file demand, cross-tenant escalation,
encoded instruction, runtime overclaim and hostile README.

The Python case matrix **does not pass these strings through a model**.
Instead, it verifies the independent host `MayaPolicyGate` always
refuses six mutating/disallowed tool actions under synthetic
`maya-architect` identity and tenant scope. This tests separation of
DATA versus trusted authorization configuration, not the model's
robustness against adversarial persuasion.

Still required: real provider/model attacks, actual tool router
denial telemetry, impersonation and replay attempts on authenticated
identity/approval service, prompt red-team scoring, source poisoning,
secret redaction, and signed independent acceptance evidence.
AA7 remains OPEN even if all 48 denials pass in CI.
