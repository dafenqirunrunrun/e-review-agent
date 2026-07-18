import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v161_final_status_summary_reports_42_items_without_release_pass():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/v161_final_status_summary.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0
    assert "V161_FINAL_STATUS_SUMMARY_COMPLETE" in completed.stdout

    result = json.loads((ROOT / "data/multimodal/audit/v161_final_status_summary.json").read_text(encoding="utf-8"))
    assert result["marker"] == "V161_FINAL_STATUS_SUMMARY_COMPLETE"
    assert len(result["items"]) == 42
    assert result["release_allowed"] is False

    values = {item["name"]: item["value"] for item in result["items"]}
    assert values["tag"] == "none"
    assert values["working_tree_clean_at_generation"].startswith(("yes", "no;"))
    assert values["recommend_enter_qwen3_ms_swift_qlora_sft"].startswith("no;")
    assert values["real_external_no_oracle_hit3_hit5"].startswith("BLOCKED:")
