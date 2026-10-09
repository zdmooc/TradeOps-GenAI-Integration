"""AA5 OpenHands proposal guard is static, no Docker or image pull."""
import pytest
from services.solution_architect.sandbox_contract import inspect_sandbox


def spec():
    return {
        "engine": "openhands", "image_digest": "sha256:" + "a" * 64,
        "network_mode": "none", "privileged": False,
        "read_only_rootfs": True, "run_as_non_root": True,
        "drop_capabilities": "ALL", "no_new_privileges": True,
        "memory_limit_mib": 2048, "cpu_limit": 2,
        "mounts": ["/input:ro", "/workspace:rw"],
        "docker_socket": False, "host_pid": False, "host_ipc": False,
        "seccomp_profile": "runtime/default",
        "writes_allowed_under": "/workspace",
    }


def test_bounded_fixture_plan_is_only_static():
    report = inspect_sandbox(spec())
    assert report["status"] == "AA5_SANDBOX_CONTRACT_STATIC_PASS"
    assert report["container_started"] is False
    assert report["AA5_SANDBOXED_BUILDER_VALIDATED"] is False


@pytest.mark.parametrize("name,value,violation", [
    ("network_mode", "host", "NETWORK_NOT_ISOLATED"),
    ("privileged", True, "PRIVILEGE_REQUIRED_FALSE"),
    ("docker_socket", True, "DOCKER_SOCKET_DENIED"),
    ("mounts", ["/:/rw"], "MOUNTS_NOT_BOUNDED"),
    ("cpu_limit", 64, "CPU_LIMIT_INVALID"),
    ("memory_limit_mib", 99999, "MEMORY_LIMIT_INVALID"),
    ("seccomp_profile", "unconfined", "SECCOMP_MUST_BE_DEFAULT"),
    ("read_only_rootfs", False, "ROOTFS_MUST_BE_READ_ONLY"),
])
def test_unsafe_sandbox_settings_denied(name, value, violation):
    payload = spec()
    payload[name] = value
    assert violation in inspect_sandbox(payload)["violations"]


def test_cannot_claim_host_approval_or_allow_extra_fields():
    payload = spec()
    payload["approved_by"] = "assistant"
    assert "SANDBOX_SPEC_FIELDS_UNREVIEWED" in inspect_sandbox(payload)["violations"]
