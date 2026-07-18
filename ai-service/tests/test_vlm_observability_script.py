import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_vlm_observability_records_tool_registry_and_blocked_runtime():
    env = os.environ.copy()
    env["E_REVIEW_VLM_MODEL_DIR"] = str(ROOT / ".runtime" / "pytest-missing-qwen3-vl")
    subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/eval_local_vlm_smoke.py")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/audit_vlm_observability.py")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert "VLM_OBSERVABILITY_BLOCKED" in completed.stdout
    assert "VLM_OBSERVABILITY_PASS" not in completed.stdout
    result = json.loads((ROOT / "data/multimodal/audit/vlm_observability_results.json").read_text(encoding="utf-8"))
    assert result["marker"] == "VLM_OBSERVABILITY_BLOCKED"
    assert all(result["tool_registry_presence"].values())
    assert "NO_REAL_IMAGE_AGENT_RUN_RECORDED" in result["blocking_reasons"]
