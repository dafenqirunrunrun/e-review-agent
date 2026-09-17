from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from run_v23_parent_child_calibration import aggregate, score_ids  # noqa: E402


def test_score_ids_calculates_coverage_and_rank() -> None:
    scores = score_ids(["a", "b", "c"], {"c"})
    assert scores["coverageAt5"] == 1.0
    assert scores["bestRelevantRank"] == 3.0
    assert scores["mrr"] == 1 / 3


def test_aggregate_reports_miss_and_rank_statistics() -> None:
    rows = [score_ids(["a", "b"], {"a"}), score_ids(["a", "b"], {"z"})]
    out = aggregate(rows)
    assert out["caseCount"] == 2
    assert out["missCount"] == 1
    assert out["coverageAt5"] == 0.5
