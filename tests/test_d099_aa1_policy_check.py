"""Tests only synthetic policy records. No OpenCode binary or user config."""
from scripts.d099_aa1_policy_check import decision, inspect


def test_operator_policy_sequence_passes():
    rules = [
        {"permission": "*", "pattern": "*", "action": "allow"},
        {"permission": "edit", "pattern": "*", "action": "deny"},
        {"permission": "edit", "pattern": ".opencode\\\\plans\\\\*.md", "action": "allow"},
        {"permission": "*", "pattern": "*", "action": "deny"},
        {"permission": "bash", "pattern": "*", "action": "deny"},
        {"permission": "edit", "pattern": "*", "action": "deny"},
        {"permission": "*", "pattern": "*", "action": "deny"},
    ]
    result = inspect({"permission": rules})
    assert result["status"] == "POLICY_RESOLVED_PASS"
    assert result["runtime_denial_proven"] is False
    assert result["permission_tests"]["bash"] == ["deny"] * 3


def test_late_edit_override_fails():
    data = {"permission": [
        {"permission": "*", "pattern": "*", "action": "deny"},
        {"permission": "edit", "pattern": "*", "action": "allow"},
    ]}
    assert inspect(data)["status"] == "FAIL"


def test_late_terminal_rule_required():
    data = {"permission": [
        {"permission": "*", "pattern": "*", "action": "deny"},
        {"permission": "bash", "pattern": "*", "action": "deny"},
    ]}
    assert inspect(data)["status"] == "FAIL"


def test_unknown_and_malformed_fail_closed():
    for data in ({}, {"permission": [{"permission": "*", "pattern": "*",
                                       "action": "maybe"}]}, []):
        assert inspect(data)["status"] == "FAIL"


def test_last_matching_deny_wins():
    rules = [
        {"permission": "*", "pattern": "*", "action": "allow"},
        {"permission": "edit", "pattern": "*", "action": "allow"},
        {"permission": "edit", "pattern": "*", "action": "deny"},
    ]
    assert decision(rules, "edit", "docs/adr.md") == "deny"
