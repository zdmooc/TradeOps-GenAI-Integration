from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate() -> list[str]:
    errors: list[str] = []
    required = (
        "services/a2a_ops_agent/main.py",
        "services/a2a_ops_agent/run.py",
        "tests/test_a2a_interop_d092.py",
        "infra/ai-access/values-a2a.example.yaml",
    )
    for path in required:
        if not (ROOT / path).is_file():
            errors.append(f"missing D-092 A2A artifact: {path}")
    if errors:
        return errors

    requirements = read("requirements.txt")
    if "a2a-sdk==1.2.1" not in requirements:
        errors.append("a2a-sdk must be pinned to 1.2.1")

    service = read("services/a2a_ops_agent/main.py")
    for marker in (
        "AgentCard(",
        'protocol_binding="JSONRPC"',
        'protocol_version="1.0"',
        "payment_mq_health",
        "payment_mq_queue_status",
        "A2A_PEER_DENIED",
        "get_payment_mq_health",
        "get_mq_queue_status",
        "source",
        "native-mcp",
    ):
        if marker not in service:
            errors.append(f"A2A baseline missing: {marker}")

    values = read("infra/helm/tradeops/values.yaml")
    if "a2a-ops-agent:" not in values or "module: services.a2a_ops_agent.run" not in values:
        errors.append("A2A workload not packaged in Helm")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"D092_A2A_VALIDATION_FAIL: {error}")
        return 1
    print("D092_A2A_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
