"""D099 AA5: fail-closed validation of proposed OpenHands sandbox settings.

This only checks a plan. It does not launch Docker/OpenHands or claim OS-level
isolation. The host must independently inspect actual runtime mounts/cgroups.
"""
from __future__ import annotations
import re
from typing import Any

DIGEST = re.compile(r"sha256:[a-f0-9]{64}\Z")
APPROVED_ENGINE = "openhands"
ALLOWED_MOUNTS = frozenset({"/workspace:rw", "/input:ro"})
KNOWN_KEYS = {
    "engine", "image_digest", "network_mode", "privileged",
    "read_only_rootfs", "run_as_non_root", "drop_capabilities",
    "no_new_privileges", "memory_limit_mib", "cpu_limit",
    "mounts", "docker_socket", "host_pid", "host_ipc",
    "seccomp_profile", "writes_allowed_under",
}


def inspect_sandbox(spec: object) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(spec, dict):
        return {"status": "AA5_SANDBOX_CONTRACT_FAIL", "violations": ["SPEC_NOT_OBJECT"],
                "container_started": False, "AA5_SANDBOXED_BUILDER_VALIDATED": False}
    if set(spec) != KNOWN_KEYS:
        issues.append("SANDBOX_SPEC_FIELDS_UNREVIEWED")
    if spec.get("engine") != APPROVED_ENGINE:
        issues.append("ENGINE_NOT_OPENHANDS")
    digest = spec.get("image_digest")
    if not isinstance(digest, str) or DIGEST.fullmatch(digest) is None:
        issues.append("IMAGE_DIGEST_NOT_PINNED")
    if spec.get("network_mode") != "none":
        issues.append("NETWORK_NOT_ISOLATED")
    if spec.get("privileged") is not False:
        issues.append("PRIVILEGE_REQUIRED_FALSE")
    if spec.get("read_only_rootfs") is not True:
        issues.append("ROOTFS_MUST_BE_READ_ONLY")
    if spec.get("run_as_non_root") is not True:
        issues.append("NON_ROOT_REQUIRED")
    if spec.get("drop_capabilities") != "ALL":
        issues.append("CAPABILITIES_MUST_BE_DROPPED")
    if spec.get("no_new_privileges") is not True:
        issues.append("NO_NEW_PRIVILEGES_REQUIRED")
    if spec.get("docker_socket") is not False:
        issues.append("DOCKER_SOCKET_DENIED")
    if spec.get("host_pid") is not False or spec.get("host_ipc") is not False:
        issues.append("HOST_NAMESPACE_DENIED")
    if spec.get("seccomp_profile") != "runtime/default":
        issues.append("SECCOMP_MUST_BE_DEFAULT")
    if spec.get("mounts") != ["/input:ro", "/workspace:rw"]:
        issues.append("MOUNTS_NOT_BOUNDED")
    if spec.get("writes_allowed_under") != "/workspace":
        issues.append("WRITE_SCOPE_NOT_WORKSPACE")
    memory = spec.get("memory_limit_mib")
    cpu = spec.get("cpu_limit")
    if type(memory) is not int or not 256 <= memory <= 8192:
        issues.append("MEMORY_LIMIT_INVALID")
    if type(cpu) not in {int, float} or not 0 < cpu <= 4:
        issues.append("CPU_LIMIT_INVALID")
    return {
        "status": "AA5_SANDBOX_CONTRACT_STATIC_PASS" if not issues else
                  "AA5_SANDBOX_CONTRACT_FAIL",
        "violations": sorted(set(issues)),
        "container_started": False,
        "runtime_isolation_measured": False,
        "AA5_SANDBOXED_BUILDER_VALIDATED": False,
    }
