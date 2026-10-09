"""AA9 replayable offline synthetic evidence pack CI acceptance."""
from services.solution_architect.synthetic_demo import replay


def test_synthetic_replay_passes_without_claiming_real_program_closure():
    report = replay()
    assert report["status"] == "AA9_SYNTHETIC_OFFLINE_REPLAY_PASS"
    assert set(report["statuses"]) == {"AA4", "AA5", "AA6", "AA7", "AA8"}
    assert report["D099_CLOSED"] is False
    assert report["AA9_REPRODUCIBLE_DEMO_VALIDATED"] is False
    assert report["real_model_invoked"] is False
    assert report["docker_or_openhands_started"] is False
    assert report["real_openshift_cluster_contacted"] is False
    assert report["authenticated_human_approval"] is False
