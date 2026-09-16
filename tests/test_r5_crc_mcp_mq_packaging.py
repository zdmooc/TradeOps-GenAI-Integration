from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_helm_deploys_native_mcp_and_agent_points_to_it() -> None:
    values = _read("infra/helm/tradeops/values.yaml")
    assert "mcp-native:" in values
    assert "module: services.mcp_native.server" in values
    assert "MCP_NATIVE_URL: http://mcp-native:8017/mcp" in values
    assert "MQ_OPS_API_URL: http://mq-ops-api.mayabank-mq-local.svc.cluster.local:8080" in values
    assert "secretKey: MQ_OPS_API_TOKEN" in values
    assert "tcpProbe: true" in values


def test_native_mcp_has_only_targeted_cross_namespace_egress() -> None:
    policy = _read("infra/openshift/base/networkpolicies.yaml")
    assert "name: allow-mcp-native-to-mayabank-mq-ops" in policy
    assert "app.kubernetes.io/name: mcp-native" in policy
    assert "kubernetes.io/metadata.name: mayabank-mq-local" in policy
    assert "app: mq-ops-api" in policy
    assert "port: 8080" in policy


def test_crc_deploy_secret_contains_mq_ops_token() -> None:
    script = _read("scripts/i9_crc_deploy.sh")
    assert "MQ_OPS_SERVICE_TOKEN" in script
    assert "MQ_OPS_API_TOKEN" in script


def test_r5_evidence_compares_mcp_and_runmqsc_depth() -> None:
    script = _read("scripts/r5_crc_mcp_mq_verify.sh")
    assert "/agent/mcp/mq/queues/PAYMENT.REQUEST.Q" in script
    assert "runmqsc QM.MAYABANK" in script
    assert '[[ "$MCP_DEPTH" == "$MQ_DEPTH" ]]' in script
    assert "SYSTEM.ADMIN.COMMAND.QUEUE" in script
    assert "DIRECT_BYPASS_DENIED=PASS" in script
    assert "R5_CRC_MCP_MQ_VERIFY_PASS" in script
