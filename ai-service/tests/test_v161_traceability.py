import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v161_requirement_traceability_covers_all_original_goal_items():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/v161_requirement_traceability.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert "V161_REQUIREMENT_TRACEABILITY_COMPLETE" in completed.stdout
    result = json.loads((ROOT / "data/multimodal/audit/v161_requirement_traceability.json").read_text(encoding="utf-8"))
    rows = result["rows"]
    assert len(rows) == 10
    assert [row["id"] for row in rows] == list(range(1, 11))
    statuses = {row["id"]: row["status"] for row in rows}
    assert statuses[1] == "COMPLETE"
    assert statuses[2] == "BLOCKED"
    assert statuses[7] == "BLOCKED"
    assert statuses[9] == "BLOCKED"
    assert statuses[10] == "COMPLETE_WITH_BLOCKED_RELEASE_GATES"
