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


def test_late_deny_after_blanket_is_still_safe():
    data = {"permission": [
        {"permission": "*", "pattern": "*", "action": "deny"},
        {"permission": "bash", "pattern": "*", "action": "deny"},
    ]}
    result = inspect(data)
    assert result["status"] == "POLICY_RESOLVED_PASS"
    assert result["global_deny_verified"] is True
    assert result["terminal_deny_all"] is False


def test_late_allow_outside_probed_categories_does_not_claim_global_deny():
    data = {"permission": [
        {"permission": "*", "pattern": "*", "action": "deny"},
        {"permission": "task", "pattern": "unsampled-*", "action": "allow"},
    ]}
    report = inspect(data)
    assert report["status"] == "TARGETED_DENY_PASS_GLOBAL_UNVERIFIED"
    assert report["global_deny_verified"] is False
    assert report["allow_or_ask_after_blanket"] == 1
    assert report["reopening_categories"] == ["task"]
    assert report["runtime_denial_proven"] is False


def test_late_ask_also_blocks_global_deny_claim():
    data = {"permission": [
        {"permission": "*", "pattern": "*", "action": "deny"},
        {"permission": "skill", "pattern": "*", "action": "ask"},
    ]}
    report = inspect(data)
    assert report["status"] == "TARGETED_DENY_PASS_GLOBAL_UNVERIFIED"
    assert report["reopening_categories"] == ["skill"]


def test_missing_catchall_while_some_tests_deny_stays_unverified():
    data = {"permission": [
        {"permission": "bash", "pattern": "*", "action": "deny"},
        {"permission": "edit", "pattern": "*", "action": "deny"},
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


def test_no_private_rule_patterns_in_output():
    record = {"permission": [
        {"permission": "*", "pattern": "*", "action": "deny"},
        {"permission": "skill", "pattern": "Users\\\\private\\\\credential.md", "action": "allow"},
    ]}
    result = inspect(record)
    assert "private" not in str(result)
    assert "credential" not in str(result)
