# D099 AA2 — adapter-side event inventory (test-host scope)

`LocalEvidenceGateway` emits a **bounded in-memory** decision event
with trusted host tenant, subject, abstract action/repository, code,
boolean allowed and content SHA-256 on successful read. It never records
source text, secrets, file paths or raw arguments.

`adapter_audit_review.review_events` checks event structure, tenant,
subject, approved repository on successful read, valid SHA, denied
content hash absent and forbidden tool names. The synthetic pytest
suite includes good/denied reads, cross-tenant and malicious events.

**Truth boundary:** the caller could forge a Python event list, and a
local attacker could alter the list; this is NOT an independently
authenticated, tamper-proof, persistent audit. It does NOT establish
real OIDC or OpenCode MCP client integration, process isolation,
TOCTOU-safe file I/O or an AA2 acceptance gate. A future real deployment
needs immutable host identity and repo-root attestation, append-only
telemetry with authenticated provenance, approved tenant scope,
per-action policy checks and separate human review. No runtime or
model inference is executed in this PR.
