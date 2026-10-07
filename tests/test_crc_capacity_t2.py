from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.crc.k8s_capacity_summary import cpu_to_millicores, memory_to_bytes, summarize

ROOT = Path(__file__).resolve().parents[1]
T2 = ROOT / "scripts" / "crc" / "t2-capacity-gitops-evidence.sh"


def test_capacity_quantity_parsing():
    assert int(cpu_to_millicores("500m")) == 500
    assert int(cpu_to_millicores("2")) == 2000
    assert int(memory_to_bytes("1Gi") / (1024**2)) == 1024
    assert int(memory_to_bytes("512Mi") / (1024**2)) == 512


def test_capacity_summary_distinguishes_scheduler_memory_pressure():
    pods = {
        "items": [
            {
                "metadata": {"name": "running"},
                "spec": {
                    "nodeName": "crc",
                    "containers": [
                        {"resources": {"requests": {"cpu": "500m", "memory": "1Gi"}}}
                    ],
                },
                "status": {"phase": "Running"},
            },
            {
                "metadata": {"name": "blocked"},
                "spec": {
                    "containers": [
                        {"resources": {"requests": {"cpu": "250m", "memory": "512Mi"}}}
                    ]
                },
                "status": {
                    "phase": "Pending",
                    "conditions": [
                        {
                            "type": "PodScheduled",
                            "status": "False",
                            "reason": "Unschedulable",
                            "message": "0/1 nodes are available: 1 Insufficient memory.",
                        }
                    ],
                },
            },
            {
                "metadata": {"name": "completed"},
                "spec": {
                    "nodeName": "crc",
                    "containers": [
                        {"resources": {"requests": {"cpu": "1", "memory": "2Gi"}}}
                    ],
                },
                "status": {"phase": "Succeeded"},
            },
        ]
    }
    nodes = {
        "items": [
            {
                "metadata": {"name": "crc"},
                "status": {
                    "allocatable": {"cpu": "8", "memory": "24Gi"},
                    "conditions": [{"type": "Ready", "status": "True"}],
                },
            }
        ]
    }

    result = summarize(pods, nodes)

    assert result["pods"]["active"] == 2
    assert result["pods"]["scheduled"] == 1
    assert result["pods"]["pending"] == 1
    assert result["pods"]["unscheduled"] == 1
    assert result["pods"]["unscheduled_insufficient_memory"] == 1
    assert result["requests"]["scheduled_cpu_m"] == 500
    assert result["requests"]["scheduled_memory_mib"] == 1024
    assert result["requests"]["unscheduled_cpu_m"] == 250
    assert result["requests"]["unscheduled_memory_mib"] == 512
    assert result["nodes"]["ready"] == 1
    assert result["nodes"]["allocatable_cpu_m"] == 8000
    assert result["nodes"]["allocatable_memory_mib"] == 24576


def test_t2_script_is_read_only_and_bash_syntax_valid():
    result = subprocess.run(
        ["bash", "-n", str(T2)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    script = T2.read_text(encoding="utf-8")
    assert 'grep -qx "PARKED"' in script
    assert "applications.argoproj.io" in script
    assert "clusteroperators.config.openshift.io" in script
    assert '"unscheduled_insufficient_memory"' in script
    assert "T2_SCHEDULER_CAPACITY_GATE=PASS" in script
    assert "T2_CAPACITY_GITOPS_GATE=PASS" in script
    assert " oc scale " not in script
    assert " oc delete " not in script
    assert " oc patch " not in script
