from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_heldout_common import decision_from_quality  # noqa: E402


def sample_quality() -> dict:
    return {
        "flat": {"caseCount": 120, "coverageAt20": 0.70, "mrr": 0.20, "ndcgAt5": 0.20},
        "parentAware": {"caseCount": 120, "coverageAt20": 0.75, "mrr": 0.20, "ndcgAt5": 0.20},
        "coverageAt20Lift": 0.05,
        "parentHitRateAt10": 0.85,
        "parentHitRateAt18": 1.0,
        "parentAwareOnlyHitRate": 0.04,
        "parentAwareOnlyHitCount": 5,
        "flatOnlyHitCount": 1,
        "netRecoveredCaseCount": 4,
        "deepRank": {"deepRankRecoveryRateAt20": 0.30},
        "noAnswer": {"noAnswerCaseCount": 30, "flatFalseEvidenceRate": 0.0, "parentAwareFalseEvidenceRate": 0.0, "lowScoreBackfillCount": 0},
        "resource": {"flatRetrievalP95Ms": 10.0, "parentAwareRetrievalP95Ms": 12.0, "indexSizeRatio": 1.06},
        "safety": {
            "tenantViolations": 0,
            "expiredEvidenceAccepted": 0,
            "inactiveEvidenceAccepted": 0,
            "disabledEvidenceAccepted": 0,
            "tombstonedEvidenceAccepted": 0,
            "crossParentTenantViolation": 0,
            "contentHashMismatch": 0,
            "nonFiniteScoreCount": 0,
            "fallbackUsedCount": 0,
            "lowScoreBackfillCount": 0,
        },
    }


def test_heldout_metric_contract_uses_required_sections_without_reading_evaluation() -> None:
    quality = sample_quality()
    assert quality["flat"]["caseCount"] == 120
    assert quality["parentAware"]["caseCount"] == 120
    assert quality["noAnswer"]["noAnswerCaseCount"] == 30
    assert quality["resource"]["indexSizeRatio"] == 1.06
    assert quality["safety"]["fallbackUsedCount"] == 0
    assert quality["parentHitRateAt18"] >= quality["parentHitRateAt10"]


def test_decision_reports_all_gate_checks() -> None:
    quality = sample_quality()
    decision = decision_from_quality(quality)
    for key in (
        "safetyPass",
        "parentHitRatePass",
        "coverageOrDeepRankPass",
        "independentIncrementPass",
        "rankingQualityPass",
        "noAnswerPass",
        "resourcePass",
    ):
        assert key in decision["checks"]
    assert decision["decision"] in {
        "PARENT_AWARE_EVALUATION_PASS",
        "PARENT_AWARE_QUALITY_BLOCKED",
        "PARENT_AWARE_RESOURCE_BLOCKED",
        "PARENT_AWARE_SAFETY_BLOCKED",
    }
