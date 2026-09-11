"""LangGraph orchestration for governed specialist-agent assessment.

I6 replaces the legacy heuristic-confidence trade graph with an analysis-only
specialist graph. Deterministic calculations remain outside the agent layer.
No node can place an order; execution and HITL are intentionally deferred to I7.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .contracts import AgentContext, AgentFinding, AgenticAssessment
from .specialists import (
    fusion_agent,
    macro_agent,
    market_agent,
    pattern_agent,
    risk_agent,
    technical_agent,
)


class I6GraphState(TypedDict, total=False):
    context: AgentContext
    findings: list[AgentFinding]
    assessment: AgenticAssessment


def _append_finding(
    state: I6GraphState,
    finding: AgentFinding,
) -> I6GraphState:
    return {"findings": [*state.get("findings", []), finding]}


def _market_node(state: I6GraphState) -> I6GraphState:
    return _append_finding(state, market_agent(state["context"]))


def _technical_node(state: I6GraphState) -> I6GraphState:
    return _append_finding(state, technical_agent(state["context"]))


def _pattern_node(state: I6GraphState) -> I6GraphState:
    return _append_finding(state, pattern_agent(state["context"]))


def _macro_node(state: I6GraphState) -> I6GraphState:
    return _append_finding(state, macro_agent(state["context"]))


def _risk_node(state: I6GraphState) -> I6GraphState:
    return _append_finding(state, risk_agent(state["context"]))


def _fusion_node(state: I6GraphState) -> I6GraphState:
    return {
        "assessment": fusion_agent(
            state["context"],
            state.get("findings", []),
        )
    }


def build_agent_graph():
    graph = StateGraph(I6GraphState)
    graph.add_node("market", _market_node)
    graph.add_node("technical", _technical_node)
    graph.add_node("pattern", _pattern_node)
    graph.add_node("macro", _macro_node)
    graph.add_node("risk", _risk_node)
    graph.add_node("fusion", _fusion_node)

    graph.add_edge(START, "market")
    graph.add_edge("market", "technical")
    graph.add_edge("technical", "pattern")
    graph.add_edge("pattern", "macro")
    graph.add_edge("macro", "risk")
    graph.add_edge("risk", "fusion")
    graph.add_edge("fusion", END)
    return graph.compile()


_AGENT_GRAPH = build_agent_graph()


def run_agent_graph(context: AgentContext) -> AgenticAssessment:
    result = _AGENT_GRAPH.invoke({"context": context, "findings": []})
    assessment = result.get("assessment")
    if assessment is None:
        raise RuntimeError("LangGraph completed without an assessment")
    return assessment
