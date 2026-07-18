import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_qwen_realworld_external_eval_blocks_without_real_external_set():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/eval_qwen_realworld_external.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED" in completed.stdout
    result_path = ROOT / "data/rag/audit/qwen_realworld_external_eval_results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["marker"] == "REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED"
    assert result["real_external_count"] < result["required_real_external_count"]
    assert result["metrics"]["qwen3_prompt_only"]["risk_type_macro_f1"] is None
    assert result["metrics"]["qwen3_synthetic_plus_real_hybrid_rag"]["unsafe_auto_pass_rate"] is None
    assert "Synthetic RAG" in (ROOT / "docs/114_v161_qwen_realworld_external_eval_report.md").read_text(encoding="utf-8")
