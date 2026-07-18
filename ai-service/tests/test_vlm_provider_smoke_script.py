import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_vlm_provider_smoke_script_records_provider_wiring_state():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/vlm_provider_smoke.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "VLM_PROVIDER_SMOKE_" in completed.stdout
    result_path = ROOT / "data/multimodal/eval/vlm_provider_smoke_results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["marker"] in {"VLM_PROVIDER_SMOKE_BLOCKED", "VLM_PROVIDER_SMOKE_READY_FOR_REAL_IMAGE_TEST"}
    assert result["provider_marker"] in {"MULTIMODAL_VLM_EVAL_BLOCKED", "MULTIMODAL_VLM_PILOT_READY"}
    assert result["schema_valid"] is True
    assert result["status_endpoint"] == "/api/v1/vlm/status"
    assert result["smoke_endpoint"] == "/api/v1/vlm/smoke-test"
