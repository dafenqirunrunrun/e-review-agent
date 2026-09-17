from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from app.policy_rag.models import PolicyChunk


def audit_legacy_challenge_qrels(
    cases: list[dict[str, Any]],
    chunks: Iterable[PolicyChunk],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    corpus = list(chunks)
    corpus_ids = {item.chunkId for item in corpus}
    judgments = [row for case in cases for row in case.get("policyJudgments", [])]
    judged_ids = {str(row.get("chunkId", "")) for row in judgments if row.get("chunkId")}
    referenced_missing = sorted(judged_ids - corpus_ids)
    duplicate_case_ids = _duplicates(str(case.get("caseId", "")) for case in cases)
    duplicate_texts = _duplicates(str(case.get("reviewText", "")) for case in cases)
    confidence = Counter(str(case.get("annotationConfidence", "unknown")) for case in cases)
    completeness = Counter(str(case.get("qrelCompleteness", "missing")) for case in cases)
    relevance = Counter(int(row.get("semanticRelevance", -1)) for row in judgments)
    sources = Counter(str(row.get("sourceName", "unknown")) for row in judgments)
    no_answer = [case for case in cases if not case.get("policyJudgments")]
    adjudication = [case for case in cases if case.get("requiresAdjudication")]
    rationale_missing = [
        f"{case.get('caseId')}:{row.get('chunkId')}"
        for case in cases
        for row in case.get("policyJudgments", [])
        if not str(row.get("judgmentRationale", "")).strip()
    ]
    blockers = [
        "LEGACY_TEXTS_EXPOSED_TO_CANDIDATES",
        "QRELS_POOLED_PARTIAL",
        "INDEPENDENT_HUMAN_ADJUDICATION_PENDING",
        "UNJUDGED_CHUNKS_REMAIN",
    ]
    if referenced_missing:
        blockers.append("QREL_REFERENCES_MISSING_CHUNK")
    if rationale_missing:
        blockers.append("QREL_RATIONALE_MISSING")
    if duplicate_case_ids:
        blockers.append("CASE_ID_DUPLICATE")
    return {
        "schemaVersion": "rag-quality-legacy-qrels-audit-v1",
        "status": "DIAGNOSTIC_VALID_PROMOTION_BLOCKED",
        "datasetVersion": manifest.get("datasetVersion", "unknown"),
        "caseCount": len(cases),
        "rankableCaseCount": len(cases) - len(no_answer),
        "noAnswerCandidateCount": len(no_answer),
        "judgmentCount": len(judgments),
        "judgedChunkCount": len(judged_ids.intersection(corpus_ids)),
        "corpusChunkCount": len(corpus),
        "judgedCorpusCoverage": round(len(judged_ids.intersection(corpus_ids)) / len(corpus), 6) if corpus else 0.0,
        "unjudgedChunkCount": len(corpus_ids - judged_ids),
        "missingChunkReferences": referenced_missing,
        "requiresAdjudicationCount": len(adjudication),
        "annotationConfidenceCounts": dict(sorted(confidence.items())),
        "qrelCompletenessCounts": dict(sorted(completeness.items())),
        "relevanceCounts": {str(key): value for key, value in sorted(relevance.items())},
        "sourceJudgmentCounts": dict(sorted(sources.items())),
        "candidateExposedTextCount": int(manifest.get("validation", {}).get("v1ExactTextReuseCount", 0)),
        "duplicateCaseIds": duplicate_case_ids,
        "duplicateReviewTextCount": len(duplicate_texts),
        "missingRationaleCount": len(rationale_missing),
        "missingRationales": rationale_missing,
        "promotionEligible": False,
        "promotionBlockers": blockers,
    }


def _duplicates(values: Iterable[str]) -> list[str]:
    counts = Counter(value for value in values if value)
    return sorted(value for value, count in counts.items() if count > 1)
