"""AA4 actual disposable local Git operations; no live repo or auth."""
import pytest

from services.solution_architect.controlled_fixture_builder import simulate


def test_isolated_real_worktree_edited_diff_checked_and_removed():
    report = simulate()
    assert report["status"] == "AA4_DISPOSABLE_SYNTHETIC_WORKTREE_PASS"
    assert report["diff_files"] == ["docs/notice.md"]
    assert report["origin_unchanged"] is True
    assert report["diff_check"] == "PASS"
    assert len(report["source_commit"]) == 40
    assert report["remote_push"] is False
    assert report["worktree_cleaned_in_finally"] is True
    assert report["AA4_CONTROLLED_BUILD_VALIDATED"] is False


@pytest.mark.parametrize("bad", ["../secret.txt", ".git/config",
                                 "src/malware.py", "docs/notice.md/../../x"])
def test_any_external_or_untrusted_target_is_denied(bad):
    with pytest.raises(ValueError, match="AA4_SYNTHETIC_FILE_ALLOWLIST_DENIED"):
        simulate(edit_target=bad)
