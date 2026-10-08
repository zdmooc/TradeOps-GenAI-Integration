"""D-099 AA1 script static safety checks: no runtime validation."""
from pathlib import Path
import shutil
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "d099_aa1_local_preflight.sh"

def test_d099_script_syntax():
    if shutil.which("bash"):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

def test_d099_script_is_read_only():
    content = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("oc apply", "oc delete", "kubectl apply", "git push",
                      "ollama pull", "ollama launch", "opencode run", "docker run",
                      "helm upgrade", "argocd app sync"):
        assert forbidden not in content, forbidden
    assert "D099_AA1_PREFLIGHT_PASS" in content
    assert "D099_AA1_LOCAL_MODEL_BASELINE_VALIDATED=NO" in content
