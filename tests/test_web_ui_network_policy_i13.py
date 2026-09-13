from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_ui_egress_is_limited_to_declared_backends():
    policy = (ROOT / "infra/openshift/base/networkpolicies.yaml").read_text(encoding="utf-8")
    assert "name: allow-tradeops-ui-backends" in policy
    assert "app.kubernetes.io/name: tradeops-ui" in policy
    assert "values: [market-data, workflow-api, agent-controller]" in policy
    for port in (8011, 8012, 8015):
        assert f"port: {port}" in policy


def test_generic_intra_namespace_policy_excludes_web_ui():
    policy = (ROOT / "infra/openshift/base/networkpolicies.yaml").read_text(encoding="utf-8")
    start = policy.index("name: allow-intra-namespace")
    end = policy.index("name: allow-tradeops-ui-backends")
    block = policy[start:end]
    assert "operator: NotIn" in block
    assert "values: [tradeops-ui]" in block
