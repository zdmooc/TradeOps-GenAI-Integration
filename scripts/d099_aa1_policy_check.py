"""D099 AA1: verify resolved OpenCode policy from an agent debug JSON snapshot.

Never parses the whole OpenCode config, never executes tools, never invokes a model.
A policy listing is evidence of configuration only, not runtime enforcement.
"""
from __future__ import annotations

import fnmatch
import json
import sys
from typing import Any

DENY_TOOLS = ("bash", "edit", "read", "external_directory", "webfetch")
PROBE_VALUES = {
    "bash": ("*", "pwd", "powershell"),
    "edit": ("*", "docs/adr.md", ".opencode/plans/sample.md"),
    "read": ("*", "docs/adr.md"),
    "external_directory": ("*", "../outside"),
    "webfetch": ("*", "https://example.com"),
}


def decision(rules: list[dict[str, Any]], tool: str, target: str = "*") -> str:
    result = "unknown"
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        category = rule.get("permission")
        pattern = rule.get("pattern")
        action = rule.get("action")
        if not all(isinstance(v, str) for v in (category, pattern, action)):
            continue
        if category not in ("*", tool):
            continue
        # OpenCode's pattern wildcard matching is its own implementation.
        # This local check uses conservative fnmatch probes, not an exact parser.
        if fnmatch.fnmatchcase(target, pattern) or pattern == "*":
            result = action
    return result


def inspect(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not isinstance(value.get("permission"), list):
        return {"status": "FAIL", "reason": "INVALID_AGENT_DEBUG_JSON",
                "permission_tests": {}, "runtime_denial_proven": False}
    rules = value["permission"]
    if not rules or any(not isinstance(r, dict)
                        or set(("permission", "pattern", "action")) - set(r)
                        or any(not isinstance(r[k], str)
                               for k in ("permission", "pattern", "action"))
                        or r["action"] not in ("allow", "ask", "deny") for r in rules):
        return {"status": "FAIL", "reason": "INVALID_PERMISSION_RULES",
                "permission_tests": {}, "runtime_denial_proven": False}
    results = {tool: [decision(rules, tool, probe) for probe in probes]
               for tool, probes in PROBE_VALUES.items()}
    # End with a deny-all catch-all: this prevents overlooked builtin and
    # user-defined permissions from slipping through these sampled probes.
    last = rules[-1]
    terminal_deny_all = (last["permission"] == "*" and last["pattern"] == "*"
                         and last["action"] == "deny")
    all_denied = all(v == "deny" for decisions in results.values() for v in decisions)
    success = terminal_deny_all and all_denied
    return {
        "status": "POLICY_RESOLVED_PASS" if success else "FAIL",
        "reason": "EFFECTIVE_DENY_ALL_SAMPLED" if success else "NON_DENY_OR_NO_FINAL_CATCHALL",
        "terminal_deny_all": terminal_deny_all,
        "permission_tests": results,
        "runtime_denial_proven": False,
    }


def main() -> int:
    try:
        value = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        value = None
    print(json.dumps(inspect(value), sort_keys=True))
    return 0 if inspect(value)["status"] == "POLICY_RESOLVED_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
