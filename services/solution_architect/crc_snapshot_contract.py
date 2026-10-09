"""D099 AA8: validate sanitized operator-supplied CRC read-only inventory.

No oc client, kubeconfig, shell, HTTP, model inference, secret export,
cluster connectivity or mutation. Validation alone cannot prove runtime.
"""
from __future__ import annotations

import re
from typing import Any

NAMESPACES = frozenset({"instant-payments-local", "shared-platform-services"})
REPO_SCOPES = frozenset({"d099.readonly.inventory"})
KINDS = frozenset({"Deployment", "Service", "Route", "Pod"})
NAME = re.compile(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?\Z")


def verify_readonly_inventory(data: object) -> dict[str, Any]:
    faults: list[str] = []
    if not isinstance(data, dict):
        data = {}
        faults.append("SNAPSHOT_NOT_OBJECT")
    if set(data) != {"scope", "namespace", "cluster_version",
                     "observed_utc", "workloads", "read_only"}:
        faults.append("INVENTORY_SCHEMA_NOT_ALLOWLISTED")
    if data.get("scope") not in REPO_SCOPES:
        faults.append("UNKNOWN_CRC_INVENTORY_SCOPE")
    if data.get("namespace") not in NAMESPACES:
        faults.append("NAMESPACE_OUT_OF_SCOPE")
    if data.get("read_only") is not True:
        faults.append("READ_ONLY_FALSE_OR_MISSING")
    version = data.get("cluster_version")
    if not isinstance(version, str) or re.fullmatch(
        r"4\.\d{1,3}\.\d{1,3}", version
    ) is None:
        faults.append("CLUSTER_VERSION_INVALID")
    timestamp = data.get("observed_utc")
    if not isinstance(timestamp, str) or re.fullmatch(
        r"20\d{2}-\d\d-\d\dT\d\d:\d\d:\d\dZ", timestamp
    ) is None:
        faults.append("UTC_TIMESTAMP_MISSING")
    workloads = data.get("workloads")
    if not isinstance(workloads, list) or len(workloads) > 100:
        faults.append("WORKLOAD_INVENTORY_INVALID")
        workloads = []
    for item in workloads:
        if not isinstance(item, dict) or set(item) != {"kind", "name", "ready"}:
            faults.append("WORKLOAD_FIELDS_UNSAFE")
            continue
        if item.get("kind") not in KINDS:
            faults.append("WORKLOAD_KIND_DENIED")
        name = item.get("name")
        if not isinstance(name, str) or len(name) > 63 or NAME.fullmatch(name) is None:
            faults.append("WORKLOAD_NAME_INVALID")
        if type(item.get("ready")) is not bool:
            faults.append("WORKLOAD_READY_INVALID")
    return {
        "status": "AA8_SANITIZED_SNAPSHOT_STATIC_PASS" if not faults else
                  "AA8_SANITIZED_SNAPSHOT_REJECTED",
        "violations": sorted(set(faults)),
        "runtime_connection_made": False,
        "captured_by_authenticated_host": False,
        "cluster_mutation_performed": False,
        "AA8_CRC_READONLY_VALIDATED": False,
    }
