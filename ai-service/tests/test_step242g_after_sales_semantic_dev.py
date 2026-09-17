from scripts.run_step242g_after_sales_semantic_dev import DEV_GATES


def test_semantic_dev_gate_prioritizes_sufficient_evidence_and_integrity() -> None:
    assert DEV_GATES["candidateEvidenceHitRateAt5"] == 0.95
    assert DEV_GATES["riskCoverageAt3"] == 0.95
    assert DEV_GATES["directPreferredHitRateAt3"] == 0.85
    assert DEV_GATES["citationValidCaseRate"] == 1.0
    assert DEV_GATES["noAnswerAbstentionAccuracy"] == 1.0
    assert DEV_GATES["unjudgedItemRateAt5"] == 0.0
