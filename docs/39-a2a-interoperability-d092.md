# D-092 — A2A interoperability baseline over native MCP

**Date:** 2026-10-04  
**Status:** IMPLEMENTED + TESTED IN CI / LIVE A2A INTEROPERABILITY PENDING

## Purpose

Add a real A2A SDK boundary above the existing native MCP runtime without weakening the deterministic authorization/HITL model.

Target:

```text
Investigation Agent
  identity: investigation-agent
       |
       | A2A JSON-RPC / protocol 1.0
       v
Payment Operations Agent
  identity: operations-agent
  skills:
    - payment_mq_health
    - payment_mq_queue_status
       |
       | re-authorize downstream access
       v
native MCP
       |
       v
IBM MQ payment operations adapter
```

## Current protocol baseline

Dated 2026-10-04:

- A2A specification release observed: **v1.0.1**;
- A2A wire protocol used by the SDK/server interface: **1.0**;
- Python SDK pinned by this repository: **a2a-sdk==1.2.1**.

The implementation uses the current v1 route-factory model:

- `AgentExecutor`;
- `RequestContext`;
- `DefaultRequestHandler`;
- `InMemoryTaskStore`;
- `TaskUpdater`;
- `create_agent_card_routes`;
- `create_jsonrpc_routes`.

## Implemented

`services/a2a_ops_agent/main.py` provides:

- one versioned Agent Card;
- JSON-RPC A2A interface;
- two bounded Payment Operations skills;
- explicit peer allowlist;
- denied unknown peer;
- denied unknown skill;
- task working/completed/rejected/failed/canceled states;
- downstream reuse of the already-existing native MCP client;
- result provenance with `source=native-mcp`.

`services/a2a_ops_agent/run.py` packages the service on port 8021.

The Helm workload `a2a-ops-agent` is disabled by default and can be enabled with:

```text
infra/ai-access/values-a2a.example.yaml
```

## Security boundary

The initial baseline proves the application-side identity/skill policy contract.

It does **not** yet claim enterprise A2A transport authentication. Live graduation must bind the peer identity to authenticated transport/IAM rather than trusting client-provided metadata.

The Operations Agent independently re-authorizes downstream MCP operations. A2A delegation never grants transitive MCP privilege.

Sensitive MCP mutation remains governed by the existing reviewer/HITL flow.

## Existing MCP evidence

TradeOps already contains the native MCP implementation. R1-R4 are tested in CI; the R5 native-MCP-to-IBM-MQ live CRC evidence remains pending until the local R5 evidence bundle exists.

Therefore the remaining D-092 evidence gap is specifically:

```text
A2A live client/server interoperability
  -> authenticated peer identity
  -> approved skill
  -> downstream native MCP call
  -> correlated evidence
```

not “implement MCP from scratch”.

## Tests added

`tests/test_a2a_interop_d092.py` covers:

- Agent Card exposes the two bounded skills;
- `investigation-agent` can invoke Payment MQ health through the MCP provider seam;
- `rogue-agent` is denied before MCP;
- an unapproved skill is denied;
- health and Agent Card HTTP endpoints are exposed.

Static packaging validator:

```bash
python scripts/d092_validate_a2a.py
```

## Runtime graduation gate

Do not claim `A2A_RUNTIME_INTEROPERABILITY` until an observed run proves:

1. Investigation Agent and Operations Agent are independently running;
2. Agent Card discovery succeeds;
3. peer identity is authenticated;
4. approved A2A task succeeds;
5. unauthorized peer/skill is denied;
6. downstream native MCP call succeeds;
7. timeout/cancellation/failure behavior is observed;
8. trace/correlation spans both agents and MCP;
9. protocol/application versions are captured;
10. no broad or transitive tool privilege is introduced.

Current claim remains:

```text
A2A SDK baseline = IMPLEMENTED
A2A tests = ADDED / CI EVIDENCE TO OBSERVE
A2A live interoperability = PENDING
native MCP R1-R4 = TESTED IN CI
R5 native MCP -> IBM MQ live CRC = PENDING
```
