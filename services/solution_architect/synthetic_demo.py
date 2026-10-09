"""D099 AA9 synthetic offline replay across prepared AA4-AA8 components.

Never performs a real Maya LLM analysis, trusted external approval,
production/CRC access, Docker/OpenHands execution or Git remote push.
"""
from __future__ import annotations
import json

from services.solution_architect.adversarial_synthetic import inspect_host_policy_invariance
from services.solution_architect.controlled_fixture_builder import simulate
from services.solution_architect.crc_snapshot_contract import verify_readonly_inventory
from services.solution_architect.maya_workflow import (
    build_workflow, run_to_review, resume_acknowledgement,
)
from services.solution_architect.sandbox_contract import inspect_sandbox


def replay() -> dict[str, object]:
    aa4 = simulate()
    aa5 = inspect_sandbox({
        "engine": "openhands", "image_digest": "sha256:" + "a" * 64,
        "network_mode": "none", "privileged": False,
        "read_only_rootfs": True, "run_as_non_root": True,
        "drop_capabilities": "ALL", "no_new_privileges": True,
        "memory_limit_mib": 2048, "cpu_limit": 2,
        "mounts": ["/input:ro", "/workspace:rw"],
        "docker_socket": False, "host_pid": False, "host_ipc": False,
        "seccomp_profile": "runtime/default",
        "writes_allowed_under": "/workspace",
    })
    graph = build_workflow()
    first = run_to_review(graph, thread_id="aa9-synthetic",
                          case_id="INVENTORY-02", facts=True, design=True,
                          policy=True, audit=True)
    if "__interrupt__" not in first:
        raise AssertionError("AA6_DID_NOT_INTERRUPT")
    second = resume_acknowledgement(
        graph, thread_id="aa9-synthetic", acknowledgement="ACKNOWLEDGE_ONLY")
    aa7 = inspect_host_policy_invariance()
    aa8 = verify_readonly_inventory({
        "scope": "d099.readonly.inventory",
        "namespace": "instant-payments-local",
        "cluster_version": "4.22.7",
        "observed_utc": "2026-10-09T13:00:00Z",
        "workloads": [{"kind": "Deployment", "name": "synthetic-workload",
                       "ready": True}],
        "read_only": True,
    })
    statuses = {
        "AA4": aa4["status"], "AA5": aa5["status"],
        "AA6": second["status"], "AA7": aa7["status"], "AA8": aa8["status"],
    }
    okay = (
        aa4["origin_unchanged"] and not aa4["AA4_CONTROLLED_BUILD_VALIDATED"]
        and aa5["status"] == "AA5_SANDBOX_CONTRACT_STATIC_PASS"
        and second["build_authorized"] is False
        and second["runtime_mutation_authorized"] is False
        and aa7["denied_tool_attempts"] == 48
        and aa8["status"] == "AA8_SANITIZED_SNAPSHOT_STATIC_PASS"
        and not aa8["runtime_connection_made"]
    )
    return {
        "status": "AA9_SYNTHETIC_OFFLINE_REPLAY_PASS" if okay else
                  "AA9_SYNTHETIC_OFFLINE_REPLAY_FAIL",
        "statuses": statuses,
        "real_model_invoked": False,
        "real_customer_repository_edited": False,
        "real_openshift_cluster_contacted": False,
        "docker_or_openhands_started": False,
        "authenticated_human_approval": False,
        "independent_runtime_tool_audit": False,
        "AA9_REPRODUCIBLE_DEMO_VALIDATED": False,
        "D099_CLOSED": False,
    }


if __name__ == "__main__":
    report = replay()
    print(json.dumps(report, sort_keys=True, indent=2))
    raise SystemExit(0 if report["status"] == (
        "AA9_SYNTHETIC_OFFLINE_REPLAY_PASS"
    ) else 2)
