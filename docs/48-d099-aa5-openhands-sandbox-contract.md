# D099 AA5 — sandbox contract, NOT OpenHands execution

Only a *static configuration validator* `sandbox_contract.py`
was prepared. A future OpenHands run must use a verified immutable
image digest, dedicated unprivileged account, network=none,
read-only root filesystem, no Docker socket or host namespaces,
ALL capabilities dropped, default seccomp, explicit RAM/CPU limits,
isolated worktree mounted under /workspace, and separate read-only
reference inputs. These constraints are a proposed baseline, **not**
a guarantee that every OpenHands image actually functions with them.

The tool tests adversarial sandbox proposals. It deliberately
**does not** install/pull images, launch containers, access the host,
mount user repositories, open network channels or authorize edits.
Actual AA5 needs a reviewed/compatible image, real resource and
mount inspection before and after execution, denial probes, rollback
and independent operator approval. Current gate: **OPEN**.
