from __future__ import annotations

from collections.abc import Iterable

from .contracts import (
    AgentContext,
    AgentFinding,
    AgentStatus,
    AgenticAssessment,
    Direction,
)


def market_agent(context: AgentContext) -> AgentFinding:
    if context.event_age_ms is None:
        return AgentFinding(
            agent="MarketAgent",
            status=AgentStatus.UNKNOWN,
            reasons=("market event age is unavailable",),
        )
    if context.event_age_ms > context.max_freshness_ms:
        return AgentFinding(
            agent="MarketAgent",
            status=AgentStatus.DATA_STALE,
            reasons=(
                f"market data age {context.event_age_ms:.0f}ms exceeds "
                f"{context.max_freshness_ms:.0f}ms",
            ),
        )
    if context.market_direction is Direction.UNKNOWN:
        return AgentFinding(
            agent="MarketAgent",
            status=AgentStatus.UNKNOWN,
            evidence_quality=0.5,
            reasons=("market direction was not supplied by deterministic market analysis",),
        )
    return AgentFinding(
        agent="MarketAgent",
        status=AgentStatus.SUPPORTED,
        direction=context.market_direction,
        evidence_quality=0.9,
        reasons=("fresh deterministic market context is available",),
        evidence=(f"event_age_ms={context.event_age_ms:.0f}",),
    )


def technical_agent(context: AgentContext) -> AgentFinding:
    structure = context.technical_structure.upper()
    if structure == "BULLISH":
        direction = Direction.LONG
    elif structure == "BEARISH":
        direction = Direction.SHORT
    elif structure == "RANGE":
        direction = Direction.NEUTRAL
    else:
        return AgentFinding(
            agent="TechnicalAgent",
            status=AgentStatus.UNKNOWN,
            reasons=("deterministic market structure is UNKNOWN",),
        )
    return AgentFinding(
        agent="TechnicalAgent",
        status=AgentStatus.SUPPORTED,
        direction=direction,
        evidence_quality=0.9,
        reasons=("direction derived from I2 deterministic market structure",),
        evidence=(f"structure={structure}",),
    )


def pattern_agent(context: AgentContext) -> AgentFinding:
    directional = {
        item
        for item in context.pattern_directions
        if item in (Direction.LONG, Direction.SHORT)
    }
    if not directional:
        return AgentFinding(
            agent="PatternAgent",
            status=AgentStatus.UNKNOWN,
            reasons=("no directional deterministic I2 pattern is available",),
        )
    if len(directional) > 1:
        return AgentFinding(
            agent="PatternAgent",
            status=AgentStatus.CONFLICT,
            reasons=("opposing LONG and SHORT deterministic patterns are present",),
            evidence=tuple(sorted(item.value for item in directional)),
        )
    direction = next(iter(directional))
    return AgentFinding(
        agent="PatternAgent",
        status=AgentStatus.SUPPORTED,
        direction=direction,
        evidence_quality=0.85,
        reasons=("direction derived from deterministic I2 pattern evidence",),
        evidence=tuple(item.value for item in context.pattern_directions),
    )


def macro_agent(context: AgentContext) -> AgentFinding:
    state = context.macro_state.upper()
    if context.event_risk or state == "POST_EVENT":
        return AgentFinding(
            agent="MacroAgent",
            status=AgentStatus.CONFLICT,
            direction=Direction.NEUTRAL,
            evidence_quality=0.8,
            reasons=("macro/event-risk context requires caution",),
            evidence=(f"macro_state={state}", f"event_risk={context.event_risk}"),
        )
    if state == "UNKNOWN":
        return AgentFinding(
            agent="MacroAgent",
            status=AgentStatus.UNKNOWN,
            reasons=("macro context is unavailable",),
        )
    if state not in {"RISK_ON", "RISK_OFF", "NEUTRAL"}:
        return AgentFinding(
            agent="MacroAgent",
            status=AgentStatus.UNKNOWN,
            reasons=(f"unsupported macro state {state}",),
        )
    return AgentFinding(
        agent="MacroAgent",
        status=AgentStatus.SUPPORTED,
        direction=Direction.NEUTRAL,
        evidence_quality=0.7,
        reasons=("macro context is available",),
        evidence=(f"macro_state={state}",),
    )


def risk_agent(context: AgentContext) -> AgentFinding:
    status = context.risk_status.upper()
    if status == "VETO":
        return AgentFinding(
            agent="RiskAgent",
            status=AgentStatus.VETO,
            direction=Direction.NEUTRAL,
            evidence_quality=1.0,
            reasons=context.risk_reasons or ("I3 deterministic risk gate vetoed the setup",),
        )
    if status == "REVIEW":
        return AgentFinding(
            agent="RiskAgent",
            status=AgentStatus.CONFLICT,
            direction=Direction.NEUTRAL,
            evidence_quality=1.0,
            reasons=context.risk_reasons or ("I3 deterministic risk gate requires review",),
        )
    if status != "ACCEPT":
        return AgentFinding(
            agent="RiskAgent",
            status=AgentStatus.UNKNOWN,
            direction=Direction.NEUTRAL,
            reasons=("I3 deterministic risk decision is unavailable",),
        )
    return AgentFinding(
        agent="RiskAgent",
        status=AgentStatus.SUPPORTED,
        direction=Direction.NEUTRAL,
        evidence_quality=1.0,
        reasons=("I3 deterministic risk gate accepted the setup",),
        evidence=context.risk_reasons,
    )


def _directional_findings(
    findings: Iterable[AgentFinding],
) -> list[AgentFinding]:
    return [
        finding
        for finding in findings
        if finding.status is AgentStatus.SUPPORTED
        and finding.direction in (Direction.LONG, Direction.SHORT)
    ]


def fusion_agent(
    context: AgentContext,
    findings: Iterable[AgentFinding],
) -> AgenticAssessment:
    collected = tuple(findings)
    unresolved: list[str] = []

    if context.rag_status is AgentStatus.CONFLICT:
        unresolved.append("RAG evidence contains an unsafe or conflicting passage")
    elif context.rag_status is AgentStatus.DATA_STALE:
        unresolved.append("RAG evidence is stale")
    elif context.rag_status is AgentStatus.UNKNOWN:
        unresolved.append("RAG evidence is unavailable or insufficient")

    if any(item.status is AgentStatus.VETO for item in collected):
        return AgenticAssessment(
            symbol=context.symbol,
            status=AgentStatus.VETO,
            direction=Direction.NEUTRAL,
            findings=collected,
            unresolved=tuple(unresolved),
        )

    if any(item.status is AgentStatus.DATA_STALE for item in collected):
        return AgenticAssessment(
            symbol=context.symbol,
            status=AgentStatus.DATA_STALE,
            direction=Direction.UNKNOWN,
            findings=collected,
            unresolved=tuple(unresolved),
        )

    if (
        any(item.status is AgentStatus.CONFLICT for item in collected)
        or context.rag_status is AgentStatus.CONFLICT
    ):
        return AgenticAssessment(
            symbol=context.symbol,
            status=AgentStatus.CONFLICT,
            direction=Direction.UNKNOWN,
            findings=collected,
            unresolved=tuple(unresolved),
        )

    directional = _directional_findings(collected)
    directions = {item.direction for item in directional}
    if len(directions) > 1:
        return AgenticAssessment(
            symbol=context.symbol,
            status=AgentStatus.CONFLICT,
            direction=Direction.UNKNOWN,
            findings=collected,
            unresolved=tuple(unresolved + ["specialized agents disagree on direction"]),
        )

    risk_supported = any(
        item.agent == "RiskAgent" and item.status is AgentStatus.SUPPORTED
        for item in collected
    )
    if not directional or not risk_supported:
        return AgenticAssessment(
            symbol=context.symbol,
            status=AgentStatus.UNKNOWN,
            direction=Direction.UNKNOWN,
            findings=collected,
            unresolved=tuple(unresolved + ["insufficient aligned directional/risk evidence"]),
        )

    direction = directional[0].direction
    unknown_agents = [
        item.agent for item in collected if item.status is AgentStatus.UNKNOWN
    ]
    unresolved.extend(f"{name} returned UNKNOWN" for name in unknown_agents)
    return AgenticAssessment(
        symbol=context.symbol,
        status=AgentStatus.SUPPORTED,
        direction=direction,
        findings=collected,
        unresolved=tuple(unresolved),
    )
