from __future__ import annotations

from pathlib import Path

import pytest

from app.rag_quality.models import RagQualityCase
from scripts.run_step242d_frozen_holdout import (
    HoldoutIntegrityError,
    assert_not_consumed,
    build_run_rows,
    evaluate_slice_safety,
    evaluate_thresholds,
)


class Chunk:
    chunkId = "chunk-a"
    sourceName = "测试政策"
    sourceUrl = "https://example.test/policy"
    sectionPath = ["第一章", "第一条"]
    clauseId = "1"
    contentHash = "1234567890abcdef"


def case(case_id: str, *, risks: list[str], no_answer: bool = False) -> RagQualityCase:
    return RagQualityCase(
        datasetVersion="frozen-test",
        caseId=case_id,
        split="holdout",
        reviewText="测试评论",
        queryStyle="fixture",
        riskTypes=risks,
        riskLevel="normal" if no_answer else "high",
        noAnswer=no_answer,
        sourceLanguage="not_applicable" if no_answer else "zh",
        documentFormat="not_applicable" if no_answer else "html",
        qrels=[] if no_answer else [{"chunkId": "chunk-a", "relevance": 3, "supports": risks}],
        qrelCompleteness="complete",
        annotationStatus="llm_adjudicated",
        annotationSource="test",
        candidateExposure=False,
        requiresAdjudication=False,
    )


def test_build_run_rows_abstains_only_when_upstream_risks_are_empty() -> None:
    risk = case("risk", risks=["fake_review"])
    normal = case("normal", risks=[], no_answer=True)

    rows = build_run_rows([risk, normal], [risk], [[(0.9, Chunk())]])

    assert rows[0].abstained is False
    assert rows[0].hits[0].chunkId == "chunk-a"
    assert rows[1].abstained is True
    assert rows[1].hits == []
    assert rows[1].metadata["reason"] == "EMPTY_FROZEN_UPSTREAM_RISK_HINTS"


def test_frozen_thresholds_fail_on_any_single_metric() -> None:
    thresholds = {
        "candidateEvidenceHitRateAt5": 0.95,
        "mrrAt5": 0.84,
        "citationValidCaseRate": 1.0,
        "unjudgedItemRateAt5": 0.0,
        "highRiskAutoPassCount": 0,
    }
    metrics = {
        "candidateEvidenceHitRateAt5": 1.0,
        "mrrAt5": 0.83,
        "citationValidCaseRate": 1.0,
        "unjudgedItemRateAt5": 0.0,
    }

    checks = evaluate_thresholds(metrics, thresholds)

    assert checks["candidateEvidenceHitRateAt5"] is True
    assert checks["mrrAt5"] is False
    assert checks["citationValidCaseRate"] is True
    assert checks["highRiskAutoPassCount"] is True
    assert not all(checks.values())


def test_slice_gate_does_not_hide_a_single_risk_regression() -> None:
    checks = evaluate_slice_safety(
        {
            "riskType": {
                "fake_review": {
                    "candidateEvidenceHitRateAt5": 1.0,
                    "citationValidCaseRate": 1.0,
                    "highRiskEvidenceMissCountAt5": 0,
                },
                "privacy_risk": {
                    "candidateEvidenceHitRateAt5": 0.0,
                    "citationValidCaseRate": 1.0,
                    "highRiskEvidenceMissCountAt5": 1,
                },
            }
        }
    )

    assert checks["everyRiskTypeHasEvidenceAt5"] is False
    assert checks["everyRiskTypeCitationValid"] is True
    assert checks["noRiskTypeHasHighRiskEvidenceMiss"] is False


def test_execution_seal_blocks_a_second_holdout_run(tmp_path: Path) -> None:
    paths = {
        "seal": tmp_path / "seal.json",
        "report": tmp_path / "report.json",
        "lock": tmp_path / ".lock",
    }
    assert_not_consumed(paths)
    paths["seal"].write_text("{}", encoding="utf-8")

    with pytest.raises(HoldoutIntegrityError, match="ALREADY_CONSUMED"):
        assert_not_consumed(paths)
