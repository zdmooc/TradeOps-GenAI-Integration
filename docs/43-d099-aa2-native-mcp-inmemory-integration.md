# D-099 M2 — in-memory MCP read evidence: a real protocol slice

The optional `services/solution_architect/mcp_evidence.py` registers a single native MCP tool `maya.read_evidence` bound to the already-tested `LocalEvidenceGateway` and deterministic `MayaPolicyGate`.

Runtime path proven by CI tests, when green:

```text
MCP client
 -> maya.read_evidence(repository, path)
 -> server injected trusted principal / tenant / repo scope
 -> MayaPolicyGate.evaluate()
 -> LocalEvidenceGateway (bounded UTF-8 file, symlinks/secret paths refused)
 -> structured reply and adapter-side audit entry
```

The suite uses the official `mcp.Client` and `MCPServer` **in memory**, with disposable pytest files. Identity is injected by the trusted **test host**, not from the model, and there is no transport accepting real external user credentials. On denial, response content is `null`; audit does not contain source text.

This is a meaningful protocol integration over pure policy unit tests, but **NOT** a production MCP deployment, real OIDC verification or a connected OpenCode MCP client. It exposes no `run()`, does not modify `services/mcp_native/server.py`, does not affect trading tools or CRC, and does not authorize repository writes. Before exposing a process outside the CI test, implement and review actual host authentication and immutable root configuration, durable audit, TOCTOU-safe file handles, provider auth, and human approval for any write workflows.

Reproduce CI slice locally (in checked-out AA2 PR branch):

```bash
pytest -q tests/test_d099_aa2_policy.py tests/test_d099_aa2_local_gateway.py tests/test_d099_aa2_mcp_evidence.py
```

AA2 remains **OPEN** until real OpenCode/client integration and access-control enforcement are independently evidenced.
