# D-099 AA2 — deterministic policy gate prototype (non-deployed)

Purpose: start implementing the **server-side** guard missing from the AA2 design in the architecture hub. This module deliberately **never executes commands, writes Git, handles kubeconfig or calls CRC**.

Source of truth: versioned `solution-architect-agent/policies/role-profiles.json` in `maya-ai-agentic-architecture-reference` PR #4. A trusted integration adapter must load this versioned policy (and validate digest and schema); it must not accept an agent-supplied profile document. This runtime module expects a previously authenticated `SecurityPrincipal` from `services/security/identity.py` and a `TrustedScope` derived from external IAM/configuration. An LLM must never construct either as trusted input.

- Unknown tools, `git push`, OpenShift mutation, broad delete and cross-tenant operations: DENY, even if a policy file is loosened.
- Scoped read: repo/namespace allowlists; sensitive file path restrictions.
- `repo.edit`/commits needing ASK: authenticated independently issued approval, bound to target identity + exact operation/arguments + expiry + one-time consumption.
- Approvals cannot be created by the maya-* roles. The demo registry is in-memory and not durable, thus **not suitable for distributed production replay protection**.
- The gate checks decisions only, not the downstream executor. A real gateway must re-check at execution time (TOCTOU), pin repository revisions, reject symlinks after filesystem resolution, bind IAM tenant, and log redacted tool calls.

Run: `pytest -q tests/test_d099_aa2_policy.py` plus normal TradeOps CI.

Truth boundary: this PR proves isolated policy mechanics in CI, NOT AA2 end-to-end enforcement, NOT live OpenCode permission enforcement, NOT Kubernetes authorization, NOT a deployed identity gateway. Approval changes and cluster mutations remain separately governed.
