from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.evidence_coverage import PolicyEvidenceCoverageSelector
from app.policy_rag.embedding import QwenOfficialTransformersEmbeddingProvider
from app.policy_rag.evidence_semantics import evidence_supports_risk, governed_risk_types
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.models import PolicySearchResult
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.rag_quality.evaluator import evaluate_retrieval_run
from app.rag_quality.models import RagQualityCase
from scripts.build_step242a_rag_quality_v2 import load_jsonl
from scripts.run_step233a_qwen_embedding_ab import current_config, release_provider
from scripts.run_step233b_ranking_recovery import (
    candidate_embedding_config,
    dense_rankings,
    load_reranker,
    release_reranker,
    rerank_variants,
    weighted_rrf,
)
from scripts.run_step242d_frozen_holdout import B2_PROTOCOL, build_run_rows, read_json, utc_now, write_json_atomic


DATASET = ROOT / "data" / "benchmarks" / "rag_quality_v2" / "dev_frozen_llm_v1.jsonl"
CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
VECTOR_INDEX_DIR = ROOT / "artifacts" / "step233a" / "qwen_official_v2"
RERANKER = ROOT.parents[1] / "models" / "v2.2" / "bge-reranker-v2-m3"
DEFAULT_OUTPUT = ROOT / "artifacts" / "step242e" / "dev_coverage_selector_result.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate B2.1 evidence coverage selection on the exposed Dev split only.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--embedding-batch-size", type=int, default=8)
    parser.add_argument("--reranker-batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.embedding_batch_size < 1 or args.reranker_batch_size < 1:
        raise SystemExit("STEP242E_BATCH_SIZE_INVALID")

    cases = [RagQualityCase.model_validate(item) for item in load_jsonl(DATASET)]
    if not cases or any(case.split != "dev" for case in cases):
        raise SystemExit("STEP242E_DEV_DATASET_REQUIRED")

    started = time.perf_counter()
    risk_cases = [case for case in cases if case.riskTypes]
    chunks = load_policy_chunks(CHUNKS)
    index_meta = read_json(VECTOR_INDEX_DIR / "policy_vectors_meta.json")
    retriever = PolicyEvidenceRetriever(chunks)
    selector = PolicyEvidenceCoverageSelector()
    queries = [
        " ".join([case.reviewText, PolicyEvidenceRetriever._expand_risk_hints(case.riskTypes)]).strip()
        for case in risk_cases
    ]

    bm25_started = time.perf_counter()
    bm25_rankings = [
        retriever._bm25_search(query, case.riskTypes, top_k=20)
        for query, case in zip(queries, risk_cases, strict=True)
    ]
    bm25_ms = _elapsed(bm25_started)

    provider = QwenOfficialTransformersEmbeddingProvider(candidate_embedding_config(current_config(batch_size=args.embedding_batch_size), index_meta))
    dense_ranked, embedding_ms = dense_rankings(provider, VECTOR_INDEX_DIR, chunks, queries)
    provider_metadata = provider.metadata()
    release_provider(provider)

    fusion_started = time.perf_counter()
    rrf20 = [
        weighted_rrf(bm25, dense, top_k=20, k=60, bm25_weight=1.0, dense_weight=1.0)
        for bm25, dense in zip(bm25_rankings, dense_ranked, strict=True)
    ]
    baseline_candidates = [ranking[:5] for ranking in rrf20]
    coverage_candidates: list[list[tuple[float, Any]]] = []
    preselection_rows: list[dict[str, object]] = []
    for case, ranking in zip(risk_cases, rrf20, strict=True):
        results = _as_results(retriever, ranking, mode="hybrid_bm25_qwen_faiss_rrf")
        selection = selector.select(results, case.riskTypes, limit=5)
        scores_by_id = {chunk.chunkId: score for score, chunk in ranking}
        chunks_by_id = {chunk.chunkId: chunk for _, chunk in ranking}
        coverage_candidates.append(
            [(scores_by_id[item.chunkId], chunks_by_id[item.chunkId]) for item in selection.evidence]
        )
        preselection_rows.append({"caseId": case.caseId, **selection.metadata})
    fusion_ms = _elapsed(fusion_started)

    reranker, reranker_metadata = load_reranker(RERANKER)
    baseline_reranked, coverage_reranked, reranker_ms, pair_count = rerank_variants(
        reranker,
        queries,
        baseline_candidates,
        coverage_candidates,
        batch_size=args.reranker_batch_size,
    )
    release_reranker(reranker)

    final_rankings: list[list[tuple[float, Any]]] = []
    postselection_rows: list[dict[str, object]] = []
    for case, ranking in zip(risk_cases, coverage_reranked, strict=True):
        results = _as_results(retriever, ranking, mode="hybrid_bge_reranked")
        selection = selector.select(results, case.riskTypes, limit=5)
        scores_by_id = {chunk.chunkId: score for score, chunk in ranking}
        chunks_by_id = {chunk.chunkId: chunk for _, chunk in ranking}
        final_rankings.append(
            [(scores_by_id[item.chunkId], chunks_by_id[item.chunkId]) for item in selection.evidence]
        )
        postselection_rows.append({"caseId": case.caseId, **selection.metadata})

    baseline_evaluation = evaluate_retrieval_run(cases, build_run_rows(cases, risk_cases, baseline_reranked), run_name="B2_dev_replay")
    coverage_evaluation = evaluate_retrieval_run(cases, build_run_rows(cases, risk_cases, final_rankings), run_name="B2.1_dev_coverage_selector")
    report = {
        "schemaVersion": "step24.2e-dev-coverage-selector-v1",
        "executedAt": utc_now(),
        "split": "dev",
        "holdoutConsulted": False,
        "holdoutExecuted": False,
        "purpose": "Diagnostic validation only. This exposed Dev result cannot promote a candidate.",
        "config": {
            "retrievalPoolK": 20,
            "rerankCandidateK": 5,
            "reflectionEvidenceLimit": 5,
            "frontendCitationLimit": 3,
            "embedding": provider_metadata,
            "reranker": reranker_metadata,
        },
        "baselineB2": baseline_evaluation,
        "coverageB21": coverage_evaluation,
        "comparison": _comparison(baseline_evaluation["metrics"], coverage_evaluation["metrics"]),
        "runtimePolicyCoverage": {
            "baselineB2": _runtime_policy_coverage(retriever, risk_cases, baseline_reranked),
            "coverageB21": _runtime_policy_coverage(retriever, risk_cases, final_rankings),
            "note": "This mirrors the Reflection tag contract. It is intentionally reported beside, not substituted for, frozen qrels riskCoverageAt3.",
        },
        "selection": {
            "preRerank": preselection_rows,
            "postRerank": postselection_rows,
            "preRerankCoverageChangedCaseCount": sum(bool(row["coverageApplied"]) for row in preselection_rows),
            "postRerankCoverageChangedCaseCount": sum(bool(row["coverageApplied"]) for row in postselection_rows),
            "uncoveredRiskOccurrencesAfterRerank": sum(len(row["uncoveredRiskTypes"]) for row in postselection_rows),
        },
        "runtime": {
            "bm25Ms": bm25_ms,
            "queryEmbeddingBatchMs": embedding_ms,
            "rrfAndSelectionMs": fusion_ms,
            "rerankerMs": reranker_ms,
            "rerankerPairCount": pair_count,
            "totalMs": _elapsed(started),
        },
    }
    write_json_atomic(args.output, report)
    print(json.dumps(_summary(report), ensure_ascii=False, indent=2))
    return 0


def _as_results(
    retriever: PolicyEvidenceRetriever,
    ranking: list[tuple[float, Any]],
    *,
    mode: str,
) -> list[PolicySearchResult]:
    return [
        retriever._to_result(chunk, score, rank=index, mode=mode)
        for index, (score, chunk) in enumerate(ranking, start=1)
    ]


def _comparison(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    metrics = (
        "candidateEvidenceHitRateAt5",
        "relevantChunkRecallAt5",
        "mrrAt5",
        "pooledNdcgAt3",
        "pooledNdcgAt5",
        "riskCoverageAt3",
        "highRiskEvidenceHitRateAt5",
        "citationValidCaseRate",
    )
    return {name: round(float(candidate[name]) - float(baseline[name]), 6) for name in metrics}


def _runtime_policy_coverage(
    retriever: PolicyEvidenceRetriever,
    cases: list[RagQualityCase],
    rankings: list[list[tuple[float, Any]]],
) -> dict[str, object]:
    rows = []
    for case, ranking in zip(cases, rankings, strict=True):
        requested = governed_risk_types(case.riskTypes)
        if not requested:
            continue
        results = _as_results(retriever, ranking, mode="hybrid_bge_reranked")
        for top_k in (3, 5):
            supported = [risk for risk in requested if any(evidence_supports_risk(risk, item) for item in results[:top_k])]
            rows.append(
                {
                    "caseId": case.caseId,
                    "topK": top_k,
                    "requestedRiskTypes": requested,
                    "supportedRiskTypes": supported,
                    "complete": set(requested).issubset(supported),
                }
            )
    summary = {}
    for top_k in (3, 5):
        scoped = [row for row in rows if row["topK"] == top_k]
        summary[f"completeCoverageRateAt{top_k}"] = round(sum(bool(row["complete"]) for row in scoped) / len(scoped), 6) if scoped else 1.0
        summary[f"uncoveredRiskOccurrencesAt{top_k}"] = sum(
            len(set(row["requestedRiskTypes"]) - set(row["supportedRiskTypes"]))
            for row in scoped
        )
    summary["caseCount"] = len({row["caseId"] for row in rows})
    return summary


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "split": report["split"],
        "holdoutConsulted": report["holdoutConsulted"],
        "baselineMetrics": report["baselineB2"]["metrics"],
        "coverageMetrics": report["coverageB21"]["metrics"],
        "delta": report["comparison"],
        "runtimePolicyCoverage": report["runtimePolicyCoverage"],
        "selection": {
            "preRerankCoverageChangedCaseCount": report["selection"]["preRerankCoverageChangedCaseCount"],
            "postRerankCoverageChangedCaseCount": report["selection"]["postRerankCoverageChangedCaseCount"],
            "uncoveredRiskOccurrencesAfterRerank": report["selection"]["uncoveredRiskOccurrencesAfterRerank"],
        },
        "runtime": report["runtime"],
    }


def _elapsed(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


if __name__ == "__main__":
    raise SystemExit(main())
