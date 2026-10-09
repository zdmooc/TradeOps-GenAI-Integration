"""AA7 synthetic policy invariance negative corpus, NOT model eval."""
from services.solution_architect.adversarial_synthetic import (
    ATTACKS, inspect_host_policy_invariance,
)


def test_host_policy_does_not_accept_untrusted_text_as_role():
    result = inspect_host_policy_invariance()
    assert result["attack_cases"] == 8
    assert result["denied_tool_attempts"] == 8 * 6
    assert result["status"] == "AA7_HOST_POLICY_INVARIANCE_SYNTHETIC_PASS"
    assert result["model_prompt_injection_resistance_tested"] is False
    assert result["AA7_AGENT_EVALS_AND_POLICY_VALIDATED"] is False


def test_attack_fixtures_are_distinct_named_cases():
    assert len({name for name, _ in ATTACKS}) == len(ATTACKS)
    assert all(len(payload) > 10 for _, payload in ATTACKS)
