from scripts.i13_validate_web_cockpit import validate_web_cockpit


def test_web_cockpit_contract_is_complete():
    assert validate_web_cockpit() == []
