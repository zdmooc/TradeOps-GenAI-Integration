"""Static contract tests for the read-only TradeOps CRC demo hub."""

from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
SCRIPTS = (DEMO / "scripts" / "00-preflight.sh", DEMO / "scripts" / "01-capture-readonly.sh")


def test_demo_documentation_references_resolve():
    docs = list(DEMO.rglob("*.md"))
    assert len(docs) >= 10
    for source in docs:
        text = source.read_text(encoding="utf-8")
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
            href = match.group(1).split("#", 1)[0]
            if not href or "://" in href or href.startswith(("mailto:", "#")):
                continue
            dest = (source.parent / href).resolve()
            assert dest.is_relative_to(ROOT), (source, href)
            assert dest.exists(), (source, href)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
@pytest.mark.parametrize("script", SCRIPTS)
def test_demo_shell_script_syntax(script):
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("script", SCRIPTS)
def test_demo_scripts_do_not_mutate_cluster(script):
    content = script.read_text(encoding="utf-8")
    assert not re.search(r"(?m)^\s*(?:oc|kubectl)\s+(?:apply|delete|patch|scale|edit|create|replace|label|annotate)\b", content)
    assert not re.search(r"(?m)^\s*(?:helm\s+(?:upgrade|install|uninstall)|crc\s+(?:start|stop|delete))\b", content)
    assert "oc whoami -t" not in content
    assert "get secret -o yaml" not in content
