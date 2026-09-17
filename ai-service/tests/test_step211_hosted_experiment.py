from types import SimpleNamespace

import pytest

from scripts.run_step211_langfuse_experiment import (
    EVALUATOR_NAMES,
    aggregate_results,
    evaluators,
    validate_hosted_dataset,
)


def _case(case_id="case-1"):
    return {
        "caseId": case_id,
        "reviewText": "五星截图返现",
        "expectedRiskTypes": ["fake_review", "rating_manipulation"],
        "expectedRoute": "governance_required",
        "expectedDecision": "suggest_action",
        "expectedEvidenceStatus": "supported",
        "expectedHumanReview": False,
    }


def _item(case, sha="ABC"):
    return SimpleNamespace(
        input={"reviewText": {"redacted": True, "hash": "safe", "length": 6}},
        expected_output={
            "riskTypes": case["expectedRiskTypes"],
            "route": case["expectedRoute"],
            "decision": case["expectedDecision"],
            "reflection": case["expectedEvidenceStatus"],
        },
        metadata={"caseId": case["caseId"], "goldSha256": sha},
    )


def test_hosted_dataset_integrity_accepts_sanitized_exact_mirror():
    case = _case()
    result = validate_hosted_dataset([_item(case)], {case["caseId"]: case}, "ABC")
    assert result == {"itemCount": 1, "duplicates": 0, "missing": 0}


def test_hosted_dataset_integrity_rejects_gold_or_expected_drift():
    case = _case()
    with pytest.raises(RuntimeError, match="GOLD_SHA_MISMATCH"):
        validate_hosted_dataset([_item(case, "OTHER")], {case["caseId"]: case}, "ABC")
    item = _item(case)
    item.expected_output["decision"] = "auto_pass"
    with pytest.raises(RuntimeError, match="EXPECTED_MISMATCH"):
        validate_hosted_dataset([item], {case["caseId"]: case}, "ABC")


def test_deterministic_evaluators_emit_complete_non_null_scores():
    case = _case()
    cases = {case["caseId"]: case}
    output = {
        "riskTypes": case["expectedRiskTypes"],
        "route": case["expectedRoute"],
        "decision": case["expectedDecision"],
        "reflection": case["expectedEvidenceStatus"],
        "citationValid": 1,
        "evidenceSupported": 1,
        "apiSuccess": 1,
    }
    values = {}
    for evaluator in evaluators(cases):
        score = evaluator(
            input={},
            output=output,
            expected_output=_item(case).expected_output,
            metadata={"caseId": case["caseId"]},
        )
        values[score.name] = score.value
    assert set(values) == set(EVALUATOR_NAMES)
    assert all(value is not None for value in values.values())
    assert values["risk_type_correct"] == 1
    assert values["high_risk_auto_pass"] == 0


def test_aggregate_reports_score_denominators_and_safety_count():
    case = _case()
    case["expectedHumanReview"] = True
    item = _item(case)
    output = {
        "riskTypes": case["expectedRiskTypes"],
        "route": case["expectedRoute"],
        "decision": "auto_pass",
        "reflection": case["expectedEvidenceStatus"],
        "citationValid": 1,
        "evidenceSupported": 1,
        "apiSuccess": 1,
    }
    scores = [
        evaluator(input={}, output=output, expected_output=item.expected_output, metadata=item.metadata)
        for evaluator in evaluators({case["caseId"]: case})
    ]
    result = SimpleNamespace(item_results=[SimpleNamespace(item=item, output=output, evaluations=scores, trace_id="trace-1")])
    aggregate = aggregate_results(result, {case["caseId"]: case}, 1)
    assert aggregate["integrity"]["scoreDenominators"] == {name: 1 for name in EVALUATOR_NAMES}
    assert aggregate["metrics"]["highRiskAutoPassCount"] == 1
