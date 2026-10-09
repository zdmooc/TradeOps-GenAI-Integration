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
    # A last-match model does not require the blanket deny to be literally
    # last. Subsequent DENY rules cannot reopen earlier permissions.
    # Subsequent ALLOW/ASK rules, however, can reopen some category or path
    # that isn't in our small probe set, so keep global verification open.
    blanket_deny_indices = [
        i for i, r in enumerate(rules)
        if r["permission"] == "*" and r["pattern"] == "*" and r["action"] == "deny"
    ]
    last_blanket_deny_index = (
        blanket_deny_indices[-1] if blanket_deny_indices else None
    )
    following = (rules[last_blanket_deny_index + 1:]
                 if last_blanket_deny_index is not None else rules)
    relaxed_after_blanket = [
        r for r in following if r["action"] in {"allow", "ask"}
    ]
    global_deny_verified = (last_blanket_deny_index is not None
                            and not relaxed_after_blanket)
    terminal_deny_all = (last_blanket_deny_index is not None
                         and last_blanket_deny_index == len(rules) - 1)
    all_denied = all(
        choice == "deny"
        for tool_results in results.values() for choice in tool_results
    )
    success = global_deny_verified and all_denied
    # Report only permission type/action; never output path patterns,
    # user directories, tokens or private workspaces from debug config.
    known_types = frozenset({
        "*", "bash", "edit", "read", "webfetch", "external_directory",
        "glob", "grep", "task", "skill", "lsp", "question", "todowrite",
        "todoread", "doom_loop",
    })
    reopening_categories = sorted({
        r["permission"] if r["permission"] in known_types else "<other>"
        for r in relaxed_after_blanket
    })
    if success:
        status = "POLICY_RESOLVED_PASS"
        reason = "ALL_TOOLS_DENIED_AFTER_LAST_BLANKET_RULE"
    elif all_denied:
        status = "TARGETED_DENY_PASS_GLOBAL_UNVERIFIED"
        reason = "LATE_ALLOW_ASK_OR_MISSING_GLOBAL_CATCHALL"
    else:
        status = "FAIL"
        reason = "AT_LEAST_ONE_PROBED_PERMISSION_NOT_DENIED"
    return {
        "status": status,
        "reason": reason,
        "terminal_deny_all": terminal_deny_all,
        "global_deny_verified": global_deny_verified,
        "last_blanket_deny_index": last_blanket_deny_index,
        "rules_after_blanket": len(following),
        "allow_or_ask_after_blanket": len(relaxed_after_blanket),
        "reopening_categories": reopening_categories,
        "permission_tests": results,
        "runtime_denial_proven": False,
    }


def main() -> int:
    try:
        value = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        value = None
    report = inspect(value)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "POLICY_RESOLVED_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
