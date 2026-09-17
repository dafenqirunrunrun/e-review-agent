from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from app.rag_quality.contract import METRIC_CONTRACT_VERSION
from app.rag_quality.models import RagQualityCase, RetrievalHit, RetrievalRunCase


def evaluate_retrieval_run(
    cases: Iterable[RagQualityCase | dict[str, Any]],
    run_rows: Iterable[RetrievalRunCase | dict[str, Any]],
    *,
    run_name: str,
) -> dict[str, Any]:
    """Evaluate one ranked run without hiding partial qrels or draft labels."""

    normalized_cases = [item if isinstance(item, RagQualityCase) else RagQualityCase.model_validate(item) for item in cases]
    normalized_runs = [
        item if isinstance(item, RetrievalRunCase) else RetrievalRunCase.model_validate(item)
        for item in run_rows
    ]
    case_ids = [item.caseId for item in normalized_cases]
    run_by_case = {item.caseId: item for item in normalized_runs}
    if len(run_by_case) != len(normalized_runs):
        raise ValueError("RAG_QUALITY_RUN_CASE_DUPLICATE")
    missing = sorted(set(case_ids) - set(run_by_case))
    extra = sorted(set(run_by_case) - set(case_ids))
    if missing or extra:
        raise ValueError(f"RAG_QUALITY_RUN_CASE_MISMATCH missing={missing} extra={extra}")

    per_case = [_evaluate_case(case, run_by_case[case.caseId]) for case in normalized_cases]
    aggregate = _aggregate(per_case)
    slices = _build_slices(per_case)
    public_case_results = [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in per_case
    ]
    all_verified = all(
        case.annotationStatus in {"human_verified", "llm_adjudicated"}
        and not case.requiresAdjudication
        and case.qrelCompleteness == "complete"
        for case in normalized_cases
    )
    all_human_verified = all(case.annotationStatus == "human_verified" for case in normalized_cases)
    verification_mode = "human" if all_human_verified else ("llm_single_judge" if all_verified else "pending")
    hard_checks = {
        "citationValidityComplete": aggregate["citationValidCaseRate"] == 1.0,
        "highRiskEvidenceHitComplete": aggregate["highRiskEvidenceHitRateAt5"] == 1.0,
        "noAnswerAbstentionComplete": aggregate["noAnswerAbstentionAccuracy"] == 1.0,
    }
    return {
        "schemaVersion": "rag-quality-retrieval-result-v1",
        "metricContractVersion": METRIC_CONTRACT_VERSION,
        "runName": run_name,
        "evaluationStatus": (
            "PROMOTION_ELIGIBLE"
            if all_human_verified
            else ("PROMOTION_ELIGIBLE_WITH_SINGLE_JUDGE_LIMITATION" if all_verified else "DIAGNOSTIC_ONLY")
        ),
        "promotionGate": "PASS" if all_verified and all(hard_checks.values()) else "HOLD",
        "annotationIntegrity": {
            "allCasesReleaseVerified": all_verified,
            "allCasesHumanVerified": all_human_verified,
            "verificationMode": verification_mode,
            "pendingCaseCount": sum(
                case.annotationStatus not in {"human_verified", "llm_adjudicated"}
                for case in normalized_cases
            ),
            "partialQrelCaseCount": sum(case.qrelCompleteness != "complete" for case in normalized_cases),
            "candidateExposedCaseCount": sum(case.candidateExposure for case in normalized_cases),
        },
        "hardSafetyChecks": hard_checks,
        "metrics": aggregate,
        "slices": slices,
        "caseResults": public_case_results,
    }


def _evaluate_case(case: RagQualityCase, run: RetrievalRunCase) -> dict[str, Any]:
    top10 = run.hits[:10]
    top5 = top10[:5]
    qrels = {item.chunkId: item for item in case.qrels}
    relevant_ids = {item.chunkId for item in case.qrels if item.relevance >= 2}
    top_ids = [item.chunkId for item in top5]
    first_relevant_rank = next(
        (rank for rank, chunk_id in enumerate(top_ids, start=1) if chunk_id in relevant_ids),
        None,
    )
    risk_support = {
        risk
        for chunk_id in top_ids[:3]
        for risk in (qrels[chunk_id].supports if chunk_id in qrels else [])
    }
    duplicate_count = len(top_ids) - len(set(top_ids))
    unjudged_count = sum(chunk_id not in qrels for chunk_id in top_ids)
    public_hits = [] if run.abstained else top5[:3]
    citation_valid = all(_citation_valid(item) for item in public_hits)
    fabricated_no_answer = bool(case.noAnswer and public_hits)
    observed_relevance = [qrels[item.chunkId].relevance if item.chunkId in qrels else 0 for item in top5]
    ideal_relevance = sorted((item.relevance for item in case.qrels), reverse=True)
    return {
        "caseId": case.caseId,
        "split": case.split,
        "smoke": case.smoke,
        "queryStyle": case.queryStyle,
        "sourceLanguage": case.sourceLanguage,
        "documentFormat": case.documentFormat,
        "riskTypes": case.riskTypes,
        "riskLevel": case.riskLevel,
        "noAnswer": case.noAnswer,
        "abstained": run.abstained,
        "rankable": bool(relevant_ids),
        "candidateEvidenceHitAt5": first_relevant_rank is not None and first_relevant_rank <= 5,
        "relevantChunkCount": len(relevant_ids),
        "relevantChunkHitCountAt5": len(relevant_ids.intersection(top_ids)),
        "reciprocalRankAt5": round(1.0 / first_relevant_rank, 6) if first_relevant_rank else 0.0,
        "pooledNdcgAt3": round(_ndcg(observed_relevance, ideal_relevance, 3), 6),
        "pooledNdcgAt5": round(_ndcg(observed_relevance, ideal_relevance, 5), 6),
        "riskCoverageAt3": set(case.riskTypes).issubset(risk_support) if case.riskTypes else True,
        "supportedRiskTypesAt3": sorted(risk_support),
        "citationValid": citation_valid,
        "fabricatedNoAnswerCitation": fabricated_no_answer,
        "duplicateItemCountAt5": duplicate_count,
        "unjudgedItemCountAt5": unjudged_count,
        "retrievedItemCountAt5": len(top5),
        "qrelCompleteness": case.qrelCompleteness,
        "annotationStatus": case.annotationStatus,
        "_qrels": [item.model_dump(mode="json") for item in case.qrels],
        "_top10": [item.model_dump(mode="json") for item in top10],
        "top5": [item.model_dump(mode="json") for item in top5],
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return _empty_metrics()
    rankable = [row for row in rows if row["rankable"]]
    risk_cases = [row for row in rows if row["riskTypes"]]
    high_risk = [row for row in rows if row["riskLevel"] == "high"]
    no_answer = [row for row in rows if row["noAnswer"]]
    citation_cases = [row for row in rows if not row["abstained"] and row["top5"]]
    retrieved_items = sum(row["retrievedItemCountAt5"] for row in rows)
    relevant_total = sum(row["relevantChunkCount"] for row in rankable)
    relevant_hits = sum(row["relevantChunkHitCountAt5"] for row in rankable)

    metrics = {
        "caseCount": len(rows),
        "rankableCaseCount": len(rankable),
        "noAnswerCaseCount": len(no_answer),
        "candidateEvidenceHitRateAt5": _ratio(sum(row["candidateEvidenceHitAt5"] for row in rankable), len(rankable)),
        "relevantChunkRecallAt5": _ratio(relevant_hits, relevant_total),
        "mrrAt5": _mean(row["reciprocalRankAt5"] for row in rankable),
        "pooledNdcgAt3": _mean(row["pooledNdcgAt3"] for row in rankable),
        "pooledNdcgAt5": _mean(row["pooledNdcgAt5"] for row in rankable),
        "riskCoverageAt3": _ratio(sum(row["riskCoverageAt3"] for row in risk_cases), len(risk_cases)),
        "highRiskEvidenceHitRateAt5": _ratio(sum(row["candidateEvidenceHitAt5"] for row in high_risk), len(high_risk)),
        "highRiskEvidenceMissCountAt5": sum(not row["candidateEvidenceHitAt5"] for row in high_risk),
        "citationValidCaseRate": _ratio(sum(row["citationValid"] for row in citation_cases), len(citation_cases)),
        "noAnswerAbstentionAccuracy": _ratio(
            sum(row["abstained"] and not row["fabricatedNoAnswerCitation"] for row in no_answer),
            len(no_answer),
        ),
        "fabricatedNoAnswerCitationCount": sum(row["fabricatedNoAnswerCitation"] for row in no_answer),
        "unjudgedItemRateAt5": _ratio(sum(row["unjudgedItemCountAt5"] for row in rows), retrieved_items),
        "duplicateItemRateAt5": _ratio(sum(row["duplicateItemCountAt5"] for row in rows), retrieved_items),
    }
    metrics.update(_standard_ir_metrics(rows))
    return metrics


def _build_slices(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    dimensions = ("queryStyle", "riskLevel", "sourceLanguage", "documentFormat")
    output = {
        dimension: {
            value: _aggregate([row for row in rows if row[dimension] == value])
            for value in sorted({str(row[dimension]) for row in rows})
        }
        for dimension in dimensions
    }
    output["riskType"] = {
        risk_type: _aggregate([row for row in rows if risk_type in row["riskTypes"]])
        for risk_type in sorted({risk for row in rows for risk in row["riskTypes"]})
    }
    return output


def _standard_ir_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    rankable = [row for row in rows if row["rankable"]]
    if not rankable:
        return {"relevantChunkRecallAt10": 0.0, "irMeasuresNdcgAt3": 0.0, "irMeasuresNdcgAt5": 0.0}
    try:
        import ir_measures
        from ir_measures import Recall, nDCG
    except ImportError as exc:
        raise RuntimeError("IR_MEASURES_NOT_INSTALLED") from exc

    qrels: list[Any] = []
    run: list[Any] = []
    for row in rankable:
        relevance_by_id = {
            item["chunkId"]: int(item["relevance"])
            for item in _case_qrels_from_result(row)
        }
        for chunk_id, relevance in relevance_by_id.items():
            qrels.append(ir_measures.Qrel(row["caseId"], chunk_id, relevance))
        hits = row["_top10"]
        for rank, hit in enumerate(hits, start=1):
            run.append(ir_measures.ScoredDoc(row["caseId"], hit["chunkId"], float(len(hits) - rank + 1)))

    measured = ir_measures.calc_aggregate([Recall(rel=2) @ 5, Recall(rel=2) @ 10, nDCG @ 3, nDCG @ 5], qrels, run)
    return {
        "irMeasuresRelevantChunkRecallAt5": round(float(measured[Recall(rel=2) @ 5]), 6),
        "relevantChunkRecallAt10": round(float(measured[Recall(rel=2) @ 10]), 6),
        "irMeasuresNdcgAt3": round(float(measured[nDCG @ 3]), 6),
        "irMeasuresNdcgAt5": round(float(measured[nDCG @ 5]), 6),
    }


def _case_qrels_from_result(row: dict[str, Any]) -> list[dict[str, Any]]:
    # qrels are retained privately on the row only while calculating standard metrics.
    return row["_qrels"]


def _citation_valid(hit: RetrievalHit) -> bool:
    return bool(
        hit.sourceName.strip()
        and hit.sourceUrl.startswith(("http://", "https://"))
        and hit.sectionPath
        and len(hit.contentHash) >= 12
    )


def _ndcg(observed: list[int], ideal_candidates: list[int], k: int) -> float:
    import math

    dcg = sum((2**rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(observed[:k], start=1))
    ideal = sorted((int(value) for value in ideal_candidates), reverse=True)[:k]
    idcg = sum((2**rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 6) if denominator else 0.0


def _mean(values: Iterable[float]) -> float:
    rows = list(values)
    return round(sum(rows) / len(rows), 6) if rows else 0.0


def _empty_metrics() -> dict[str, Any]:
    return {
        "caseCount": 0,
        "rankableCaseCount": 0,
        "noAnswerCaseCount": 0,
        "candidateEvidenceHitRateAt5": 0.0,
        "relevantChunkRecallAt5": 0.0,
        "irMeasuresRelevantChunkRecallAt5": 0.0,
        "relevantChunkRecallAt10": 0.0,
        "mrrAt5": 0.0,
        "pooledNdcgAt3": 0.0,
        "pooledNdcgAt5": 0.0,
        "riskCoverageAt3": 0.0,
        "highRiskEvidenceHitRateAt5": 0.0,
        "highRiskEvidenceMissCountAt5": 0,
        "citationValidCaseRate": 0.0,
        "noAnswerAbstentionAccuracy": 0.0,
        "fabricatedNoAnswerCitationCount": 0,
        "unjudgedItemRateAt5": 0.0,
        "duplicateItemRateAt5": 0.0,
        "irMeasuresNdcgAt3": 0.0,
        "irMeasuresNdcgAt5": 0.0,
    }
