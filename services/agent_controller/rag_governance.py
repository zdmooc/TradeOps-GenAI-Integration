from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import AgentStatus


_PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "developer message",
    "reveal secrets",
    "show hidden prompt",
    "execute shell",
    "run shell",
    "bypass policy",
    "disable safety",
)


@dataclass(frozen=True, slots=True)
class RagPolicy:
    min_score: float = 0.25
    max_hits: int = 5
    allowed_suffixes: tuple[str, ...] = (".md", ".txt")
    max_text_chars: int = 6_000

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_score <= 1.0:
            raise ValueError("min_score must be within [0, 1]")
        if self.max_hits <= 0:
            raise ValueError("max_hits must be positive")
        if self.max_text_chars <= 0:
            raise ValueError("max_text_chars must be positive")


@dataclass(frozen=True, slots=True)
class RagAssessment:
    status: AgentStatus
    accepted_hits: tuple[dict[str, Any], ...]
    rejected: tuple[str, ...]

    @property
    def evidence(self) -> tuple[str, ...]:
        return tuple(
            f"{hit['source']}@{float(hit['score']):.4f}" for hit in self.accepted_hits
        )


def _contains_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _PROMPT_INJECTION_MARKERS)


def assess_rag_hits(
    hits: list[dict[str, Any]],
    policy: RagPolicy | None = None,
) -> RagAssessment:
    policy = policy or RagPolicy()
    accepted: list[dict[str, Any]] = []
    rejected: list[str] = []
    unsafe = False

    for index, hit in enumerate(hits[: policy.max_hits]):
        source = str(hit.get("source", "")).strip()
        text = str(hit.get("text", "")).strip()
        raw_score = hit.get("score", 0.0)
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            rejected.append(f"hit[{index}]: invalid score")
            continue

        if not source or not source.lower().endswith(policy.allowed_suffixes):
            rejected.append(f"hit[{index}]: unapproved source")
            continue
        if not text:
            rejected.append(f"hit[{index}]: empty text")
            continue
        if len(text) > policy.max_text_chars:
            rejected.append(f"hit[{index}]: text too large")
            continue
        if not 0.0 <= score <= 1.0 or score < policy.min_score:
            rejected.append(f"hit[{index}]: score below policy threshold")
            continue
        if _contains_prompt_injection(text):
            rejected.append(f"hit[{index}]: prompt-injection marker detected")
            unsafe = True
            continue

        accepted.append({"source": source, "text": text, "score": score})

    if unsafe:
        status = AgentStatus.CONFLICT
    elif accepted:
        status = AgentStatus.SUPPORTED
    else:
        status = AgentStatus.UNKNOWN

    return RagAssessment(
        status=status,
        accepted_hits=tuple(accepted),
        rejected=tuple(rejected),
    )
