# D099 AA8 — sanitized offline CRC inventory contract

The only AA8 artifact prepared here is an **offline validator** of
an operator-supplied sanitized read-only summary. Allowed fields:
scope, namespace, version, UTC observation time, workload kind/name/
ready, and an explicit read-only declaration. The validator rejects
secrets, kubeconfig, arbitrary annotations, commands and resources
outside the two preapproved example namespaces.

The CI test snapshot is completely synthetic; the occurrence of the
current CRC version string `4.22.7` in a fixture is NOT evidence
that any cluster was queried. No call to `oc`, `kubectl`, API server,
Ollama, Argo CD or other mutating tool happens in this component.
A self-declared `read_only=true` is not trustworthy independent
action telemetry.

**To close AA8:** authenticated authorized host-side observer, scoped
service account, `oc auth can-i` negative permissions, independent
tool trajectory/denial audit, version/namespace workload captures,
CRC before/after non-mutation evidence, and human approval.
Do not run on user's CRC without explicit authorization.
