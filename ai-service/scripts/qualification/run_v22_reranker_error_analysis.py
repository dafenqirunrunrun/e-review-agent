from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.agent_rag.metrics import score_query  # noqa: E402
from app.agent_rag.reranker import GovernedReranker, RerankerConfig  # noqa: E402
from app.rag.document_contract import stable_hash  # noqa: E402
from run_v22_answerable_ranking_gate import build_candidate_pool_manifest  # noqa: E402
from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload, build_manifest, hash_ids  # noqa: E402


OUT = ROOT / "artifacts" / "real-model-chain"
DOCS = ROOT / "docs" / "real-model-chain"
EVALUATION_TIME_UTC = "2026-07-22T00:00:00Z"
SOURCE_COMMIT = "7c592a6f"
SELECTED = {"candidateK": 8, "maximumFinalK": 5, "batchSize": 8, "maxLength": 384}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        os.environ["AGENT_RAG_V22_ASSET_MANIFEST"] = args.asset_manifest
        apply_asset_manifest(Path(args.asset_manifest))
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    payload = benchmark_payload()
    manifest = build_manifest(payload)
    candidate_manifest, rows_by_case = build_candidate_pool_manifest(payload, manifest)
    cases = [case for case in payload["cases"] if case["relevantChunkIds"]]
    diagnostic_cases = [case for case in cases if set(case["relevantChunkIds"]) & {item.chunkId for item in rows_by_case[case["caseId"]]}]

    tokenizer = load_tokenizer()
    analysis = analyze_cases(diagnostic_cases, rows_by_case, tokenizer)
    truncation = build_truncation_audit(analysis)
    taxonomy = build_taxonomy(analysis)
    boundary = build_diagnostic_boundary(diagnostic_cases, manifest)
    baseline = build_regression_baseline(manifest, candidate_manifest)

    write_json(OUT / "v22-reranker-token-truncation-audit.json", truncation)
    write_json(OUT / "v22-reranker-case-level-error-analysis.json", analysis)
    write_json(OUT / "v22-reranker-error-taxonomy.json", taxonomy)
    write_markdown(DOCS / "V22_PHASE_88_DIAGNOSTIC_DATA_BOUNDARY.md", render_boundary(boundary))
    write_markdown(DOCS / "V22_PHASE_88_RERANKER_REGRESSION_BASELINE_LOCK.md", render_baseline_lock(baseline))
    write_markdown(DOCS / "V22_DETERMINISTIC_RERANKER_FEATURE_AUDIT.md", render_deterministic_audit())
    print("E_REVIEW_V22_RERANKER_ERROR_ANALYSIS_RECORDED")
    return 0


def analyze_cases(cases: list[dict[str, Any]], rows_by_case: dict[str, list[Any]], tokenizer: Any | None) -> dict[str, Any]:
    det = GovernedReranker(RerankerConfig(requested_type="deterministic", candidate_k=SELECTED["candidateK"], final_k=SELECTED["maximumFinalK"]))
    real = GovernedReranker(
        RerankerConfig(
            requested_type="local-model",
            model_path=os.getenv("RAG_RERANKER_MODEL_PATH", ""),
            model_name="BAAI/bge-reranker-v2-m3",
            device=os.getenv("RAG_RERANKER_DEVICE", "cuda"),
            use_fp16=True,
            batch_size=SELECTED["batchSize"],
            max_length=SELECTED["maxLength"],
            candidate_k=SELECTED["candidateK"],
            final_k=SELECTED["maximumFinalK"],
            timeout_ms=60000,
            real_required=True,
            provider_impl=os.getenv("RAG_RERANKER_PROVIDER_IMPL", "flagembedding"),
            normalize=True,
            model_id="BAAI/bge-reranker-v2-m3",
            model_revision="953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        )
    )
    rows = []
    latencies = []
    for case in cases:
        base = rows_by_case[case["caseId"]][: SELECTED["candidateK"]]
        started = time.perf_counter()
        det_result = det.rerank(case["query"], base, top_k=SELECTED["candidateK"], tenant_id=case["tenantId"], request_id=case["caseId"], evaluation_time_utc=EVALUATION_TIME_UTC)
        real_result = real.rerank(case["query"], base, top_k=SELECTED["candidateK"], tenant_id=case["tenantId"], request_id=case["caseId"], evaluation_time_utc=EVALUATION_TIME_UTC)
        latencies.append(round((time.perf_counter() - started) * 1000, 3))
        rows.append(case_row(case, base, det_result.candidates, det_result.scores, real_result.candidates, real_result.scores, tokenizer))
    summary = summarize_rows(rows, latencies)
    return {
        "schemaVersion": "agent-rag-v22-reranker-case-level-error-analysis-v2",
        "sourceCommit": SOURCE_COMMIT,
        "evaluationTimeUtc": EVALUATION_TIME_UTC,
        "selected": SELECTED,
        "caseCount": len(rows),
        **summary,
        "cases": rows,
    }


def case_row(case: dict[str, Any], base: list[Any], det: list[Any], det_scores: list[float], real: list[Any], real_scores: list[float], tokenizer: Any | None) -> dict[str, Any]:
    relevant = set(case["relevantChunkIds"])
    base_ids = [item.chunkId for item in base]
    det_ids = [item.chunkId for item in det]
    real_ids = [item.chunkId for item in real]
    real_score_by_id = {item.chunkId: score for item, score in zip(real, real_scores, strict=False)}
    wrong_scores = [score for item, score in zip(real, real_scores, strict=False) if item.chunkId not in relevant]
    relevant_scores = [float(real_score_by_id[chunk_id]) for chunk_id in relevant if chunk_id in real_score_by_id]
    original_ranks = ranks_for(base_ids, relevant)
    det_ranks = ranks_for(det_ids, relevant)
    real_ranks = ranks_for(real_ids, relevant)
    original_best = min([rank for rank in original_ranks if rank] or [0])
    real_best = min([rank for rank in real_ranks if rank] or [0])
    det_best = min([rank for rank in det_ranks if rank] or [0])
    delta = rank_delta(original_best, real_best)
    candidate_audits = [candidate_audit(case["query"], item, item.chunkId in relevant, tokenizer) for item in base]
    relevant_audits = [row for row in candidate_audits if row["isRelevant"]]
    near_duplicate_count = count_near_duplicates(base)
    top_wrong = first((item for item in real if item.chunkId not in relevant), None)
    top_wrong_score = float(real_score_by_id.get(top_wrong.chunkId, 0.0)) if top_wrong else 0.0
    best_relevant = max(relevant_scores) if relevant_scores else 0.0
    primary, signals = classify_error(case, base, original_best, real_best, det_best, relevant_audits, near_duplicate_count, best_relevant, top_wrong_score)
    return {
        "caseId": case["caseId"],
        "category": normalize_category(case["retrievalChallengeType"]),
        "queryCharacterCount": len(case["query"]),
        "queryTokenCount": token_count(tokenizer, case["query"]),
        "queryTruncated": False,
        "queryFieldNames": ["query"],
        "queryRepresentationHash": stable_hash({"query": case["query"]}),
        "candidateCount": len(base),
        "relevantChunkIdsHash": hash_ids(case["relevantChunkIds"]),
        "relevantOriginalRanks": original_ranks,
        "relevantDeterministicRanks": det_ranks,
        "relevantRealRerankerRanks": real_ranks,
        "relevantRerankerScores": [round(value, 8) for value in relevant_scores],
        "topIrrelevantRerankerScores": [round(value, 8) for value in wrong_scores[:3]],
        "bestRelevantScore": round(best_relevant, 8),
        "bestIrrelevantScore": round(max(wrong_scores) if wrong_scores else 0.0, 8),
        "scoreGap": round(best_relevant - (max(wrong_scores) if wrong_scores else 0.0), 8),
        "promotionCount": int(delta > 0),
        "demotionCount": int(delta < 0),
        "top5RelevantBefore": any(chunk_id in relevant for chunk_id in base_ids[: SELECTED["maximumFinalK"]]),
        "top5RelevantAfter": any(chunk_id in relevant for chunk_id in real_ids[: SELECTED["maximumFinalK"]]),
        "bestRelevantOriginalRank": original_best,
        "bestRelevantDeterministicRank": det_best,
        "bestRelevantRealRank": real_best,
        "rankDeltaFromOriginal": delta,
        "rankingGroup": ranking_group(original_best, real_best),
        "truncatedRelevantCount": sum(1 for row in relevant_audits if row["truncated"]),
        "relevantMeaningLikelyLost": sum(1 for row in relevant_audits if not row["relevantSpanRetained"]),
        "nearDuplicateCandidateCount": near_duplicate_count,
        "primaryErrorType": primary,
        "secondaryErrorTypes": secondary_errors(primary, signals),
        "evidenceSignals": signals,
        "reviewConfidence": confidence(primary, signals),
        "candidateInputAudit": [
            {key: value for key, value in row.items() if key != "isRelevant"}
            for row in candidate_audits
        ],
        "scores": {
            "original": score_ids(case, base_ids[: SELECTED["maximumFinalK"]]),
            "deterministic": score_ids(case, det_ids[: SELECTED["maximumFinalK"]]),
            "real": score_ids(case, real_ids[: SELECTED["maximumFinalK"]]),
        },
    }


def candidate_audit(query: str, item: Any, is_relevant: bool, tokenizer: Any | None) -> dict[str, Any]:
    row = item.row or {}
    content = str(row.get("content") or row.get("text") or "")
    title = str(row.get("title") or "")
    section = str(row.get("section_title") or row.get("sectionTitle") or "")
    query_tokens = token_count(tokenizer, query)
    passage_tokens = token_count(tokenizer, content)
    combined = pair_token_count(tokenizer, query, content)
    truncated = combined > SELECTED["maxLength"]
    return {
        "caseChunkHash": stable_hash({"caseInput": query, "chunkId": item.chunkId})[:24],
        "chunkIdHash": stable_hash(item.chunkId)[:24],
        "passageCharacterCount": len(content),
        "passageTokenCount": passage_tokens,
        "queryTokens": query_tokens,
        "combinedTokensBeforeTruncation": combined,
        "combinedTokensAfterTruncation": min(combined, SELECTED["maxLength"]),
        "truncated": truncated,
        "truncatedTokenCount": max(0, combined - SELECTED["maxLength"]),
        "passageTruncated": truncated,
        "titleIncluded": False,
        "sectionIncluded": False,
        "metadataIncluded": False,
        "titleAvailable": bool(title),
        "sectionAvailable": bool(section),
        "sourceTypeAvailable": bool(row.get("source_type") or row.get("sourceType")),
        "effectiveDateAvailable": bool(row.get("effective_from") or row.get("effectiveFrom")),
        "tenantScopeAvailable": bool(item.tenantId),
        "passageRepresentationHash": stable_hash({"passage": content})[:24],
        "isRelevant": is_relevant,
        "relevantSpanRetained": not truncated if is_relevant else True,
    }


def classify_error(
    case: dict[str, Any],
    base: list[Any],
    original_best: int,
    real_best: int,
    det_best: int,
    relevant_audits: list[dict[str, Any]],
    near_duplicate_count: int,
    best_relevant_score: float,
    best_wrong_score: float,
) -> tuple[str, dict[str, Any]]:
    row_by_id = {item.chunkId: item for item in base}
    relevant_docs = {row_by_id[chunk_id].documentId for chunk_id in case["relevantChunkIds"] if chunk_id in row_by_id}
    top_wrong_same_doc = False
    for item in base[: SELECTED["maximumFinalK"]]:
        if item.chunkId not in set(case["relevantChunkIds"]) and item.documentId in relevant_docs:
            top_wrong_same_doc = True
    signals = {
        "bestRelevantOriginalRank": original_best,
        "bestRelevantRealRank": real_best,
        "bestRelevantDeterministicRank": det_best,
        "relevantTruncated": any(row["truncated"] for row in relevant_audits),
        "relevantMeaningLikelyLost": any(not row["relevantSpanRetained"] for row in relevant_audits),
        "titleAvailableButMissing": any(row["titleAvailable"] and not row["titleIncluded"] for row in relevant_audits),
        "sectionAvailableButMissing": any(row["sectionAvailable"] and not row["sectionIncluded"] for row in relevant_audits),
        "metadataAvailableButMissing": any((row["sourceTypeAvailable"] or row["effectiveDateAvailable"] or row["tenantScopeAvailable"]) and not row["metadataIncluded"] for row in relevant_audits),
        "topWrongSameDocument": top_wrong_same_doc,
        "nearDuplicateCandidateCount": near_duplicate_count,
        "bestRelevantScore": round(best_relevant_score, 8),
        "bestWrongScore": round(best_wrong_score, 8),
        "scoreGap": round(best_relevant_score - best_wrong_score, 8),
        "deterministicPreservedOriginalRank": det_best == original_best and original_best > 0,
    }
    if signals["relevantMeaningLikelyLost"]:
        return "RELEVANT_INFORMATION_TRUNCATED", signals
    if signals["titleAvailableButMissing"] or signals["sectionAvailableButMissing"]:
        return "PASSAGE_REPRESENTATION_INCOMPLETE", signals
    if real_best == 0 and original_best:
        return "DESTRUCTIVE_REORDERING", signals
    if real_best and original_best and real_best - original_best >= 3:
        return "DESTRUCTIVE_REORDERING", signals
    if top_wrong_same_doc:
        return "LABEL_GRANULARITY_MISMATCH", signals
    if near_duplicate_count:
        return "SEMANTIC_NEAR_DUPLICATE", signals
    if normalize_category(case["retrievalChallengeType"]) in {"temporal", "tenant-isolation"} and signals["metadataAvailableButMissing"]:
        return "METADATA_REQUIRED_BUT_MISSING", signals
    return "MODEL_DOMAIN_MISMATCH", signals


def summarize_rows(rows: list[dict[str, Any]], latencies: list[float]) -> dict[str, Any]:
    groups = Counter(row["rankingGroup"] for row in rows)
    types = Counter(row["primaryErrorType"] for row in rows)
    return {
        "improvedCaseCount": groups["IMPROVED"],
        "unchangedCaseCount": groups["UNCHANGED"],
        "slightlyRegressedCaseCount": groups["SLIGHTLY_REGRESSED"],
        "severelyRegressedCaseCount": groups["SEVERELY_REGRESSED"],
        "errorTypeCounts": dict(sorted(types.items())),
        "relevantPromotionRate": round(sum(1 for row in rows if row["promotionCount"]) / max(1, len(rows)), 6),
        "relevantDemotionRate": round(sum(1 for row in rows if row["demotionCount"]) / max(1, len(rows)), 6),
        "top5Retention": round(sum(1 for row in rows if row["top5RelevantBefore"] and row["top5RelevantAfter"]) / max(1, sum(1 for row in rows if row["top5RelevantBefore"])), 6),
        "latency": {"p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95)},
    }


def build_truncation_audit(analysis: dict[str, Any]) -> dict[str, Any]:
    candidates = [item for row in analysis["cases"] for item in row["candidateInputAudit"]]
    relevant = [item for row in analysis["cases"] for item in row["candidateInputAudit"] if item["chunkIdHash"] in {x["chunkIdHash"] for x in row["candidateInputAudit"][:0]}]
    relevant_total = sum(len(row["relevantOriginalRanks"]) for row in analysis["cases"])
    relevant_truncated = sum(row["truncatedRelevantCount"] for row in analysis["cases"])
    return {
        "schemaVersion": "agent-rag-v22-reranker-token-truncation-audit-v1",
        "sourceCommit": SOURCE_COMMIT,
        "selected": SELECTED,
        "candidateCount": len(candidates),
        "queryTruncationCases": 0,
        "passageTruncationCases": sum(1 for item in candidates if item["passageTruncated"]),
        "relevantCandidatesTotal": relevant_total,
        "relevantCandidatesTruncated": relevant_truncated,
        "relevantMeaningLikelyLost": sum(row["relevantMeaningLikelyLost"] for row in analysis["cases"]),
        "irrelevantCandidatesTruncated": max(0, sum(1 for item in candidates if item["passageTruncated"]) - relevant_truncated),
        "rootCauseIfHigh": "RELEVANT_INFORMATION_TRUNCATED" if relevant_truncated > max(3, relevant_total * 0.2) else "TRUNCATION_NOT_PRIMARY",
        "tokenizerAvailable": any(item["queryTokens"] for item in candidates),
    }


def build_taxonomy(analysis: dict[str, Any]) -> dict[str, Any]:
    records = [
        {
            "caseId": row["caseId"],
            "primaryErrorType": row["primaryErrorType"],
            "secondaryErrorTypes": row["secondaryErrorTypes"],
            "evidenceSignals": row["evidenceSignals"],
            "reviewConfidence": row["reviewConfidence"],
        }
        for row in analysis["cases"]
    ]
    return {
        "schemaVersion": "agent-rag-v22-reranker-error-taxonomy-v1",
        "sourceCommit": SOURCE_COMMIT,
        "caseCount": len(records),
        "typeCounts": dict(sorted(Counter(row["primaryErrorType"] for row in records).items())),
        "cases": records,
    }


def build_diagnostic_boundary(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    ids = [case["caseId"] for case in cases]
    return {
        "schemaVersion": "agent-rag-v22-phase88-diagnostic-data-boundary-v1",
        "diagnosticSetHash": stable_hash({"caseIds": ids, "benchmarkHash": manifest["benchmarkHash"]}),
        "diagnosticCaseCount": len(ids),
        "diagnosticCaseIdsHash": hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest(),
        "consumedAtCommit": SOURCE_COMMIT,
        "futureQualificationUseAllowed": False,
        "allowedUse": ["error analysis", "root cause localization", "limited input ablation"],
        "forbiddenUse": ["final unbiased evaluation", "MODEL_RERANKER_VERIFIED evidence"],
    }


def build_regression_baseline(manifest: dict[str, Any], candidate_manifest: dict[str, Any]) -> dict[str, Any]:
    gate = read_json(OUT / "v22-answerable-ranking-gate.json")
    assets = read_json(OUT / "model-assets-summary.json")
    reranker = (assets.get("assets") or assets).get("reranker", {})
    evidence_files = [
        "v22-answerable-ranking-gate.json",
        "v22-answerability-canonical-candidate-pool-manifest.json",
        "V22_PHASE_87_ANSWERABLE_RANKING_REPORT.md",
        "V22_PHASE_87_CORRECTNESS_BASELINE_LOCK.md",
    ]
    return {
        "schemaVersion": "agent-rag-v22-phase88-reranker-regression-baseline-lock-v1",
        "sourceCommit": SOURCE_COMMIT,
        "modelId": reranker.get("modelId") or "BAAI/bge-reranker-v2-m3",
        "revision": reranker.get("revision") or "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        "fingerprint": reranker.get("assetFingerprint") or reranker.get("fingerprint") or "",
        "dtype": "fp16",
        "candidateK": SELECTED["candidateK"],
        "maximumFinalK": SELECTED["maximumFinalK"],
        "maxLength": SELECTED["maxLength"],
        "batchSize": SELECTED["batchSize"],
        "candidatePoolHash": candidate_manifest["candidatePoolHash"],
        "knowledgeSnapshotHash": manifest["knowledgeHash"],
        "evaluationTimeUtc": EVALUATION_TIME_UTC,
        "metrics": {
            "deterministic": gate.get("subsets", {}).get("overall", {}).get("deterministic", {}),
            "real": gate.get("subsets", {}).get("overall", {}).get("real", {}),
            "deterministicSemantic": gate.get("subsets", {}).get("semantic", {}).get("deterministic", {}),
            "realSemantic": gate.get("subsets", {}).get("semantic", {}).get("real", {}),
            "retrievalMissedAnswerableCases": gate.get("retrievalMissedAnswerableCases"),
            "retrievalEligibleAnswerableCases": gate.get("retrievalEligibleAnswerableCases"),
        },
        "evidenceSha256": {name: sha256_for_evidence(name) for name in evidence_files},
    }


def render_boundary(payload: dict[str, Any]) -> str:
    return f"""# V2.2 Phase 8.8 Diagnostic Data Boundary

The 74 retrieval-eligible answerable cases from Phase 8.7 are now consumed diagnostic data.

- Diagnostic set hash: `{payload['diagnosticSetHash']}`
- Diagnostic case count: `{payload['diagnosticCaseCount']}`
- Diagnostic case ids hash: `{payload['diagnosticCaseIdsHash']}`
- Consumed at commit: `{payload['consumedAtCommit']}`
- Future qualification use allowed: `{payload['futureQualificationUseAllowed']}`

These cases may be used for error analysis and limited ablation only. They must not be used as final unbiased evidence for `MODEL_RERANKER_VERIFIED`.
"""


def render_baseline_lock(payload: dict[str, Any]) -> str:
    m = payload["metrics"]
    return f"""# V2.2 Phase 8.8 Reranker Regression Baseline Lock

- Source commit: `{payload['sourceCommit']}`
- Model: `{payload['modelId']}`
- Revision: `{payload['revision']}`
- Fingerprint: `{payload['fingerprint']}`
- Dtype: `{payload['dtype']}`
- Candidate K: `{payload['candidateK']}`
- Maximum final K: `{payload['maximumFinalK']}`
- Max length: `{payload['maxLength']}`
- Batch size: `{payload['batchSize']}`
- Candidate pool hash: `{payload['candidatePoolHash']}`
- Knowledge snapshot hash: `{payload['knowledgeSnapshotHash']}`
- Evaluation time UTC: `{payload['evaluationTimeUtc']}`

## Frozen Metrics

- Retrieval eligible answerable cases: `{m['retrievalEligibleAnswerableCases']}`
- Retrieval missed answerable cases: `{m['retrievalMissedAnswerableCases']}`
- Deterministic overall nDCG@5: `{m['deterministic'].get('ndcgAt5')}`
- Real overall nDCG@5: `{m['real'].get('ndcgAt5')}`
- Deterministic overall MRR: `{m['deterministic'].get('mrr')}`
- Real overall MRR: `{m['real'].get('mrr')}`
- Deterministic semantic nDCG@5: `{m['deterministicSemantic'].get('ndcgAt5')}`
- Real semantic nDCG@5: `{m['realSemantic'].get('ndcgAt5')}`
- Deterministic semantic MRR: `{m['deterministicSemantic'].get('mrr')}`
- Real semantic MRR: `{m['realSemantic'].get('mrr')}`

## Evidence Hashes

{chr(10).join(f'- `{key}`: `{value}`' for key, value in payload['evidenceSha256'].items())}
"""


def render_deterministic_audit() -> str:
    return """# V2.2 Deterministic Reranker Feature Audit

The deterministic reranker is not a pure same-input cross-encoder baseline.

## Features Used

- Original retrieval rank: yes, through stable tie-breaking after scoring.
- BM25 score: yes, indirectly through `fusionScore`.
- Dense score: yes, indirectly through `fusionScore` when the hybrid candidate came from dense retrieval.
- RRF score: yes, `fusionScore` is the primary score basis.
- Source priority: no explicit source priority in the reranker itself.
- Temporal priority: no explicit temporal priority in the reranker itself; temporal eligibility has already filtered candidates.
- Document status: no scoring boost, but eligibility filtering rejects invalid evidence before reranking.
- Exact keyword overlap: yes, `overlap * 0.01` is added to fusion score.
- Task-specific metadata: yes, through upstream tenant/time/status eligibility and RRF features not visible to the real cross-encoder passage.

## Fairness Observation

The real cross-encoder receives query plus content-only passage. It does not receive fusion score, original RRF rank, source type, title, section title, tenant scope, or effective date. Therefore the deterministic baseline has a task-specific information advantage. This explains part of the measured gap but does not qualify the real reranker.

Current engineering default should remain:

`BAAI/bge-m3 -> deterministic reranker -> Qwen/Qwen3-1.7B`
"""


def score_ids(case: dict[str, Any], ids: list[str]) -> dict[str, float]:
    return score_query(
        retrieved_chunk_ids=ids,
        relevant_chunk_ids=set(case["relevantChunkIds"]),
        forbidden_chunk_ids=set(case["forbiddenChunkIds"]),
        relevance_grades=case["relevanceGrades"],
    )


def ranks_for(ids: list[str], relevant: set[str]) -> list[int]:
    return [ids.index(chunk_id) + 1 if chunk_id in ids else 0 for chunk_id in sorted(relevant)]


def rank_delta(original_best: int, real_best: int) -> int:
    if not original_best or not real_best:
        return -99 if original_best and not real_best else 0
    return original_best - real_best


def ranking_group(original_best: int, real_best: int) -> str:
    delta = rank_delta(original_best, real_best)
    if delta > 0:
        return "IMPROVED"
    if delta == 0:
        return "UNCHANGED"
    if real_best == 0 or delta <= -3 or (original_best <= 5 and real_best > 5):
        return "SEVERELY_REGRESSED"
    return "SLIGHTLY_REGRESSED"


def secondary_errors(primary: str, signals: dict[str, Any]) -> list[str]:
    values = []
    if primary != "PASSAGE_REPRESENTATION_INCOMPLETE" and (signals["titleAvailableButMissing"] or signals["sectionAvailableButMissing"]):
        values.append("PASSAGE_REPRESENTATION_INCOMPLETE")
    if primary != "METADATA_REQUIRED_BUT_MISSING" and signals["metadataAvailableButMissing"]:
        values.append("METADATA_REQUIRED_BUT_MISSING")
    if primary != "SEMANTIC_NEAR_DUPLICATE" and signals["nearDuplicateCandidateCount"]:
        values.append("SEMANTIC_NEAR_DUPLICATE")
    if primary != "DESTRUCTIVE_REORDERING" and signals["bestRelevantRealRank"] and signals["bestRelevantOriginalRank"] and signals["bestRelevantRealRank"] > signals["bestRelevantOriginalRank"]:
        values.append("DESTRUCTIVE_REORDERING")
    return values[:4]


def confidence(primary: str, signals: dict[str, Any]) -> str:
    if primary in {"RELEVANT_INFORMATION_TRUNCATED", "PASSAGE_REPRESENTATION_INCOMPLETE", "DESTRUCTIVE_REORDERING"}:
        return "high"
    if signals["scoreGap"] < 0 or signals["metadataAvailableButMissing"]:
        return "medium"
    return "low"


def count_near_duplicates(candidates: list[Any]) -> int:
    docs = Counter(item.documentId for item in candidates)
    hashes = Counter(str((item.row or {}).get("content_hash") or "") for item in candidates)
    return sum(1 for count in docs.values() if count > 1) + sum(1 for count in hashes.values() if count > 1)


def token_count(tokenizer: Any | None, text: str) -> int:
    if tokenizer is not None:
        try:
            return len(tokenizer.encode(text, add_special_tokens=False))
        except Exception:
            pass
    return len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", text))


def pair_token_count(tokenizer: Any | None, query: str, passage: str) -> int:
    if tokenizer is not None:
        try:
            encoded = tokenizer(query, passage, add_special_tokens=True, truncation=False)
            return len(encoded.get("input_ids", []))
        except Exception:
            pass
    return token_count(None, query) + token_count(None, passage) + 3


def load_tokenizer() -> Any | None:
    model_path = os.getenv("RAG_RERANKER_MODEL_PATH", "")
    if not model_path:
        return None
    try:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    except Exception:
        return None


def normalize_category(value: str) -> str:
    return "no-answer" if value == "negative/no-answer" else value


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = round((len(ordered) - 1) * fraction)
    return round(ordered[max(0, min(index, len(ordered) - 1))], 3)


def first(values: Any, default: Any = None) -> Any:
    for value in values:
        return value
    return default


def sha256_for_evidence(name: str) -> str:
    for base in (OUT, DOCS):
        path = base / name
        if path.exists():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    return ""


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
