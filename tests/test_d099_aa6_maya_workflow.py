"""AA6 verifies real LangGraph MemorySaver interrupt and refusal semantics."""
from services.solution_architect.maya_workflow import (
    build_workflow, run_to_review, resume_acknowledgement,
)


def test_failed_gate_never_reaches_interrupt():
    graph = build_workflow()
    result = run_to_review(graph, thread_id="D099-BLOCKED", case_id="NOTIFY-01",
                           facts=True, design=False, policy=True, audit=True)
    assert result["status"] == "REJECTED_PRECHECK_FAILED"
    assert result["build_authorized"] is False
    assert graph.get_state({"configurable": {"thread_id": "D099-BLOCKED"}}).next == ()


def test_all_test_host_gates_pause_at_explicit_review():
    graph = build_workflow()
    config = {"configurable": {"thread_id": "D099-HITL"}}
    result = run_to_review(graph, thread_id="D099-HITL", case_id="NOTIFY-01",
                           facts=True, design=True, policy=True, audit=True)
    assert "__interrupt__" in result
    assert graph.get_state(config).next == ("request_review",)
    acknowledgement = resume_acknowledgement(
        graph, thread_id="D099-HITL", acknowledgement="ACKNOWLEDGE_ONLY")
    assert acknowledgement["status"] == "HUMAN_REVIEW_ACKNOWLEDGED_NOT_APPROVED"
    assert acknowledgement["build_authorized"] is False
    assert acknowledgement["runtime_mutation_authorized"] is False
    assert graph.get_state(config).next == ()


def test_fake_approval_value_can_never_enable_build():
    graph = build_workflow()
    run_to_review(graph, thread_id="D099-FORGERY", case_id="INVENTORY-02",
                  facts=True, design=True, policy=True, audit=True)
    response = resume_acknowledgement(
        graph, thread_id="D099-FORGERY",
        acknowledgement="APPROVED_MERGE_PUSH_APPLY")
    assert response["status"] == "HUMAN_REVIEW_NOT_ACKNOWLEDGED"
    assert response["build_authorized"] is False


def test_missing_identity_of_case_blocks():
    graph = build_workflow()
    result = run_to_review(graph, thread_id="D099-EMPTY", case_id="",
                           facts=True, design=True, policy=True, audit=True)
    assert result["status"] == "REJECTED_MISSING_CASE_ID"
