from __future__ import annotations

from scripts.run_step233e_business_gate import (
    STRICT_WARM_P95_SLO_MS,
    business_checks,
    evidence_confidence,
    evaluate_normal_bypass,
    governance_decision,
)


def _metrics(**overrides):
    values = {
        "riskEvidenceHitAt3": 0.90,
        "highRiskEvidenceHitAt3": 0.90,
        "allRiskCoverageAt3": 0.80,
        "evidenceSupportedRate": 0.80,
        "citationValidity": 1.0,
        "humanReviewRecall": 1.0,
        "highRiskHumanReviewRate": 1.0,
        "highRiskAutoPassCount": 0,
    }
    values.update(overrides)
    return values


def test_high_risk_is_human_review_even_when_evidence_is_supported():
    assert governance_decision("high", "supported") == "human_review"
    assert governance_decision("medium", "supported") == "suggest_action"
    assert governance_decision("medium", "mismatch") == "human_review"


def test_evidence_confidence_is_not_presented_as_model_probability():
    assert evidence_confidence("supported", True) == 0.90
    assert evidence_confidence("mismatch", True) == 0.55
    assert evidence_confidence("insufficient", False) == 0.25


def test_normal_review_bypasses_retrieval_and_reranker():
    result = evaluate_normal_bypass([{"caseId": "normal-1"}, {"caseId": "normal-2"}])

    assert result["decision"] == "auto_pass"
    assert result["retrievalInvocationCount"] == 0
    assert result["rerankerInvocationCount"] == 0
    assert result["policyEvidenceRendered"] is False


def test_business_gate_ignores_primary_policy_order_but_enforces_safety_and_slo():
    baseline = _metrics()
    candidate = _metrics(riskEvidenceHitAt3=0.92, allRiskCoverageAt3=0.82)
    normal = evaluate_normal_bypass([{"caseId": "normal"}])

    passed = business_checks(baseline, candidate, normal, {"p95Ms": STRICT_WARM_P95_SLO_MS})
    slow = business_checks(baseline, candidate, normal, {"p95Ms": STRICT_WARM_P95_SLO_MS + 1})

    assert all(passed.values())
    assert slow["warmStrictP95WithinExistingSlo"] is False
    assert "primaryPolicyAccuracyAt1" not in passed


def test_business_gate_rejects_high_risk_auto_pass_and_coverage_regression():
    baseline = _metrics()
    candidate = _metrics(highRiskAutoPassCount=1, allRiskCoverageAt3=0.70)

    checks = business_checks(
        baseline,
        candidate,
        evaluate_normal_bypass([]),
        {"p95Ms": 1000.0},
    )

    assert checks["highRiskAutoPassZero"] is False
    assert checks["allRiskCoverageAt3NoRegression"] is False
