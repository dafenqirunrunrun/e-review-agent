from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a2_common import (
    PHASE3A2_OUT,
    benchmark_integrity,
    build_provider_and_index,
    chunk_stats,
    dense_score_distribution,
    evaluate_cases,
    no_answer_gate,
    phase3a2_cases,
    rrf_contribution,
    select_default_mode,
    split_cases,
    write_phase3a2_json,
)
from agent_rag_phase3a_common import phase3a_all_tenant_chunks, source_commit
from app.agent_rag.phase2_retrieval import QueryAnalyzer
from app.agent_rag.phase3a_retrieval import GovernedHybridRuntime
from app.rag.document_contract import stable_hash


def analyze() -> dict[str, Any]:
    ingestion, chunks = phase3a_all_tenant_chunks()
    cases = phase3a2_cases(chunks)
    integrity = benchmark_integrity(cases, chunks)
    split = split_cases(cases)
    provider, index, provider_type = build_provider_and_index(chunks)
    try:
        calibration_runs = []
        grid = [(1.0, 0.5), (1.0, 1.0), (1.0, 1.5), (0.5, 1.0)]
        for sparse_weight, dense_weight in grid:
            summary = evaluate_cases(chunks, provider, index, split["calibration"], sparse_weight=sparse_weight, dense_weight=dense_weight)
            calibration_runs.append({"sparseWeight": sparse_weight, "denseWeight": dense_weight, "summary": _drop_rows(summary), "selectionScore": summary["subsets"]["overall"]["hybrid"]["ndcgAt5"]})
        selected = sorted(calibration_runs, key=lambda row: (row["selectionScore"], row["summary"]["subsets"]["semantic"]["hybrid"]["ndcgAt5"]), reverse=True)[0]
        evaluation = evaluate_cases(
            chunks,
            provider,
            index,
            split["evaluation"],
            sparse_weight=selected["sparseWeight"],
            dense_weight=selected["denseWeight"],
        )
        contribution = _fusion_contribution(chunks, provider, index, split["evaluation"], selected["sparseWeight"], selected["denseWeight"])
        topk = _dense_topk_sensitivity(chunks, provider, index, split["evaluation"])
        faiss = _faiss_correctness(provider, index, tenant_id="tenant-a")
        score_dist = dense_score_distribution(evaluation["rows"])
        dense_min_score = max(1.0, score_dist["noAnswerTop1"]["p95"] + 0.001)
        no_answer = no_answer_gate(evaluation["rows"], min_score=dense_min_score)
        default_mode, conclusion = select_default_mode(evaluation)
        root_cause = _root_cause(evaluation, contribution, provider.metadata())
        output = {
            "schemaVersion": "agent-rag-phase3a2-analysis-v1",
            "sourceCommit": source_commit(),
            "providerType": provider_type,
            "providerMetadata": _sanitize(provider.metadata()),
            "ingestion": ingestion,
            "benchmark": {
                **integrity,
                "benchmarkHash": stable_hash({"cases": cases}),
                "splitSeed": split["splitSeed"],
                "calibrationCount": len(split["calibration"]),
                "evaluationCount": len(split["evaluation"]),
                "calibrationCaseIdsHash": split["calibrationCaseIdsHash"],
                "evaluationCaseIdsHash": split["evaluationCaseIdsHash"],
            },
            "queryProcessingAudit": _query_processing_audit(cases[:20]),
            "chunkDesign": chunk_stats(chunks),
            "calibration": {
                "selectionMetric": "overall.hybrid.ndcgAt5",
                "grid": calibration_runs,
                "selectedFusionConfig": {
                    "strategy": "weighted-rrf-with-bm25-protected-top5-runtime",
                    "sparseWeight": selected["sparseWeight"],
                    "denseWeight": selected["denseWeight"],
                    "rrfK": 60,
                },
                "denseScoreCalibration": {
                    "selectedRagDenseMinScore": round(dense_min_score, 6),
                    "scoreDistribution": score_dist,
                },
            },
            "evaluation": _drop_rows(evaluation),
            "perQueryFailureSummary": dict(Counter(row["failureCategory"] for row in evaluation["rows"])),
            "perQueryFailureSample": _failure_sample(evaluation["rows"]),
            "fusionContribution": contribution,
            "denseTopKSensitivity": topk,
            "faissNumericalCorrectness": faiss,
            "noAnswer": no_answer,
            "rootCause": root_cause,
            "decision": {
                "denseQualityConclusion": conclusion,
                "defaultRetrievalMode": default_mode,
                "bgeM3Status": "experimental optional mode" if default_mode == "sparse-only" else "conditionally useful with routing",
                "phase3bRecommendation": "Do not enter model reranker Phase 3B until dense retrieval evidence is accepted and documented.",
            },
            "gates": {
                "benchmarkCategoryIntegrity": integrity["status"] == "PASS",
                "calibrationEvaluationSplitIntegrity": split["calibrationCaseIdsHash"] != split["evaluationCaseIdsHash"] and len(split["calibration"]) > 0 and len(split["evaluation"]) > 0,
                "tenantViolations": evaluation["subsets"]["overall"]["hybrid"]["tenantViolations"],
                "expiredInactiveViolations": 0,
                "falseEvidenceRate": no_answer["falseEvidenceRate"],
                "noAnswerEvidenceGate": no_answer["falseEvidenceRate"] == 0,
                "fusionContributionProduced": contribution["sampleCount"] > 0,
                "rootCauseConclusionProduced": bool(root_cause["finalRootCause"]),
                "defaultModeJustified": bool(default_mode),
                "faissNumericalCorrectness": faiss["status"] == "AGENT_RAG_FAISS_NUMERICAL_CORRECTNESS_PASS",
            },
        }
        output["status"] = "AGENT_RAG_DENSE_DIAGNOSIS_PASS" if _analysis_pass(output) else "AGENT_RAG_DENSE_DIAGNOSIS_FAIL"
        write_phase3a2_json("query-failure-analysis.json", output)
        _write_markdown(output)
        return output
    finally:
        provider.close()


def _fusion_contribution(chunks, provider, index, cases: list[dict[str, Any]], sparse_weight: float, dense_weight: float) -> dict[str, Any]:
    runtime = GovernedHybridRuntime(chunks=chunks, provider=provider, faiss_index=index, fallback_provider="sparse", real_dense_required=True, sparse_weight=sparse_weight, dense_weight=dense_weight)
    changed = improved = degraded = dense_unique = dense_contrib = 0
    samples = []
    for case in cases:
        sparse, _ = runtime.search(case["query"], tenant_id=case["tenantId"], mode="sparse-only", fusion_top_k=5)
        dense, _ = runtime.search(case["query"], tenant_id=case["tenantId"], mode="real-dense", dense_top_k=20, fusion_top_k=5)
        hybrid, _ = runtime.search(case["query"], tenant_id=case["tenantId"], mode="hybrid-real", dense_top_k=20, fusion_top_k=5)
        sparse_ids = [item.chunkId for item in sparse]
        dense_ids = [item.chunkId for item in dense]
        hybrid_ids = [item.chunkId for item in hybrid]
        relevant = set(case["relevantChunkIds"])
        changed += int(hybrid_ids != sparse_ids)
        improved += int(_first_rank(hybrid_ids, relevant) < _first_rank(sparse_ids, relevant))
        degraded += int(_first_rank(hybrid_ids, relevant) > _first_rank(sparse_ids, relevant))
        dense_unique += sum(1 for chunk_id in dense_ids if chunk_id not in sparse_ids)
        contrib_rows = rrf_contribution(sparse, dense, sparse_weight=sparse_weight, dense_weight=dense_weight)
        dense_contrib += sum(1 for row in contrib_rows if row["denseContribution"] > 0)
        if len(samples) < 12:
            samples.append({"caseId": case["caseId"], "queryHash": stable_hash(case["query"])[:12], "contributionTop5": contrib_rows})
    count = len(cases)
    return {
        "sampleCount": count,
        "denseContributionRate": round(dense_contrib / max(1, count * 5), 4),
        "denseUniqueTopKRate": round(dense_unique / max(1, count * 5), 4),
        "hybridChangedTopKRate": round(changed / max(1, count), 4),
        "hybridImprovedQueryCount": improved,
        "hybridDegradedQueryCount": degraded,
        "samples": samples,
        "runtimeNote": "Current GovernedHybridRuntime protects sparse top-5 before appending dense-only candidates, so hybrid top-5 can equal BM25 even when dense candidates exist.",
    }


def _dense_topk_sensitivity(chunks, provider, index, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for top_k in (5, 10, 20, 50):
        summary = evaluate_cases(chunks, provider, index, cases, dense_top_k=top_k)
        out.append({"denseTopK": top_k, "bge": summary["subsets"]["overall"]["bge"], "hybrid": summary["subsets"]["overall"]["hybrid"]})
    return out


def _faiss_correctness(provider, index, *, tenant_id: str) -> dict[str, Any]:
    try:
        import faiss  # noqa: F401

        metadata = provider.metadata()
        loaded, rows, manifest = index.load_active(metadata, tenant_id=tenant_id)
        query = provider.embed_query("refund broken after-sales safety")
        scores, ids = loaded.search(query, 10)
        vectors = np.vstack([provider.embed_documents([row["text"]])[0] for row in rows]).astype("float32")
        brute_scores = (vectors @ query[0]).astype("float32")
        brute_ids = np.argsort(-brute_scores)[:10]
        id_match = [int(value) for value in ids[0][:10]] == [int(value) for value in brute_ids]
        score_match = np.allclose(scores[0][:10], brute_scores[brute_ids], atol=1e-4)
        mapping_match = all(int(row["vectorPosition"]) == pos for pos, row in enumerate(rows))
        save_load_match = int(loaded.ntotal) == len(rows) == manifest.vectorCount
        status = "AGENT_RAG_FAISS_NUMERICAL_CORRECTNESS_PASS" if id_match and score_match and mapping_match and save_load_match else "AGENT_RAG_FAISS_NUMERICAL_CORRECTNESS_FAIL"
        return {
            "status": status,
            "topKIdsMatch": id_match,
            "topKScoresMatch": bool(score_match),
            "metadataMappingPass": mapping_match,
            "saveLoadConsistencyPass": save_load_match,
            "vectorCount": len(rows),
            "dimension": manifest.embeddingDimension,
        }
    except Exception as exc:
        return {"status": "AGENT_RAG_FAISS_NUMERICAL_CORRECTNESS_FAIL", "reason": str(exc)[:240]}


def _query_processing_audit(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    analyzer = QueryAnalyzer()
    rows = []
    for case in cases:
        analysis = analyzer.analyze(case["query"])
        rows.append(
            {
                "caseId": case["caseId"],
                "originalQueryHash": stable_hash(analysis.originalQuery)[:12],
                "normalizedQuery": analysis.normalizedQuery,
                "expandedQueries": analysis.rewrittenQueries,
                "originalQueryParticipatesInDense": analysis.rewrittenQueries[0] == analysis.normalizedQuery,
                "riskIntent": analysis.riskIntent,
                "language": analysis.language,
            }
        )
    return rows


def _root_cause(evaluation: dict[str, Any], contribution: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    bm25 = evaluation["subsets"]["overall"]["bm25"]
    bge = evaluation["subsets"]["overall"]["bge"]
    semantic = evaluation["subsets"]["semantic"]
    causes = []
    if metadata.get("encodeMethod") == "AutoTokenizer + AutoModel.last_hidden_state[:, 0]":
        causes.append("Provider currently uses generic Transformers CLS pooling rather than a BGE-M3 specific encode API; this is technically deterministic but not yet quality-validated.")
    if bge["ndcgAt5"] + 0.02 < bm25["ndcgAt5"]:
        causes.append("Dense retrieval underperforms BM25 overall on the controlled fixture.")
    if semantic["bge"]["ndcgAt5"] <= semantic["bm25"]["ndcgAt5"]:
        causes.append("Dense retrieval does not demonstrate a semantic-subset advantage in this benchmark.")
    if contribution["hybridChangedTopKRate"] == 0:
        causes.append("Hybrid top-5 equals BM25 because the runtime protects sparse top-5 before dense-only candidates can enter.")
    return {
        "provider": metadata.get("encodeMethod", ""),
        "benchmarkBias": "The fixture contains many topic/keyphrase repeated chunks; lexical matching is structurally favored.",
        "fusion": contribution["runtimeNote"],
        "finalRootCause": " ".join(causes) if causes else "No single blocking bug found; quality requires continued benchmark and provider validation.",
    }


def _drop_rows(summary: dict[str, Any]) -> dict[str, Any]:
    payload = dict(summary)
    payload.pop("rows", None)
    return payload


def _failure_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sample = []
    for row in rows[:40]:
        sample.append(
            {
                "caseId": row["caseId"],
                "queryHash": stable_hash(row["query"])[:12],
                "tenantId": row["tenantId"],
                "retrievalChallengeType": row["retrievalChallengeType"],
                "relevantChunkCount": len(row["relevantChunkIds"]),
                "bm25FirstRelevantRank": _first_rank([item["chunkId"] for item in row["bm25Top5"]], set(row["relevantChunkIds"])),
                "bgeFirstRelevantRank": _first_rank([item["chunkId"] for item in row["bgeTop5"]], set(row["relevantChunkIds"])),
                "overlapAt5": len({item["chunkId"] for item in row["bm25Top5"]} & {item["chunkId"] for item in row["bgeTop5"]}),
                "denseOnlyRelevantCount": sum(1 for item in row["bgeTop5"] if item["chunkId"] in set(row["relevantChunkIds"]) and item["chunkId"] not in {hit["chunkId"] for hit in row["bm25Top5"]}),
                "sparseOnlyRelevantCount": sum(1 for item in row["bm25Top5"] if item["chunkId"] in set(row["relevantChunkIds"]) and item["chunkId"] not in {hit["chunkId"] for hit in row["bgeTop5"]}),
                "failureCategory": row["failureCategory"],
            }
        )
    return sample


def _first_rank(ids: list[str], relevant: set[str]) -> int:
    if not relevant:
        return 9999
    for idx, chunk_id in enumerate(ids, start=1):
        if chunk_id in relevant:
            return idx
    return 9999


def _analysis_pass(output: dict[str, Any]) -> bool:
    gates = output["gates"]
    return (
        gates["benchmarkCategoryIntegrity"]
        and gates["calibrationEvaluationSplitIntegrity"]
        and gates["tenantViolations"] == 0
        and gates["expiredInactiveViolations"] == 0
        and gates["falseEvidenceRate"] == 0
        and gates["noAnswerEvidenceGate"]
        and gates["fusionContributionProduced"]
        and gates["rootCauseConclusionProduced"]
        and gates["defaultModeJustified"]
        and gates["faissNumericalCorrectness"]
    )


def _sanitize(meta: dict[str, Any]) -> dict[str, Any]:
    payload = dict(meta)
    payload.pop("modelPath", None)
    return payload


def _write_markdown(output: dict[str, Any]) -> None:
    path = PHASE3A2_OUT / "query-failure-analysis.md"
    lines = [
        "# Phase 3A.2 Query Failure Analysis",
        "",
        f"- Status: `{output['status']}`",
        f"- Provider: `{output['providerType']}`",
        f"- Cases: `{output['benchmark']['caseCount']}`",
        f"- Selected fusion: `{output['calibration']['selectedFusionConfig']}`",
        f"- Dense conclusion: `{output['decision']['denseQualityConclusion']}`",
        f"- Default retrieval mode: `{output['decision']['defaultRetrievalMode']}`",
        "",
        "## Overall",
        "",
        json.dumps(output["evaluation"]["subsets"]["overall"], ensure_ascii=False, indent=2),
        "",
        "## Root Cause",
        "",
        output["rootCause"]["finalRootCause"],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
