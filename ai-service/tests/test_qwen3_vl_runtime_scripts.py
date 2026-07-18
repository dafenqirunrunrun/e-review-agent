import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_qwen3_vl_direct_smoke_blocks_when_model_is_missing(tmp_path):
    env = os.environ.copy()
    env["E_REVIEW_VLM_MODEL_DIR"] = str(tmp_path / "missing-qwen3-vl")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/qwen3_vl_direct_smoke.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert completed.returncode != 0
    assert "VLM_DIRECT_INFERENCE_BLOCKED_MODEL_NOT_READY" in completed.stdout


def test_qwen3_vl_runtime_diagnostics_records_blocked_state():
    path = ROOT / "data/multimodal/audit/qwen3_vl_runtime_diagnostics.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["marker"] == "QWEN3_VL_RUNTIME_DIAGNOSTICS_BLOCKED"
    assert data["model_download"]["marker"] == "VLM_MODEL_DOWNLOAD_BLOCKED_NETWORK"
    assert data["direct_inference"]["marker"] == "VLM_DIRECT_INFERENCE_BLOCKED_MODEL_NOT_READY"
    assert data["local_vlm_smoke"]["real_vlm_inference_count"] == 0
