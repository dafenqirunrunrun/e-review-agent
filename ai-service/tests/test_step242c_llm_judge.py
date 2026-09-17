from __future__ import annotations

import json

import pytest

from app.rag_quality.llm_judge import (
    BlindJudgeCase,
    build_blind_prompt,
    judge_agreement,
    parse_blind_judge_output,
    protocol_hash,
)


def test_blind_prompt_does_not_expose_candidate_labels_or_qrels():
    prompt = build_blind_prompt(
        [BlindJudgeCase("case-1", "客服要求五星截图后返现。")],
        pass_name="recall_first",
    )
    assert "客服要求五星截图后返现" in prompt
    assert "proposedRiskTypes" not in prompt
    assert "qrels" not in prompt.lower()
    assert "candidate" not in prompt.lower()
    assert '"noAnswer":true' not in prompt
    assert "NEGATED_RISK" not in prompt


def test_parse_blind_judge_output_enforces_closed_schema():
    raw = json.dumps(
        {
            "cases": [
                {
                    "caseId": "case-1",
                    "riskTypes": ["rating_manipulation"],
                    "noAnswer": False,
                    "confidence": 0.91,
                    "reasonCodes": ["INCENTIVE_FOR_STARS"],
                }
            ]
        }
    )
    parsed = parse_blind_judge_output(raw, ["case-1"])
    assert parsed[0]["riskTypes"] == ["rating_manipulation"]
    with pytest.raises(ValueError, match="UNKNOWN_RISK_TYPE"):
        parse_blind_judge_output(raw.replace("rating_manipulation", "made_up_risk"), ["case-1"])


def test_parse_blind_judge_output_rejects_no_answer_contradiction():
    raw = json.dumps(
        {
            "cases": [
                {
                    "caseId": "case-1",
                    "riskTypes": ["fake_review"],
                    "noAnswer": True,
                    "confidence": 0.9,
                    "reasonCodes": [],
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="NO_ANSWER_CONTRADICTION"):
        parse_blind_judge_output(raw, ["case-1"])


def test_parse_blind_judge_output_accepts_deterministic_outer_wrapper_repair():
    raw = json.dumps(
        [
            {
                "caseId": "case-1",
                "riskTypes": ["privacy_risk"],
                "noAnswer": False,
                "confidence": 0.88,
                "reasonCodes": ["PERSONAL_INFORMATION_DISCLOSED"],
            }
        ]
    )
    parsed = parse_blind_judge_output(raw, ["case-1"])
    assert parsed[0]["riskTypes"] == ["privacy_risk"]


def test_parse_blind_judge_output_accepts_compact_case_rows():
    raw = json.dumps(
        {
            "cases": [
                ["case-1", ["rating_manipulation"], False, 93, ["INCENTIVE_FOR_STARS"]]
            ]
        }
    )
    parsed = parse_blind_judge_output(raw, ["case-1"])
    assert parsed[0]["confidence"] == 0.93


def test_parse_blind_judge_output_derives_no_answer_and_reason_code():
    raw = json.dumps(
        {"cases": [{"caseId": "case-1", "riskTypes": [], "confidence": 96}]}
    )
    parsed = parse_blind_judge_output(raw, ["case-1"])
    assert parsed[0]["noAnswer"] is True
    assert parsed[0]["reasonCodes"] == ["NO_POLICY_RISK"]
    assert parsed[0]["confidence"] == 0.96


def test_agreement_reports_exact_and_disputed_risks():
    first = {"riskTypes": ["fake_review", "rating_manipulation"], "noAnswer": False, "confidence": 0.9}
    second = {"riskTypes": ["rating_manipulation"], "noAnswer": False, "confidence": 0.8}
    result = judge_agreement(first, second)
    assert result["exact"] is False
    assert result["agreedRiskTypes"] == ["rating_manipulation"]
    assert result["disputedRiskTypes"] == ["fake_review"]
    assert result["minimumConfidence"] == 0.8


def test_protocol_hash_is_stable():
    assert protocol_hash() == protocol_hash()
    assert len(protocol_hash()) == 64
