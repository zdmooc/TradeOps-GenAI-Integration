from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Mapping


_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="mcp-governed")

_SECRET_KEY_PATTERN = re.compile(
    r"(authorization|token|secret|password|api[_-]?key|credential)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Principal:
    name: str
    scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    required_scopes: frozenset[str]
    human_approval_required: bool = False
    max_calls_per_minute: int = 60
    timeout_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_calls_per_minute <= 0:
            raise ValueError("max_calls_per_minute must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    allowed: bool
    code: str
    reason: str
    sanitized_arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GovernedExecution:
    allowed: bool
    code: str
    reason: str
    result: Any
    sanitized_arguments: dict[str, Any]
    duration_ms: float


DEFAULT_TOOL_POLICIES: dict[str, ToolPolicy] = {
    "market.get_last_price": ToolPolicy(frozenset({"market.read"})),
    "risk.check_trade": ToolPolicy(frozenset({"risk.evaluate"})),
    "db.get_workflow": ToolPolicy(frozenset({"workflow.read"})),
    "db.list_audit": ToolPolicy(frozenset({"audit.read"}), max_calls_per_minute=20),
    "oms.place_order": ToolPolicy(
        frozenset({"paper.execute"}),
        human_approval_required=True,
        max_calls_per_minute=10,
        timeout_seconds=3.0,
    ),
}


def redact_sensitive(value: Any, key: str = "") -> Any:
    if key and _SECRET_KEY_PATTERN.search(key):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {
            str(item_key): redact_sensitive(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    return value


class StaticTokenAuthenticator:
    """Map bearer tokens to server-side principals and scopes."""

    def __init__(self, token_map: Mapping[str, Principal]):
        self._token_map = {
            token: principal for token, principal in token_map.items() if token
        }

    def authenticate(self, bearer_token: str | None) -> Principal | None:
        if not bearer_token:
            return None
        return self._token_map.get(bearer_token)


class SlidingWindowRateLimiter:
    def __init__(self, now_fn: Callable[[], float] | None = None):
        self._now = now_fn or time.monotonic
        self._calls: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, principal: str, tool: str, limit: int) -> bool:
        now = self._now()
        cutoff = now - 60.0
        key = (principal, tool)
        with self._lock:
            queue = self._calls[key]
            while queue and queue[0] <= cutoff:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(now)
        return True


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def validate_tool_arguments(
    arguments: Mapping[str, Any],
    parameters: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, str]:
    unknown = sorted(set(arguments) - set(parameters))
    if unknown:
        return False, f"unknown arguments: {', '.join(unknown)}"

    for name, spec in parameters.items():
        required = bool(spec.get("required", False))
        if required and name not in arguments:
            return False, f"missing required argument: {name}"
        if name not in arguments:
            continue
        value = arguments[name]
        expected = str(spec.get("type", ""))
        if expected and not _matches_type(value, expected):
            return False, f"invalid type for {name}: expected {expected}"
        enum = spec.get("enum")
        if enum is not None and value not in enum:
            return False, f"invalid value for {name}: expected one of {enum}"
        if name == "qty" and isinstance(value, (int, float)) and value <= 0:
            return False, "qty must be positive"
        if name == "limit" and isinstance(value, int) and not 1 <= value <= 500:
            return False, "limit must be within [1, 500]"
    return True, ""


class ToolGovernor:
    def __init__(
        self,
        policies: Mapping[str, ToolPolicy] | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ):
        self._policies = dict(policies or DEFAULT_TOOL_POLICIES)
        self._rate_limiter = rate_limiter or SlidingWindowRateLimiter()

    def authorize(
        self,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        principal: Principal | None,
        tool_registry: Mapping[str, Mapping[str, Any]],
        human_approved: bool,
    ) -> GovernanceDecision:
        sanitized = dict(redact_sensitive(dict(arguments)))

        if principal is None:
            return GovernanceDecision(
                False, "UNAUTHENTICATED", "valid bearer token required", sanitized
            )
        if tool_name not in tool_registry or tool_name not in self._policies:
            return GovernanceDecision(
                False, "TOOL_NOT_ALLOWED", "tool is not in the governed allowlist", sanitized
            )

        policy = self._policies[tool_name]
        missing_scopes = sorted(policy.required_scopes - principal.scopes)
        if missing_scopes:
            return GovernanceDecision(
                False,
                "FORBIDDEN",
                f"missing scopes: {', '.join(missing_scopes)}",
                sanitized,
            )

        valid, error = validate_tool_arguments(
            arguments,
            tool_registry[tool_name].get("parameters", {}),
        )
        if not valid:
            return GovernanceDecision(False, "INVALID_ARGUMENTS", error, sanitized)

        if policy.human_approval_required and not human_approved:
            return GovernanceDecision(
                False,
                "HUMAN_APPROVAL_REQUIRED",
                "tool requires explicit human approval",
                sanitized,
            )

        if not self._rate_limiter.allow(
            principal.name,
            tool_name,
            policy.max_calls_per_minute,
        ):
            return GovernanceDecision(
                False,
                "RATE_LIMITED",
                "tool rate limit exceeded",
                sanitized,
            )

        return GovernanceDecision(True, "ALLOWED", "policy checks passed", sanitized)

    def execute(
        self,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        principal: Principal | None,
        tool_registry: Mapping[str, Mapping[str, Any]],
        human_approved: bool,
        executor: Callable[[str, dict[str, Any]], Any],
    ) -> GovernedExecution:
        decision = self.authorize(
            tool_name=tool_name,
            arguments=arguments,
            principal=principal,
            tool_registry=tool_registry,
            human_approved=human_approved,
        )
        if not decision.allowed:
            return GovernedExecution(
                allowed=False,
                code=decision.code,
                reason=decision.reason,
                result=None,
                sanitized_arguments=decision.sanitized_arguments,
                duration_ms=0.0,
            )

        policy = self._policies[tool_name]
        started = time.monotonic()
        future = _EXECUTOR.submit(executor, tool_name, dict(arguments))
        try:
            result = future.result(timeout=policy.timeout_seconds)
        except FutureTimeoutError:
            future.cancel()
            return GovernedExecution(
                allowed=False,
                code="TIMEOUT",
                reason=f"tool exceeded {policy.timeout_seconds:.3f}s timeout",
                result=None,
                sanitized_arguments=decision.sanitized_arguments,
                duration_ms=(time.monotonic() - started) * 1000.0,
            )

        return GovernedExecution(
            allowed=True,
            code="OK",
            reason="tool completed",
            result=result,
            sanitized_arguments=decision.sanitized_arguments,
            duration_ms=(time.monotonic() - started) * 1000.0,
        )
