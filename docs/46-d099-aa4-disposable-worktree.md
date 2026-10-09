# D099 AA4 — Real ephemeral Git worktree, fictional only

`controlled_fixture_builder.py` creates a disposable Git repository
in its own `TemporaryDirectory`, pins a commit, creates a separate
worktree branch, edits exactly `docs/notice.md` with **fixed
literal test content**, checks `git diff --check` and scope, checks
original branch unchanged, then removes the worktree. It uses host Git
and Python, without Git remotes, arbitrary shell snippets, filesystem
paths from agents, credentials, network, push, merge or CRC.

The CI result is genuine *synthetic worktree execution*, but it is
**NOT** an authorized Maya build against a real repository, does not
run independently approved product tests and does not qualify
`AA4_CONTROLLED_BUILD_VALIDATED`. Next: reviewed artifact/source
binding, human HITL approval from a verified independent identity,
limited filesystem handle sandbox, bounded test execution and
externally retained independent reviewer evidence.

Run in TradeOps repo:
`python -m services.solution_architect.controlled_fixture_builder`
or `pytest -q tests/test_d099_aa4_fixture_builder.py`.
