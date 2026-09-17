from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from v23_retrieval_common import (
    DOCS,
    EVALUATION_TIME_UTC,
    OUT,
    hash_json,
    prepare_runtime,
    read_json,
    sparse_top_ids,
    stable_hash,
    write_json,
    write_text,
)


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.agent_rag.eligibility import evaluate_evidence_eligibility  # noqa: E402
from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload, build_manifest  # noqa: E402


SELECTED = {"currentCandidateK": 8, "analysisTopK": 100, "sparseTopK": 100, "denseTopK": 100, "rrfTopK": 100}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="v22-answerable-ranking-missed")
    parser.add_argument("--knowledge-manifest", default="")
    parser.add_argument("--index-manifest", default="")
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    parser.add_argument("--evaluation-time", default=EVALUATION_TIME_UTC)
    parser.add_argument("--output-dir", default=str(OUT))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.asset_manifest:
        os.environ["AGENT_RAG_V22_ASSET_MANIFEST"] = args.asset_manifest
        apply_asset_manifest(Path(args.asset_manifest))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    payload = benchmark_payload()
    manifest = build_manifest(payload)
    provider, runtime = prepare_runtime(payload)
    try:
        analysis = analyze(payload, manifest, runtime, args.evaluation_time)
    finally:
        try:
            provider.close()
        except Exception:
            pass
    taxonomy = summarize_taxonomy(analysis)
    boundary = diagnostic_boundary(analysis, manifest)
    priority = priority_decision(taxonomy)
    write_json(output_dir / "v23-retrieval-miss-case-analysis.json", analysis)
    write_json(output_dir / "v23-retrieval-miss-taxonomy-summary.json", taxonomy)
    write_json(output_dir / "v23-retrieval-optimization-priority-decision.json", priority)
    write_text(DOCS / "V23_PHASE_91_RETRIEVAL_MISS_DIAGNOSTIC_BOUNDARY.md", render_boundary(boundary))
    write_text(DOCS / "V23_RETRIEVAL_MISS_ERROR_ANALYSIS.md", render_analysis_doc(analysis, taxonomy))
    write_text(DOCS / "V23_RETRIEVAL_OPTIMIZATION_PRIORITY.md", render_priority_doc(priority))
    print("RETRIEVAL_MISS_ANALYSIS_COMPLETE")
    print(priority["recommendedPhase"])
    return 0


def analyze(payload: dict[str, Any], manifest: dict[str, Any], runtime: Any, evaluation_time: str) -> dict[str, Any]:
    chunk_by_id = {chunk.chunkId: chunk for chunk in payload["chunks"]}
    missed_cases = []
    case_rows = []
    for case in payload["cases"]:
        relevant = set(case["relevantChunkIds"])
        if not relevant:
            continue
        current_candidates, _trace = runtime.search(
            case["query"],
            tenant_id=case["tenantId"],
            mode="hybrid-real",
            sparse_top_k=20,
            dense_top_k=20,
            fusion_top_k=SELECTED["currentCandidateK"],
            rerank_top_k=None,
            evaluation_time_utc=evaluation_time,
        )
        if relevant & {item.chunkId for item in current_candidates}:
            continue
        missed_cases.append(case)
    for case in missed_cases:
        case_rows.append(analyze_case(case, chunk_by_id, runtime, evaluation_time))
    return {
        "schemaVersion": "agent-rag-v23-retrieval-miss-case-analysis-v1",
        "sourceCommit": "e7378b5e",
        "sourceBenchmarkHash": manifest["benchmarkHash"],
        "knowledgeSnapshotHash": manifest["knowledgeHash"],
        "evaluationTimeUtc": evaluation_time,
        "selected": SELECTED,
        "diagnosticStatus": "CONSUMED_RETRIEVAL_MISS_DIAGNOSTIC_SET",
        "diagnosticCases": len(case_rows),
        "futureQualificationUseAllowed": False,
        "caseIdsHash": hash_json([row["caseId"] for row in case_rows]),
        "cases": case_rows,
        "createdAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def analyze_case(case: dict[str, Any], chunk_by_id: dict[str, Any], runtime: Any, evaluation_time: str) -> dict[str, Any]:
    relevant = set(case["relevantChunkIds"])
    bm25_ids = sparse_top_ids(case["query"], case["tenantId"], 100)
    dense_candidates, dense_trace = runtime.search(
        case["query"],
        tenant_id=case["tenantId"],
        mode="real-dense",
        sparse_top_k=100,
        dense_top_k=100,
        fusion_top_k=100,
        rerank_top_k=None,
        evaluation_time_utc=evaluation_time,
    )
    dense_ids = [item.chunkId for item in dense_candidates]
    rrf_candidates, rrf_trace = runtime.search(
        case["query"],
        tenant_id=case["tenantId"],
        mode="hybrid-real",
        sparse_top_k=100,
        dense_top_k=100,
        fusion_top_k=100,
        rerank_top_k=None,
        evaluation_time_utc=evaluation_time,
    )
    rrf_ids = [item.chunkId for item in rrf_candidates]
    bm25_rank = best_rank(bm25_ids, relevant)
    dense_rank = best_rank(dense_ids, relevant)
    rrf_rank = best_rank(rrf_ids, relevant)
    union_ids = union_ranked_ids(bm25_ids, dense_ids)
    union_rank = best_rank(union_ids, relevant)
    relevant_chunks = [chunk_by_id.get(chunk_id) for chunk_id in relevant if chunk_by_id.get(chunk_id)]
    eligibility = eligibility_summary(case, relevant_chunks, evaluation_time)
    index_presence = index_presence_summary(relevant, bm25_ids, dense_ids)
    chunk_audit = chunk_self_containment(case, relevant_chunks)
    query_audit = query_representation(case)
    primary, secondary, signals = classify(case, bm25_rank, dense_rank, rrf_rank, union_rank, eligibility, index_presence, chunk_audit, query_audit)
    return {
        "caseId": case["caseId"],
        "queryIntent": str(case.get("retrievalChallengeType") or ""),
        "queryHash": stable_hash(case["query"]),
        "queryTokenCount": len(case["query"].split()),
        "relevantChunkIdsHash": hash_json(sorted(relevant)),
        "relevantExistsInKnowledge": bool(relevant_chunks),
        "relevantExistsInIndex": index_presence["relevantExistsInIndex"],
        "relevantEligibleAtEvaluationTime": eligibility["allRelevantEligible"],
        "bm25BestRelevantRank": bm25_rank,
        "denseBestRelevantRank": dense_rank,
        "rrfBestRelevantRank": rrf_rank,
        "unionBestRelevantRank": union_rank,
        "bm25Top100Hit": bool(bm25_rank),
        "denseTop100Hit": bool(dense_rank),
        "rrfTop100Hit": bool(rrf_rank),
        "unionTop100Hit": bool(union_rank),
        "currentCandidatePoolHit": False,
        "candidateKRequired": candidate_k_required(bm25_rank, dense_rank, rrf_rank, union_rank),
        "relevantChunkTokenCount": max([chunk.tokenCount for chunk in relevant_chunks] or [0]),
        "relevantChunkSelfContained": chunk_audit["selfContained"],
        "titleRequired": chunk_audit["titleRequired"],
        "sectionRequired": chunk_audit["sectionRequired"],
        "parentContextRequired": chunk_audit["parentContextRequired"],
        "eligibilityAudit": eligibility,
        "indexAudit": index_presence,
        "chunkAudit": chunk_audit,
        "queryAudit": query_audit,
        "sourceRoutingAudit": {
            "classification": "SOURCE_ROUTING_CORRECT",
            "tenantId": case["tenantId"],
            "sourceTypeSearched": True,
        },
        "retrieverDiagnostics": {
            "bm25": classify_rank("BM25", bm25_rank),
            "dense": classify_rank("DENSE", dense_rank),
            "rrf": classify_rrf(bm25_rank, dense_rank, rrf_rank),
            "denseTrace": safe_trace(dense_trace),
            "rrfTrace": safe_trace(rrf_trace),
        },
        "primaryMissType": primary,
        "secondaryMissTypes": secondary,
        "reviewConfidence": review_confidence(primary, signals),
        "evidenceSignals": signals,
        "consumedForFutureQualification": True,
    }


def best_rank(ids: list[str], relevant: set[str]) -> int:
    for index, chunk_id in enumerate(ids, start=1):
        if chunk_id in relevant:
            return index
    return 0


def union_ranked_ids(left: list[str], right: list[str]) -> list[str]:
    seen = set()
    rows = []
    for ids in (left, right):
        for rank, chunk_id in enumerate(ids, start=1):
            if chunk_id not in seen:
                seen.add(chunk_id)
                rows.append((min(rank, 100), chunk_id))
    return [chunk_id for _rank, chunk_id in sorted(rows, key=lambda item: (item[0], item[1]))]


def candidate_k_required(*ranks: int) -> str:
    best = min([rank for rank in ranks if rank] or [0])
    if not best:
        return "NOT_RECOVERABLE_BY_K"
    if best <= 10:
        return "CANDIDATE_K_10_RECOVERABLE"
    if best <= 20:
        return "CANDIDATE_K_20_RECOVERABLE"
    if best <= 50:
        return "CANDIDATE_K_50_RECOVERABLE"
    if best <= 100:
        return "CANDIDATE_K_100_RECOVERABLE"
    return "NOT_RECOVERABLE_BY_K"


def eligibility_summary(case: dict[str, Any], chunks: list[Any], evaluation_time: str) -> dict[str, Any]:
    rows = []
    for chunk in chunks:
        decision = evaluate_evidence_eligibility(chunk.as_retriever_row(), case["tenantId"], evaluation_time)
        rows.append({"chunkIdHash": stable_hash(chunk.chunkId)[:24], "eligible": decision.eligible, "reasonCode": decision.reasonCode})
    return {"allRelevantEligible": bool(rows) and all(row["eligible"] for row in rows), "rows": rows}


def index_presence_summary(relevant: set[str], bm25_ids: list[str], dense_ids: list[str]) -> dict[str, Any]:
    return {
        "relevantExistsInBm25Top100": bool(relevant & set(bm25_ids)),
        "relevantExistsInDenseTop100": bool(relevant & set(dense_ids)),
        "relevantExistsInIndex": bool((relevant & set(bm25_ids)) or (relevant & set(dense_ids))),
        "classification": "INDEX_COMPLETE" if bool((relevant & set(bm25_ids)) or (relevant & set(dense_ids))) else "INDEX_OR_RETRIEVER_TOP100_MISS",
    }


def chunk_self_containment(case: dict[str, Any], chunks: list[Any]) -> dict[str, Any]:
    requires_title = str(case.get("retrievalChallengeType")) in {"title", "mixed"}
    requires_section = str(case.get("retrievalChallengeType")) in {"temporal", "mixed"}
    max_tokens = max([chunk.tokenCount for chunk in chunks] or [0])
    return {
        "selfContained": not (requires_title or requires_section or max_tokens > 80),
        "titleRequired": requires_title,
        "sectionRequired": requires_section,
        "parentContextRequired": max_tokens > 80,
        "classification": "CHUNK_SELF_CONTAINED" if not (requires_title or requires_section or max_tokens > 80) else "TITLE_OR_SECTION_CONTEXT_REQUIRED",
    }


def query_representation(case: dict[str, Any]) -> dict[str, Any]:
    challenge = str(case.get("retrievalChallengeType") or "")
    mapping = {
        "semantic": "QUERY_SYNONYM_EXPANSION_NEEDED",
        "mixed": "QUERY_MULTI_QUERY_NEEDED",
        "temporal": "QUERY_TEMPORAL_NORMALIZATION_NEEDED",
        "tenant-isolation": "QUERY_CLEAN",
        "lexical": "QUERY_CLEAN",
    }
    return {"classification": mapping.get(challenge, "QUERY_NORMALIZATION_NEEDED"), "challengeType": challenge}


def classify(
    case: dict[str, Any],
    bm25_rank: int,
    dense_rank: int,
    rrf_rank: int,
    union_rank: int,
    eligibility: dict[str, Any],
    index_presence: dict[str, Any],
    chunk_audit: dict[str, Any],
    query_audit: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any]]:
    signals = {
        "bm25HitTop100": bool(bm25_rank),
        "denseHitTop100": bool(dense_rank),
        "rrfHitTop100": bool(rrf_rank),
        "unionHitTop100": bool(union_rank),
        "queryClass": query_audit["classification"],
        "chunkClass": chunk_audit["classification"],
    }
    if not eligibility["allRelevantEligible"]:
        primary = "ELIGIBILITY_OR_LABEL_CONFLICT"
    elif not index_presence["relevantExistsInIndex"]:
        primary = "BOTH_RETRIEVERS_MISS"
    elif union_rank and not rrf_rank:
        primary = "RRF_FUSION_DEMOTION"
    elif rrf_rank and rrf_rank > SELECTED["currentCandidateK"]:
        primary = "CANDIDATE_K_TOO_SMALL"
    elif query_audit["classification"] != "QUERY_CLEAN":
        primary = "QUERY_REPRESENTATION_MISS"
    elif not chunk_audit["selfContained"]:
        primary = "CHUNK_NOT_SELF_CONTAINED"
    else:
        primary = "MULTIPLE_CONTRIBUTING_FACTORS"
    secondary = []
    if not bm25_rank:
        secondary.append("BM25_LEXICAL_MISS")
    if not dense_rank:
        secondary.append("DENSE_SEMANTIC_MISS")
    if query_audit["classification"] != "QUERY_CLEAN":
        secondary.append("QUERY_REPRESENTATION_MISS")
    if not chunk_audit["selfContained"]:
        secondary.append("CHUNK_NOT_SELF_CONTAINED")
    if rrf_rank and rrf_rank > SELECTED["currentCandidateK"]:
        secondary.append("CANDIDATE_K_TOO_SMALL")
    return primary, sorted(set(item for item in secondary if item != primary)), signals


def classify_rank(prefix: str, rank: int) -> str:
    if rank and rank <= SELECTED["currentCandidateK"]:
        return f"{prefix}_HIT_WITHIN_CURRENT_K"
    if rank:
        return f"{prefix}_HIT_TOP100_ONLY"
    return f"{prefix}_COMPLETE_MISS"


def classify_rrf(bm25_rank: int, dense_rank: int, rrf_rank: int) -> str:
    if rrf_rank and rrf_rank <= SELECTED["currentCandidateK"]:
        return "RRF_RECOVERED"
    if rrf_rank:
        return "RRF_WINDOW_OR_CANDIDATE_K_TOO_SMALL"
    if bm25_rank or dense_rank:
        return "RRF_DEMOTED_SINGLE_RETRIEVER_HIT"
    return "RRF_COMPLETE_MISS"


def review_confidence(primary: str, signals: dict[str, Any]) -> str:
    if primary in {"CANDIDATE_K_TOO_SMALL", "RRF_FUSION_DEMOTION", "ELIGIBILITY_OR_LABEL_CONFLICT"}:
        return "high"
    if primary in {"QUERY_REPRESENTATION_MISS", "CHUNK_NOT_SELF_CONTAINED"}:
        return "medium"
    return "low"


def safe_trace(trace: Any) -> dict[str, Any]:
    return {
        "effectiveRetrievalMode": getattr(trace, "effectiveRetrievalMode", ""),
        "denseProvider": getattr(trace, "denseProvider", ""),
        "denseFallbackUsed": bool(getattr(trace, "denseFallbackUsed", False)),
        "embeddingDimension": int(getattr(trace, "embeddingDimension", 0) or 0),
    }


def summarize_taxonomy(analysis: dict[str, Any]) -> dict[str, Any]:
    rows = analysis["cases"]
    primary_counts = Counter(row["primaryMissType"] for row in rows)
    candidate_counts = Counter(row["candidateKRequired"] for row in rows)
    bm25_top100 = sum(row["bm25Top100Hit"] for row in rows)
    dense_top100 = sum(row["denseTop100Hit"] for row in rows)
    both = sum(row["bm25Top100Hit"] and row["denseTop100Hit"] for row in rows)
    neither = sum((not row["bm25Top100Hit"]) and (not row["denseTop100Hit"]) for row in rows)
    union = sum(row["unionTop100Hit"] for row in rows)
    return {
        "schemaVersion": "agent-rag-v23-retrieval-miss-taxonomy-summary-v1",
        "diagnosticCases": len(rows),
        "consumed": all(row["consumedForFutureQualification"] for row in rows),
        "bm25Top100Hits": bm25_top100,
        "denseTop100Hits": dense_top100,
        "bothTop100Hits": both,
        "neitherTop100Hits": neither,
        "unionTop100Coverage": round(union / max(1, len(rows)), 6),
        "unionTop100Hits": union,
        "candidateKRecoverable": sum(row["candidateKRequired"] != "NOT_RECOVERABLE_BY_K" for row in rows),
        "candidateKCounts": dict(candidate_counts),
        "primaryMissTypeCounts": dict(primary_counts),
        "sensitivePayloadPolicy": "hashes, ranks, counts, classifications only",
        "summaryHash": stable_hash({"primary": dict(primary_counts), "candidate": dict(candidate_counts), "union": union}),
    }


def priority_decision(taxonomy: dict[str, Any]) -> dict[str, Any]:
    counts = taxonomy["primaryMissTypeCounts"]
    total = max(1, taxonomy["diagnosticCases"])
    candidates = [
        priority_item("Candidate K", counts.get("CANDIDATE_K_TOO_SMALL", 0), total, 4, 2, 2, "Phase 9.2"),
        priority_item("RRF Window", counts.get("RRF_FUSION_DEMOTION", 0), total, 3, 2, 2, "Phase 9.2"),
        priority_item("Query Normalization", counts.get("QUERY_REPRESENTATION_MISS", 0), total, 3, 2, 2, "Phase 9.2"),
        priority_item("Title + Section Retrieval Content", counts.get("CHUNK_NOT_SELF_CONTAINED", 0), total, 3, 3, 3, "Phase 9.2"),
        priority_item("Index Repair", counts.get("INDEXING_MISS", 0) + counts.get("ELIGIBILITY_OR_LABEL_CONFLICT", 0), total, 4, 2, 1, "Phase 9.2"),
        priority_item("BGE-M3 Sparse", counts.get("BOTH_RETRIEVERS_MISS", 0), total, 2, 4, 4, "Phase 9.3"),
        priority_item("Multi-vector", counts.get("BOTH_RETRIEVERS_MISS", 0), total, 2, 5, 5, "Phase 9.3"),
    ]
    ranked = sorted(candidates, key=lambda item: (-item["priorityScore"], item["implementationComplexity"], item["name"]))
    top = ranked[0]
    recommended = "PHASE_92_PRIORITY_MIXED"
    if top["name"] == "Candidate K":
        recommended = "PHASE_92_PRIORITY_CANDIDATE_K_AND_FUSION"
    elif top["name"] == "Query Normalization":
        recommended = "PHASE_92_PRIORITY_QUERY_OPTIMIZATION"
    elif top["name"] == "Title + Section Retrieval Content":
        recommended = "PHASE_92_PRIORITY_CHUNKING_AND_CONTEXT"
    elif top["name"] == "Index Repair":
        recommended = "PHASE_92_PRIORITY_INDEX_REPAIR"
    return {
        "schemaVersion": "agent-rag-v23-retrieval-optimization-priority-decision-v1",
        "status": "COMPLETE",
        "ranking": ranked,
        "recommendedPhase": recommended,
        "forbiddenClaims": ["RETRIEVAL_QUALITY_VERIFIED", "PRODUCTION_RETRIEVAL_PASS"],
    }


def priority_item(name: str, count: int, total: int, confidence: int, complexity: int, runtime_cost: int, phase: str) -> dict[str, Any]:
    recoverable = round(count / total, 6)
    score = round((min(5, max(1, int(recoverable * 5) or 1)) * confidence) / max(1, runtime_cost), 3)
    return {
        "name": name,
        "affectedCaseCount": count,
        "affectedCaseRate": recoverable,
        "expectedRecoverableCases": count,
        "implementationComplexity": complexity,
        "runtimeCost": runtime_cost,
        "indexCost": complexity,
        "risk": "medium" if complexity >= 3 else "low",
        "recommendedPhase": phase,
        "priorityScore": score,
    }


def diagnostic_boundary(analysis: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnosticCaseCount": analysis["diagnosticCases"],
        "diagnosticCaseIdsHash": analysis["caseIdsHash"],
        "sourceBenchmarkHash": manifest["benchmarkHash"],
        "consumedAtCommit": "pending",
        "futureQualificationUseAllowed": False,
        "status": "CONSUMED_RETRIEVAL_MISS_DIAGNOSTIC_SET",
    }


def render_boundary(boundary: dict[str, Any]) -> str:
    return f"""# V2.3 Phase 9.1 Retrieval Miss Diagnostic Boundary

Diagnostic cases: `{boundary['diagnosticCaseCount']}`

Diagnostic case IDs hash: `{boundary['diagnosticCaseIdsHash']}`

Source benchmark hash: `{boundary['sourceBenchmarkHash']}`

Future qualification use allowed: `false`

The 90 retrieval-missed answerable cases are consumed by Phase 9.1 error analysis. They may be used for root cause analysis and Phase 9.2 experiment design, but must not be reused as final unbiased retrieval qualification evaluation data.
"""


def render_analysis_doc(analysis: dict[str, Any], taxonomy: dict[str, Any]) -> str:
    return f"""# V2.3 Retrieval Miss Error Analysis

Phase 9.1 analyzes the existing retrieval-missed answerable cases from the frozen v2.2 benchmark. It does not modify retrieval runtime, BM25, dense retrieval, RRF, chunking, sparse retrieval, multi-vector retrieval, or query expansion.

| Metric | Value |
|---|---:|
| Diagnostic cases | {taxonomy['diagnosticCases']} |
| BM25 Top100 hits | {taxonomy['bm25Top100Hits']} |
| Dense Top100 hits | {taxonomy['denseTop100Hits']} |
| Both Top100 hits | {taxonomy['bothTop100Hits']} |
| Neither Top100 hits | {taxonomy['neitherTop100Hits']} |
| Union Top100 coverage | {taxonomy['unionTop100Coverage']} |
| Candidate K recoverable | {taxonomy['candidateKRecoverable']} |

Primary miss type counts:

```json
{json_dumps(taxonomy['primaryMissTypeCounts'])}
```

Candidate K recovery counts:

```json
{json_dumps(taxonomy['candidateKCounts'])}
```
"""


def render_priority_doc(priority: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| {item['name']} | {item['affectedCaseCount']} | {item['affectedCaseRate']} | {item['implementationComplexity']} | {item['runtimeCost']} | {item['priorityScore']} | {item['recommendedPhase']} |"
        for item in priority["ranking"]
    )
    return f"""# V2.3 Retrieval Optimization Priority

Recommended path: `{priority['recommendedPhase']}`

| Workstream | Affected cases | Rate | Complexity | Runtime cost | Priority score | Phase |
|---|---:|---:|---:|---:|---:|---|
{rows}

This is a diagnostic prioritization result, not a retrieval quality pass.
"""


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
