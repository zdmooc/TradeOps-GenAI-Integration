from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"

EXPECTED = {
    "Home.md",
    "_Sidebar.md",
    "README.md",
    "01-Vision-et-Principes.md",
    "02-C4-et-Architecture-Logique.md",
    "03-Architecture-Applicative-et-Services.md",
    "04-Agentic-AI-RAG-MCP.md",
    "05-Risk-Fusion-HITL.md",
    "06-EDA-Data-ML-Replay.md",
    "07-Securite-Zero-Trust.md",
    "08-OpenShift-CRC-GitOps-RHOAI.md",
    "09-Observability-Resilience-SLO.md",
    "10-FinOps-GreenOps.md",
    "11-Web-Cockpit.md",
    "12-Azure-ARO-Target.md",
    "13-ADR-Patterns-AntiPatterns.md",
    "14-Demo-Runbook-Evidence.md",
    "15-Glossaire-Concepts.md",
}

LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


def validate() -> tuple[int, int]:
    if not WIKI.is_dir():
        raise SystemExit("WIKI_VALIDATION_FAIL: wiki/ directory missing")

    present = {p.name for p in WIKI.glob("*.md")}
    missing = sorted(EXPECTED - present)
    if missing:
        raise SystemExit(f"WIKI_VALIDATION_FAIL: missing pages: {', '.join(missing)}")

    checked_links = 0
    errors: list[str] = []

    for page in sorted(WIKI.glob("*.md")):
        text = page.read_text(encoding="utf-8")
        if not text.lstrip().startswith("#"):
            errors.append(f"{page.relative_to(ROOT)}: missing Markdown heading")

        for raw_target in LINK_RE.findall(text):
            target = raw_target.strip().split(" ", 1)[0].strip("<>\"")
            if not target or target.startswith(SKIP_PREFIXES):
                continue

            target = unquote(target.split("#", 1)[0])
            if not target:
                continue

            resolved = (page.parent / target).resolve()
            checked_links += 1
            if not resolved.exists():
                errors.append(
                    f"{page.relative_to(ROOT)}: broken link {raw_target!r} -> "
                    f"{resolved.relative_to(ROOT) if ROOT in resolved.parents else resolved}"
                )

    if errors:
        raise SystemExit("WIKI_VALIDATION_FAIL:\n- " + "\n- ".join(errors))

    return len(present), checked_links


if __name__ == "__main__":
    pages, links = validate()
    print(f"WIKI_VALIDATION_PASS pages={pages} links={links}")
