"""D099 AA4: actual but disposable synthetic Git-worktree exercise.

The program creates its OWN blank repository inside TemporaryDirectory.
It never edits a checked-out project, accepts a repo path, pushes, merges,
uses the network, obtains credentials or touches OpenShift. This is NOT the
independently approved AA4 builder.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

SYNTHETIC_FILE = "docs/notice.md"
SYNTHETIC_INITIAL = "Synthetic notification design: no retry budget.\n"
SYNTHETIC_MODIFIED = "Synthetic notification design: bounded retry budget (proposal).\n"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], text=True,
        capture_output=True, check=True, timeout=15,
        env=None,  # uses host Git only; no remote commands or URL.
    )
    return result.stdout.strip()


def simulate(*, edit_target: str = SYNTHETIC_FILE) -> dict[str, object]:
    """Return sanitized, verifiable facts; never claim an external approval."""
    if edit_target != SYNTHETIC_FILE:
        raise ValueError("AA4_SYNTHETIC_FILE_ALLOWLIST_DENIED")
    with tempfile.TemporaryDirectory(prefix="d099-aa4-fixture-") as temp:
        base = Path(temp)
        origin, worktree = base / "origin", base / "isolated-worktree"
        origin.mkdir()
        _git(origin, "init", "-q")
        _git(origin, "config", "user.name", "D099 Synthetic CI")
        _git(origin, "config", "user.email", "d099-fixture@invalid.example")
        target = origin / SYNTHETIC_FILE
        target.parent.mkdir()
        target.write_text(SYNTHETIC_INITIAL, encoding="utf-8")
        _git(origin, "add", "--", SYNTHETIC_FILE)
        _git(origin, "commit", "-qm", "synthetic: baseline")
        pinned = _git(origin, "rev-parse", "HEAD")
        if len(pinned) != 40:
            raise RuntimeError("AA4_SOURCE_NOT_PINNED")
        try:
            _git(origin, "worktree", "add", "-qb", "d099-aa4-synthetic",
                 str(worktree), pinned)
            assert _git(worktree, "rev-parse", "HEAD") == pinned
            # Intentionally deterministic fixture content, NOT model diff.
            (worktree / SYNTHETIC_FILE).write_text(
                SYNTHETIC_MODIFIED, encoding="utf-8")
            _git(worktree, "diff", "--check")
            files = _git(worktree, "diff", "--name-only").splitlines()
            if files != [SYNTHETIC_FILE]:
                raise RuntimeError("AA4_DIFF_SCOPE_VIOLATION")
            digest = hashlib.sha256(
                (worktree / SYNTHETIC_FILE).read_bytes()).hexdigest()
            if (origin / SYNTHETIC_FILE).read_text(encoding="utf-8") != SYNTHETIC_INITIAL:
                raise RuntimeError("AA4_ORIGIN_MUTATED")
            return {
                "status": "AA4_DISPOSABLE_SYNTHETIC_WORKTREE_PASS",
                "diff_files": files,
                "source_commit": pinned,
                "candidate_sha256": digest,
                "diff_check": "PASS",
                "origin_unchanged": True,
                "remote_push": False,
                "worktree_cleaned_in_finally": True,
                "actual_customer_build": False,
                "external_human_approval": "NOT_PRESENT",
                "AA4_CONTROLLED_BUILD_VALIDATED": False,
            }
        finally:
            if worktree.exists():
                _git(origin, "worktree", "remove", "--force", str(worktree))
            # Entire disposable repository/branch is deleted by temp context.


if __name__ == "__main__":
    import json
    print(json.dumps(simulate(), indent=2))
