"""D099 AA6: LangGraph human-interrupt scaffold, NO privileged execution.

The caller/host provides the prior gate decisions; values are NOT attested
and can never authorize a write. MemorySaver is volatile, NOT a durable
production checkpointer. This does not affect the trading-agent graph.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class MayaFlowState(TypedDict, total=False):
    case_id: str
    fact_gate_pass: bool
    design_gate_pass: bool
    policy_gate_pass: bool
    audit_gate_pass: bool
    review_note: str
    status: str
    build_authorized: bool
    runtime_mutation_authorized: bool


def _preflight(state: MayaFlowState) -> MayaFlowState:
    required = ("fact_gate_pass", "design_gate_pass",
                "policy_gate_pass", "audit_gate_pass")
    if not isinstance(state.get("case_id"), str) or not state["case_id"].strip():
        return {"status": "REJECTED_MISSING_CASE_ID",
                "build_authorized": False,
                "runtime_mutation_authorized": False}
    if not all(state.get(field) is True for field in required):
        return {"status": "REJECTED_PRECHECK_FAILED",
                "build_authorized": False,
                "runtime_mutation_authorized": False}
    return {"status": "AWAITING_INDEPENDENT_HUMAN_REVIEW",
            "build_authorized": False,
            "runtime_mutation_authorized": False}


def _next(state: MayaFlowState) -> str:
    return "request_review" if state["status"] == (
        "AWAITING_INDEPENDENT_HUMAN_REVIEW"
    ) else "stop"


def _request_review(state: MayaFlowState) -> MayaFlowState:
    """An LLM/client resume is only an acknowledgement, never approval."""
    answer = interrupt({
        "status": "HUMAN_REVIEW_REQUESTED",
        "case_id": state["case_id"],
        "external_authenticated_approval_required": True,
        "execution_authorized": False,
    })
    return {
        "review_note": "ACKNOWLEDGED" if answer == "ACKNOWLEDGE_ONLY"
                       else "REJECTED",
        "status": ("HUMAN_REVIEW_ACKNOWLEDGED_NOT_APPROVED"
                   if answer == "ACKNOWLEDGE_ONLY"
                   else "HUMAN_REVIEW_NOT_ACKNOWLEDGED"),
        "build_authorized": False,
        "runtime_mutation_authorized": False,
    }


def build_workflow():
    graph = StateGraph(MayaFlowState)
    graph.add_node("preflight", _preflight)
    graph.add_node("request_review", _request_review)
    graph.add_node("stop", lambda state: {
        "status": state["status"],
        "build_authorized": False,
        "runtime_mutation_authorized": False,
    })
    graph.add_edge(START, "preflight")
    graph.add_conditional_edges("preflight", _next,
                                {"request_review": "request_review",
                                 "stop": "stop"})
    graph.add_edge("request_review", END)
    graph.add_edge("stop", END)
    return graph.compile(checkpointer=MemorySaver())


def run_to_review(graph, *, thread_id: str, case_id: str,
                  facts: bool, design: bool, policy: bool, audit: bool):
    if not thread_id or not isinstance(thread_id, str):
        raise ValueError("D099_THREAD_ID_REQUIRED")
    return graph.invoke({
        "case_id": case_id,
        "fact_gate_pass": facts, "design_gate_pass": design,
        "policy_gate_pass": policy, "audit_gate_pass": audit,
    }, config={"configurable": {"thread_id": thread_id}})


def resume_acknowledgement(graph, *, thread_id: str, acknowledgement: str):
    return graph.invoke(Command(resume=acknowledgement),
                        config={"configurable": {"thread_id": thread_id}})
