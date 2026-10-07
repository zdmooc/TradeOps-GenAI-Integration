#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

BINARY_MEMORY = {
    "Ki": Decimal(1024),
    "Mi": Decimal(1024**2),
    "Gi": Decimal(1024**3),
    "Ti": Decimal(1024**4),
    "Pi": Decimal(1024**5),
    "Ei": Decimal(1024**6),
}
DECIMAL_MEMORY = {
    "k": Decimal(1000),
    "K": Decimal(1000),
    "M": Decimal(1000**2),
    "G": Decimal(1000**3),
    "T": Decimal(1000**4),
    "P": Decimal(1000**5),
    "E": Decimal(1000**6),
}


def cpu_to_millicores(value: str | int | float | None) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    raw = str(value)
    if raw.endswith("m"):
        return Decimal(raw[:-1])
    if raw.endswith("u"):
        return Decimal(raw[:-1]) / Decimal(1000)
    if raw.endswith("n"):
        return Decimal(raw[:-1]) / Decimal(1_000_000)
    return Decimal(raw) * Decimal(1000)


def memory_to_bytes(value: str | int | float | None) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    raw = str(value)
    for suffix, multiplier in BINARY_MEMORY.items():
        if raw.endswith(suffix):
            return Decimal(raw[: -len(suffix)]) * multiplier
    for suffix, multiplier in DECIMAL_MEMORY.items():
        if raw.endswith(suffix):
            return Decimal(raw[: -len(suffix)]) * multiplier
    return Decimal(raw)


def resource_pair(resources: dict[str, Any] | None) -> tuple[Decimal, Decimal]:
    requests = (resources or {}).get("requests") or {}
    return (
        cpu_to_millicores(requests.get("cpu")),
        memory_to_bytes(requests.get("memory")),
    )


def add_pair(left: tuple[Decimal, Decimal], right: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    return left[0] + right[0], left[1] + right[1]


def max_pair(left: tuple[Decimal, Decimal], right: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    return max(left[0], right[0]), max(left[1], right[1])


def pod_effective_request(pod: dict[str, Any]) -> tuple[Decimal, Decimal]:
    spec = pod.get("spec") or {}

    regular = (Decimal(0), Decimal(0))
    for container in spec.get("containers") or []:
        regular = add_pair(regular, resource_pair(container.get("resources")))

    init_max = (Decimal(0), Decimal(0))
    for container in spec.get("initContainers") or []:
        init_max = max_pair(init_max, resource_pair(container.get("resources")))

    effective = max_pair(regular, init_max)
    overhead = spec.get("overhead") or {}
    return (
        effective[0] + cpu_to_millicores(overhead.get("cpu")),
        effective[1] + memory_to_bytes(overhead.get("memory")),
    )


def unschedulable_message(pod: dict[str, Any]) -> str:
    for condition in (pod.get("status") or {}).get("conditions") or []:
        if (
            condition.get("type") == "PodScheduled"
            and condition.get("status") == "False"
            and condition.get("reason") == "Unschedulable"
        ):
            return str(condition.get("message") or "")
    return ""


def summarize(pods_payload: dict[str, Any], nodes_payload: dict[str, Any]) -> dict[str, Any]:
    scheduled_cpu = Decimal(0)
    scheduled_mem = Decimal(0)
    unscheduled_cpu = Decimal(0)
    unscheduled_mem = Decimal(0)
    active = 0
    scheduled = 0
    pending = 0
    unscheduled = 0
    insufficient_memory = 0
    insufficient_cpu = 0

    for pod in pods_payload.get("items") or []:
        status = pod.get("status") or {}
        phase = status.get("phase") or "Unknown"
        if phase in {"Succeeded", "Failed"}:
            continue

        active += 1
        if phase == "Pending":
            pending += 1

        request = pod_effective_request(pod)
        node_name = (pod.get("spec") or {}).get("nodeName")
        if node_name:
            scheduled += 1
            scheduled_cpu += request[0]
            scheduled_mem += request[1]
        else:
            unscheduled += 1
            unscheduled_cpu += request[0]
            unscheduled_mem += request[1]
            message = unschedulable_message(pod)
            if "Insufficient memory" in message:
                insufficient_memory += 1
            if "Insufficient cpu" in message:
                insufficient_cpu += 1

    alloc_cpu = Decimal(0)
    alloc_mem = Decimal(0)
    ready_nodes = 0
    total_nodes = 0
    for node in nodes_payload.get("items") or []:
        total_nodes += 1
        allocatable = (node.get("status") or {}).get("allocatable") or {}
        alloc_cpu += cpu_to_millicores(allocatable.get("cpu"))
        alloc_mem += memory_to_bytes(allocatable.get("memory"))
        for condition in (node.get("status") or {}).get("conditions") or []:
            if condition.get("type") == "Ready" and condition.get("status") == "True":
                ready_nodes += 1
                break

    mib = Decimal(1024**2)

    def as_int(value: Decimal) -> int:
        return int(value.to_integral_value())

    result = {
        "pods": {
            "active": active,
            "scheduled": scheduled,
            "pending": pending,
            "unscheduled": unscheduled,
            "unscheduled_insufficient_memory": insufficient_memory,
            "unscheduled_insufficient_cpu": insufficient_cpu,
        },
        "requests": {
            "scheduled_cpu_m": as_int(scheduled_cpu),
            "scheduled_memory_mib": as_int(scheduled_mem / mib),
            "unscheduled_cpu_m": as_int(unscheduled_cpu),
            "unscheduled_memory_mib": as_int(unscheduled_mem / mib),
        },
        "nodes": {
            "total": total_nodes,
            "ready": ready_nodes,
            "allocatable_cpu_m": as_int(alloc_cpu),
            "allocatable_memory_mib": as_int(alloc_mem / mib),
        },
    }
    if alloc_cpu:
        result["requests"]["scheduled_cpu_pct_allocatable"] = round(
            float(scheduled_cpu * 100 / alloc_cpu), 2
        )
    if alloc_mem:
        result["requests"]["scheduled_memory_pct_allocatable"] = round(
            float(scheduled_mem * 100 / alloc_mem), 2
        )
    return result


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Kubernetes pod requests and node capacity.")
    parser.add_argument("--pods", required=True, type=Path)
    parser.add_argument("--nodes", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = summarize(load_json(args.pods), load_json(args.nodes))
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
