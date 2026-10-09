# D099 AA2 — Local evidence gateway, CI adapter (no OpenCode integration)

This proof connects existing `MayaPolicyGate` to **one actual operation**: reading a bounded UTF-8 file inside a trusted allowlisted repository root. The repository root and authenticated `SecurityPrincipal` are supplied by a **trusted host adapter**; neither should be constructed from LLM content. Tested using disposable pytest files, without any GitHub account, Ollama model, CRC or network request.

Security boundary:

- `repo.read` only, behind the existing deny-by-default role/scope policy;
- rejects any other action including shell, Git writes, and OpenShift mutations;
- requires trusted repository root and tenant/repo identity checks;
- denies unsafe path components, missing files, non-allowed extensions, symlink components and files over 128 KiB;
- captures a minimal local in-memory **adapter-side event** with decision and content hash, not raw contents.
- does not persist the event remotely or guarantee integrity against a privileged local process;
- path checking + `read_bytes` has an acknowledged time-of-check/time-of-use (TOCTOU) race if a hostile process can modify the filesystem, which a production adapter must fix via OS handle-based/no-follow semantics;
- **not a production GitHub connector, not an OpenCode tool router, not an OIDC gateway**, not a durable approval/audit store, and not actual end-to-end authorization enforcement.

Run: `pytest -q tests/test_d099_aa2_policy.py tests/test_d099_aa2_local_gateway.py`.

The next integration boundary, AA2-OpenCode, requires a vetted read-only tool interface with client-side tool registration, a server-side trusted identity, immutable allowlists, version-locked canonical role policies and independent external audit. That would be a new test/evidence gate, NOT implied by these pytest runs.

## Policy provenance / canonical reuse

Canonical role policy is owned by `zdmooc/maya-ai-agentic-architecture-reference`, file `solution-architect-agent/policies/role-profiles.json` (currently method PR #4). TradeOps **must not invent or silently change a second independent role catalog**.

The optional offline `policy_loader.load_policy(path, expected_sha256=...)` accepts only a bounded, valid local JSON with SHA-256 matching a **trusted, out-of-band pinned digest from an independently reviewed hub commit** and matching policy version. It returns the existing `MayaPolicyGate`. Missing hash, mismatches, invalid permissions, and symlinked policy file fail closed. Tests use synthetic policy files and do not fetch an unmerged PR at runtime.

A correct policy digest does not authenticate the user, prove the tool gateway is connected to OpenCode, or demonstrate remote audit. Still pending: approved canonical commit, trusted policy distribution, authenticated server-side principal/scopes, handle-based file open, durable approval ledger, and OpenCode integration.
