from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def test_parent_aware_route_closure_state_if_present() -> None:
    path = OUT / "v23-parent-aware-route-closure.json"
    if not path.exists():
        return
    p = json.loads(path.read_text(encoding="utf-8"))
    assert p["evaluationConsumptionState"] == "CONSUMED_BLOCKED"
    assert p["evaluationRerunAllowed"] is False
    assert p["calibrationRetuningAllowed"] is False
    assert p["challengeAccessed"] is False
    assert p["runtimePromotionAllowed"] is False


def test_bad_case_analysis_uses_safe_hashes_only_if_present() -> None:
    path = OUT / "v23-parent-aware-heldout-bad-case-analysis.json"
    if not path.exists():
        return
    p = json.loads(path.read_text(encoding="utf-8"))
    assert p["retrieverRerun"] is False
    assert p["configurationChanged"] is False
    assert p["fullQueriesStored"] is False
    assert p["fullChunksStored"] is False
    assert p["classificationCounts"]["FLAT_ONLY_HIT"] == 5
    assert p["classificationCounts"]["PARENT_AWARE_ONLY_HIT"] == 3
