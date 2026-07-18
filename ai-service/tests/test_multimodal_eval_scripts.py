import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_vlm_visual_evidence_eval_reports_required_metrics_as_blocked(tmp_path):
    env = os.environ.copy()
    env["E_REVIEW_VLM_MODEL_DIR"] = str(tmp_path / "missing-qwen3-vl")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/eval_vlm_visual_evidence.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "MULTIMODAL_VLM_EVAL_BLOCKED" in completed.stdout
    result = json.loads((ROOT / "data/multimodal/eval/vlm_visual_eval_results.json").read_text(encoding="utf-8"))
    assert result["marker"] == "MULTIMODAL_VLM_EVAL_BLOCKED"
    assert result["external_multimodal_count"] < result["required_external_multimodal_count"]
    assert result["model_available"] is False
    assert result["metrics"]["visual_schema_valid_rate"] is None
    assert result["metrics"]["visual_unsupported_claim_rate"] is None
    assert "VLM Visual Evidence" in (ROOT / "docs/128_v161_vlm_visual_evidence_eval_report.md").read_text(encoding="utf-8")


def test_multimodal_ablation_eval_reports_all_four_modes_as_blocked():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/eval_multimodal_ablation.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "MULTIMODAL_ABLATION_EVAL_BLOCKED" in completed.stdout
    result = json.loads((ROOT / "data/multimodal/eval/multimodal_ablation_results.json").read_text(encoding="utf-8"))
    assert result["marker"] == "MULTIMODAL_ABLATION_EVAL_BLOCKED"
    assert result["evaluated_modes"] == ["text_only", "image_only", "text_image", "text_image_hybrid_rag"]
    assert result["metrics"]["text_only"]["risk_type_macro_f1"] is None
    assert result["metrics"]["text_image_hybrid_rag"]["visual_unsupported_claim_rate"] is None
    assert "Multimodal Ablation" in (ROOT / "docs/113_v161_multimodal_ablation_eval_report.md").read_text(encoding="utf-8")
