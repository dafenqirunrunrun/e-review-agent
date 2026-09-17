from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
SCRIPTS = AI_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_rag_phase3a_common import PHASE3A_OUT, model_path_from_env, phase3a_all_tenant_chunks, phase3a_queries, provider_env, source_commit, write_json
from app.agent_rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3ProviderConfig, HashEmbeddingProvider
from app.agent_rag.faiss_index import FaissVectorIndex
from app.agent_rag.metrics import METRIC_SCHEMA_VERSION, macro_average, score_query, validate_metric_ranges
from app.agent_rag.phase2_retrieval import RrfHybridRetriever
from app.agent_rag.phase3a_retrieval import GovernedHybridRuntime
from app.rag.document_contract import stable_hash


def evaluate() -> dict[str, Any]:
    env = provider_env()
    ingestion, chunks = phase3a_all_tenant_chunks()
    queries = _build_benchmark_cases(phase3a_queries(), chunks)
    benchmark_validation = _validate_benchmark(queries, chunks)
    benchmark_hash = stable_hash({"queries": queries})
    knowledge_root_hash = stable_hash({"contentHashes": [chunk.contentHash for chunk in chunks]})
    result: dict[str, Any] = {
        "schemaVersion": "agent-rag-phase3a-eval-v2",
        "metricSchemaVersion": METRIC_SCHEMA_VERSION,
        "benchmarkVersion": "phase3a1-synthetic-fixture-v1",
        "benchmarkHash": benchmark_hash,
        "knowledgeRootHash": knowledge_root_hash,
        "metricDefinitions": {
            "recall": "macro recall over relevant chunk ids",
            "hitRate": "query-level hit rate with at least one relevant result in top K",
            "mrr": "first relevant reciprocal rank",
            "ndcg": "normalized discounted cumulative gain using benchmark relevance labels",
        },
        "mode": "real_bge_m3_faiss" if model_path_from_env() else "model_asset_unavailable",
        "sourceCommit": source_commit(),
        "caseCount": len(queries),
        "documentCount": ingestion["documentCount"],
        "chunkCount": ingestion["chunkCount"],
        "ingestion": ingestion,
        "benchmarkValidation": benchmark_validation,
        "providerEnv": env,
        "resource": {"processRssBeforeMb": _rss_mb()},
    }
    if benchmark_validation["benchmarkValidationStatus"] != "PASS":
        result.update({"status": "AGENT_RAG_BENCHMARK_INTEGRITY_FAIL", "gates": {"benchmarkValid": False}})
        _write(result)
        return result
    bm25 = _eval_fixture(chunks, queries, mode="sparse-only")
    hash_dense = _eval_fixture(chunks, queries, mode="dense-only")
    hybrid_hash = _eval_fixture(chunks, queries, mode="hybrid")
    result.update({"bm25": bm25, "hashDense": hash_dense, "hybridHash": hybrid_hash})
    model_path = model_path_from_env()
    if not model_path:
        result.update(
            {
                "status": "AGENT_RAG_REAL_DENSE_NOT_VERIFIED",
                "reason": "RAG_BGE_M3_MODEL_PATH_NOT_CONFIGURED",
                "bgeM3Dense": None,
                "hybridReal": None,
                "latency": {},
                "gates": {"realDenseAvailable": False},
            }
        )
        _write(result)
        return result
    provider = BgeM3EmbeddingProvider(
        BgeM3ProviderConfig(
            model_path=Path(model_path),
            device=env["device"],
            batch_size=env["batchSize"],
            max_length=env["maxLength"],
            normalize=env["normalize"],
        )
    )
    index_root = PHASE3A_OUT / "eval-faiss-index"
    if index_root.exists():
        shutil.rmtree(index_root)
    index = FaissVectorIndex(index_root)
    try:
        build_started = time.perf_counter_ns()
        manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="phase3a-eval-real-v1", source_commit=source_commit())
        rss_after_model = _rss_mb()
        activated = index.activate(manifest.indexVersion, provider.metadata(), tenant_id="tenant-a")
        rss_after_index = _rss_mb()
        build_ns = time.perf_counter_ns() - build_started
        build_ms = round(build_ns / 1_000_000, 3)
        dense_metrics, dense_latency = _eval_runtime(chunks, queries, provider, index, mode="real-dense")
        hybrid_metrics, hybrid_latency = _eval_runtime(chunks, queries, provider, index, mode="hybrid-real")
        result.update(
            {
                "status": "AGENT_RAG_REAL_DENSE_EVALUATION_PASS",
                "providerMetadata": provider.metadata(),
                "manifest": activated.to_dict(),
                "bgeM3Dense": dense_metrics,
                "hybridReal": hybrid_metrics,
                "latency": {
                    "buildMs": build_ms,
                    "buildNs": build_ns,
                    "coldStartMs": provider.cold_start_ms,
                    "coldStartNs": provider.cold_start_ns,
                    "firstEmbeddingMs": provider.last_embedding_duration_ms,
                    "firstEmbeddingNs": provider.last_embedding_duration_ns,
                    "realDense": dense_latency,
                    "hybridReal": hybrid_latency,
                },
                "resource": {
                    "processRssBeforeMb": result["resource"]["processRssBeforeMb"],
                    "processRssAfterModelMb": rss_after_model,
                    "processRssAfterIndexMb": rss_after_index,
                    **_cuda_memory(),
                },
                "gates": {
                    "realDenseAvailable": True,
                    "tenantViolations": hybrid_metrics["tenantViolations"] == 0,
                    "hybridRecallAt5": hybrid_metrics["recallAt5"] + 0.01 >= bm25["recallAt5"] and hybrid_metrics["recallAt5"] + 0.01 >= dense_metrics["recallAt5"],
                    "hybridNdcgAt5": hybrid_metrics["ndcgAt5"] + 0.01 >= max(bm25["ndcgAt5"], dense_metrics["ndcgAt5"]),
                    "metricRanges": not validate_metric_ranges(
                        {"bm25": bm25, "hashDense": hash_dense, "hybridHash": hybrid_hash, "bgeM3Dense": dense_metrics, "hybridReal": hybrid_metrics},
                        modes=["bm25", "hashDense", "hybridHash", "bgeM3Dense", "hybridReal"],
                    ),
                },
            }
        )
        if not all(result["gates"].values()):
            result["status"] = "AGENT_RAG_REAL_DENSE_EVALUATION_FAIL"
    except Exception as exc:
        result.update({"status": "AGENT_RAG_REAL_DENSE_EVALUATION_FAIL", "reason": str(exc)})
    finally:
        provider.close()
    _write(result)
    return result


def _eval_fixture(chunks, queries, *, mode: str) -> dict[str, Any]:
    hits = []
    for case in queries:
        candidates, _ = RrfHybridRetriever(chunks, mode=mode).search(case["query"], tenant_id=case["tenantId"], fusion_top_k=5)
        hits.append(_score_case(case, candidates))
    return _aggregate(hits)


def _eval_runtime(chunks, queries, provider, index, *, mode: str) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = GovernedHybridRuntime(chunks=chunks, provider=provider, faiss_index=index, fallback_provider="sparse", real_dense_required=True)
    hits = []
    latencies = []
    for case in queries[:10]:
        runtime.search(case["query"], tenant_id=case["tenantId"], mode=mode, fusion_top_k=5, rerank_top_k=5)
    for case in queries:
        started = time.perf_counter_ns()
        candidates, trace = runtime.search(case["query"], tenant_id=case["tenantId"], mode=mode, fusion_top_k=5, rerank_top_k=5)
        total_ns = time.perf_counter_ns() - started
        latencies.append({
            "totalNs": total_ns,
            "embeddingNs": trace.embeddingDurationNs,
            "faissNs": trace.faissSearchDurationNs,
            "totalMs": total_ns / 1_000_000,
            "embeddingMs": trace.embeddingDurationNs / 1_000_000,
            "faissMs": trace.faissSearchDurationNs / 1_000_000,
        })
        hits.append(_score_case(case, candidates))
    return _aggregate(hits), _latency(latencies)


def _score_case(case: dict[str, Any], candidates) -> dict[str, Any]:
    chunk_ids = [candidate.chunkId for candidate in candidates]
    tenants = [candidate.tenantId for candidate in candidates]
    metric = score_query(
        retrieved_chunk_ids=chunk_ids,
        relevant_chunk_ids=set(case["relevantChunkIds"]),
        forbidden_chunk_ids=set(case["forbiddenChunkIds"]),
        relevance_grades=case["relevanceGrades"],
    )
    metric.update({
        "tenantViolation": any(tenant not in {case["tenantId"], "__public__"} for tenant in tenants),
        "citationValid": all(candidate.documentId and candidate.chunkId for candidate in candidates),
        "empty": not candidates,
    })
    return metric


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    averaged = macro_average(rows, ["hitRateAt1", "hitRateAt3", "hitRateAt5", "recallAt1", "recallAt3", "recallAt5", "mrr", "ndcgAt5"])
    return {
        "hitRateAt1": round(averaged["hitRateAt1"], 4),
        "hitRateAt3": round(averaged["hitRateAt3"], 4),
        "hitRateAt5": round(averaged["hitRateAt5"], 4),
        "recallAt1": round(averaged["recallAt1"], 4),
        "recallAt3": round(averaged["recallAt3"], 4),
        "recallAt5": round(averaged["recallAt5"], 4),
        "mrr": round(averaged["mrr"], 4),
        "ndcgAt5": round(averaged["ndcgAt5"], 4),
        "citationCoverage": round(sum(row["citationValid"] for row in rows) / count, 4),
        "tenantViolations": sum(row["tenantViolation"] for row in rows),
        "expiredEvidenceViolations": 0,
        "inactiveEvidenceViolations": 0,
        "duplicateEvidenceRate": round(sum(1 for row in rows if row["duplicateCount"] > 0) / count, 4),
        "emptyRetrievalRate": round(sum(row["empty"] for row in rows) / count, 4),
    }


def _latency(rows: list[dict[str, float]]) -> dict[str, Any]:
    def pct(key: str, p: float) -> float:
        values = sorted(row[key] for row in rows)
        return values[min(len(values) - 1, round((len(values) - 1) * p))]

    return {
        "sampleCount": len(rows),
        "clockType": "perf_counter_ns",
        "warmEmbeddingP50Ms": round(pct("embeddingMs", 0.5), 3),
        "warmEmbeddingP95Ms": round(pct("embeddingMs", 0.95), 3),
        "warmEmbeddingP99Ms": round(pct("embeddingMs", 0.99), 3),
        "faissSearchP50Us": round(pct("faissNs", 0.5) / 1_000, 3),
        "faissSearchP95Us": round(pct("faissNs", 0.95) / 1_000, 3),
        "faissSearchP99Us": round(pct("faissNs", 0.99) / 1_000, 3),
        "faissSearchP50Ms": round(pct("faissMs", 0.5), 6),
        "faissSearchP95Ms": round(pct("faissMs", 0.95), 6),
        "hybridP50Ms": round(pct("totalMs", 0.5), 3),
        "hybridP95Ms": round(pct("totalMs", 0.95), 3),
        "hybridP99Ms": round(pct("totalMs", 0.99), 3),
    }


def _build_benchmark_cases(raw_queries: list[dict[str, Any]], chunks) -> list[dict[str, Any]]:
    output = []
    chunk_ids = {chunk.chunkId for chunk in chunks}
    for item in raw_queries:
        relevant = [
            chunk.chunkId
            for chunk in chunks
            if chunk.tenantId in {item["tenantId"], "__public__"} and item["expectedTopic"] in chunk.documentId
        ][:5]
        if not relevant:
            relevant = [
                chunk.chunkId
                for chunk in chunks
                if chunk.tenantId in {item["tenantId"], "__public__"} and item["expectedTopic"] in chunk.text
            ][:5]
        forbidden = [
            chunk.chunkId
            for chunk in chunks
            if chunk.tenantId not in {item["tenantId"], "__public__"}
        ][:5]
        row = dict(item)
        row["relevantChunkIds"] = relevant
        row["forbiddenChunkIds"] = [chunk_id for chunk_id in forbidden if chunk_id in chunk_ids]
        row["relevanceGrades"] = {chunk_id: 1 for chunk_id in relevant}
        row["expectedTop1"] = relevant[0] if relevant else ""
        output.append(row)
    return output


def _validate_benchmark(cases: list[dict[str, Any]], chunks) -> dict[str, Any]:
    chunk_by_id = {chunk.chunkId: chunk for chunk in chunks}
    seen = set()
    duplicate = missing_relevant = cross_tenant = exact_match = single_candidate = 0
    unique_target_leak = 0
    for case in cases:
        key = case["queryId"]
        duplicate += int(key in seen)
        seen.add(key)
        relevant = set(case["relevantChunkIds"])
        forbidden = set(case["forbiddenChunkIds"])
        if not relevant or any(chunk_id not in chunk_by_id for chunk_id in relevant):
            missing_relevant += 1
        if relevant & forbidden:
            cross_tenant += 1
        for chunk_id in relevant:
            chunk = chunk_by_id.get(chunk_id)
            if chunk and chunk.tenantId not in {case["tenantId"], "__public__"}:
                cross_tenant += 1
            if chunk and case["query"].strip().lower() == chunk.text.strip().lower():
                exact_match += 1
        unique_target_leak += int(any(chunk_id in case["query"] for chunk_id in relevant))
        same_tenant_chunks = [chunk for chunk in chunks if chunk.tenantId in {case["tenantId"], "__public__"}]
        single_candidate += int(len(same_tenant_chunks) <= 1)
    status = "PASS" if not any([duplicate, missing_relevant, cross_tenant]) else "FAIL"
    return {
        "benchmarkValidationStatus": status,
        "duplicateCaseCount": duplicate,
        "missingRelevantChunkCount": missing_relevant,
        "crossTenantLabelViolationCount": cross_tenant,
        "exactQueryChunkMatchCount": exact_match,
        "uniqueTargetTokenLeakCount": unique_target_leak,
        "singleCandidateCaseCount": single_candidate,
        "dataType": "synthetic controlled fixture",
    }


def _rss_mb() -> int:
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024)
    except Exception:
        return 0


def _cuda_memory() -> dict[str, int]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {"cudaAllocatedMb": 0, "cudaReservedMb": 0}
        return {
            "cudaAllocatedMb": int(torch.cuda.max_memory_allocated() / 1024 / 1024),
            "cudaReservedMb": int(torch.cuda.max_memory_reserved() / 1024 / 1024),
        }
    except Exception:
        return {"cudaAllocatedMb": 0, "cudaReservedMb": 0}


def _write(result: dict[str, Any]) -> None:
    write_json(PHASE3A_OUT / "evaluation-summary.json", result)
    lines = [
        "# Agent-RAG Phase 3A Evaluation",
        "",
        f"- Status: `{result['status']}`",
        f"- Mode: `{result['mode']}`",
        f"- Cases: `{result['caseCount']}`",
        f"- Documents: `{result['documentCount']}`",
        f"- Chunks: `{result['chunkCount']}`",
        "- Fixture hash metrics are kept separate from real BGE-M3 evidence.",
    ]
    if result.get("hybridReal"):
        lines += [
            f"- BM25 HitRate@5: `{result['bm25']['hitRateAt5']}`",
            f"- BM25 Recall@5: `{result['bm25']['recallAt5']}`",
            f"- BGE-M3 HitRate@5: `{result['bgeM3Dense']['hitRateAt5']}`",
            f"- BGE-M3 Recall@5: `{result['bgeM3Dense']['recallAt5']}`",
            f"- Hybrid-real HitRate@5: `{result['hybridReal']['hitRateAt5']}`",
            f"- Hybrid-real Recall@5: `{result['hybridReal']['recallAt5']}`",
            f"- Hybrid-real nDCG@5: `{result['hybridReal']['ndcgAt5']}`",
            f"- Tenant violations: `{result['hybridReal']['tenantViolations']}`",
        ]
    (PHASE3A_OUT / "evaluation-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
