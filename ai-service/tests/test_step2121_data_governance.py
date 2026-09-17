from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_step2121_data_governance.py"
SPEC = importlib.util.spec_from_file_location("step2121_data_governance", SCRIPT)
assert SPEC and SPEC.loader
governance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(governance)


def staging_row(text: str, *, outcome: str = "accepted_ai_label", eligible: bool = True) -> dict:
    return {
        "sanitizedText": text,
        "currentRiskType": "fake_review",
        "sourceType": "risk_task:test",
        "sourcePeriod": "2026-09",
        "reviewOutcome": outcome,
        "provenanceTier": "A",
        "humanReviewed": True,
        "eligibleAsGold": eligible,
    }


def test_human_set_excludes_frozen_duplicates_and_conflicting_outcomes():
    frozen = [{"reviewText": "冻结样本"}]
    staging = [
        staging_row("可用人工样本"),
        staging_row("冻结样本"),
        staging_row("冲突样本"),
        staging_row("冲突样本", outcome="human_override_needs_gold_label", eligible=False),
    ]

    rows, excluded = governance.build_human_cases(staging, frozen)

    assert [row["sanitizedText"] for row in rows] == ["可用人工样本"]
    assert excluded["exact"] == 1
    assert excluded["conflictingHumanOutcome"] == 1
    assert all(row["humanReviewed"] is True for row in rows)


def test_source_aware_split_has_no_template_or_text_leakage():
    rows = []
    for index, text in enumerate(("五星返现十元", "五星返现二十元", "商家组织刷单", "没有购买却要求好评")):
        rows.append({
            "caseId": f"human-{index}",
            "sanitizedText": text,
            "sourceType": "risk_task:test",
            "sourcePeriod": "2026-09",
            "goldRiskTypes": ["fake_review"],
            "explicitOrImplicit": "explicit",
        })

    split, audit = governance.source_aware_split(rows)

    assert split["fitCount"] + split["validationCount"] == len(rows)
    assert audit == {
        "templateFamilyLeakageCount": 0,
        "normalizedTextLeakageCount": 0,
        "passed": True,
    }


def test_override_is_queued_without_reviewer_identity_even_when_text_was_previously_accepted():
    staging = [
        staging_row("同一评论先接受"),
        staging_row("同一评论先接受", outcome="human_override_needs_gold_label", eligible=False),
    ]
    human_rows, _ = governance.build_human_cases(staging, [])

    queue = governance.build_annotation_queue(staging, human_rows, [], target=10)

    assert human_rows == []
    assert len(queue) == 1
    assert queue[0]["queueReason"] == "HUMAN_OVERRIDE_NEEDS_GOLD_LABEL"
    serialized = json.dumps(queue[0], ensure_ascii=False).lower()
    assert "reviewer" not in serialized
    assert "operator" not in serialized


def test_failed_calibrator_is_retained_but_not_approved(tmp_path: Path):
    path = tmp_path / "calibrator.json"
    original = {"method": "isotonic", "thresholds": [0.8], "values": [1.0]}
    path.write_text(json.dumps(original), encoding="utf-8")

    governance.mark_not_approved(path)
    result = json.loads(path.read_text(encoding="utf-8"))

    assert result["thresholds"] == original["thresholds"]
    assert result["values"] == original["values"]
    assert result["approvalStatus"] == "NOT_APPROVED_FOR_ROUTING"


def test_historical_frozen_count_is_not_replaced_by_new_checkpoint_reconstruction(tmp_path: Path):
    report = tmp_path / "frozen.json"
    report.write_text(json.dumps({
        "governance": {"riskCalibrationHoldout": {
            "highConfidenceErrorCount": 26,
            "highSeverityUndercallCount": 4,
        }}
    }), encoding="utf-8")

    result = governance.frozen_error_taxonomy([], tmp_path / "checkpoints", report)

    assert result["highConfidenceErrorCount"] == 26
    assert result["highSeverityUndercallCount"] == 4
    assert result["highConfidenceCountSource"] == "frozen_step21.2_holdout_artifact"
    assert result["classificationStatus"] == "BLOCKED_HISTORICAL_PER_CASE_SNAPSHOT_UNAVAILABLE"
