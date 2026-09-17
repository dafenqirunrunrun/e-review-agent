from __future__ import annotations

from pathlib import Path

from app.policy_rag.index_store import load_policy_chunks
from app.rag_quality.models import RetrievalHit, RetrievalRunCase
from scripts.build_step242f_after_sales_delta import CHUNKS, build_cases, validate_cases
from scripts.freeze_step242f_after_sales_delta import freeze_thresholds
from scripts.run_step242f_after_sales_delta import direct_preferred_metrics, evidence_query


def test_after_sales_delta_has_full_qrels_for_current_corpus() -> None:
    chunks = load_policy_chunks(CHUNKS)
    cases = build_cases(chunks)
    result = validate_cases(cases, chunks)

    assert result["caseCount"] == 24
    assert result["devCount"] == 16
    assert result["holdoutCount"] == 8
    assert all(len(case.qrels) == len(chunks) == 123 for case in cases)
    assert all(case.qrelCompleteness == "complete" for case in cases)
    assert all(not case.candidateExposure for case in cases if case.split == "holdout")


def test_after_sales_delta_normal_cases_are_abstain_only() -> None:
    cases = build_cases(load_policy_chunks(CHUNKS))
    normal = [case for case in cases if case.noAnswer]

    assert len(normal) == 3
    assert all(case.riskTypes == [] for case in normal)
    assert all(not any(qrel.relevance >= 2 for qrel in case.qrels) for case in normal)


def test_direct_preferred_metric_requires_direct_clause_not_any_support() -> None:
    case = next(case for case in build_cases(load_policy_chunks(CHUNKS)) if case.caseId == "asdv1-001")
    direct = next(qrel.chunkId for qrel in case.qrels if qrel.relevance == 3)
    support = next(qrel.chunkId for qrel in case.qrels if qrel.relevance == 2)
    rows = [
        RetrievalRunCase(
            caseId=case.caseId,
            hits=[
                RetrievalHit(chunkId=support, score=0.9),
                RetrievalHit(chunkId=direct, score=0.8),
            ],
        )
    ]

    result = direct_preferred_metrics([case], rows)

    assert result["directPreferredHitRateAt1"] == 0.0
    assert result["directPreferredHitRateAt3"] == 1.0


def test_freeze_thresholds_keeps_integrity_exact_and_quality_bounded() -> None:
    thresholds = freeze_thresholds(
        {
            "evaluation": {
                "metrics": {
                    "candidateEvidenceHitRateAt5": 1.0,
                    "mrrAt5": 0.84,
                    "pooledNdcgAt5": 0.77,
                    "riskCoverageAt3": 0.91,
                }
            },
            "directPreferred": {"directPreferredHitRateAt3": 0.88},
        }
    )

    assert thresholds["candidateEvidenceHitRateAt5"] == 0.9
    assert thresholds["mrrAt5"] == 0.74
    assert thresholds["citationValidCaseRate"] == 1.0
    assert thresholds["unjudgedItemRateAt5"] == 0.0


def test_delta_query_matches_strict_workflow_shape() -> None:
    case = next(case for case in build_cases(load_policy_chunks(CHUNKS)) if case.caseId == "asdv1-001")

    query = evidence_query(case)

    assert case.reviewText in query
    assert "after_sales_risk" in query
    assert "after-sales" in query
