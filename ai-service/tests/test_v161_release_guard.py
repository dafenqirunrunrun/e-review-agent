import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v161_release_guard_blocks_tag_when_final_gate_blocked():
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "ai-service/scripts/v161_release_guard.py"),
            "--tag",
            "v1.6.1-realworld-multimodal-evaluation",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "V161_RELEASE_GUARD_BLOCKED" in completed.stdout
    result_path = ROOT / "data/multimodal/audit/v161_release_guard_results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["marker"] == "V161_RELEASE_GUARD_BLOCKED"
    assert result["tag_command_allowed"] is False
    assert result["recommended_command"] is None
    assert result["final_gate_marker"] == "V161_FINAL_GATE_BLOCKED"
    assert result["final_gate_release_allowed"] is False
    assert result["requested_tag"] == "v1.6.1-realworld-multimodal-evaluation"
    assert any("REALWORLD_EXTERNAL_EVAL_PASS" in item for item in result["release_blockers"])
