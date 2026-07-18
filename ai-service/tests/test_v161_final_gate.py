import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v161_final_gate_blocks_release_without_real_external_and_vlm():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/v161_final_gate.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "V161_FINAL_GATE_BLOCKED" in completed.stdout
    result_path = ROOT / "data/multimodal/audit/v161_final_gate_results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["marker"] == "V161_FINAL_GATE_BLOCKED"
    assert result["release_allowed"] is False
    assert result["recommended_tag"] is None
    blocker_text = "\n".join(result["release_blockers"])
    assert "REALWORLD_EXTERNAL_EVAL_PASS" in blocker_text
    assert "REALWORLD_QWEN_EXTERNAL_EVAL_PASS" in blocker_text
    assert "VLM_PROVIDER_SMOKE_PASS" in blocker_text
    assert "MULTIMODAL_VLM_EVAL_PASS" in blocker_text
    assert "MULTIMODAL_ABLATION_EVAL_PASS" in blocker_text
    assert "SFT_DATA_READY" in blocker_text
    assert result["metrics"]["real_external_count"] == 0
    assert result["metrics"]["qwen_real_external_count"] == 0
    assert result["metrics"]["vlm_provider_model_available"] in {True, False}
    assert result["metrics"]["multimodal_external_count"] == 0
