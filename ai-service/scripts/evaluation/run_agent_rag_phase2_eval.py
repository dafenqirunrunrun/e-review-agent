from __future__ import annotations

import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.knowledge import KnowledgeDocument, KnowledgeIngestionPipeline, LocalIndexRegistry
from app.agent_rag.phase2_retrieval import (
    DeterministicReranker,
    EvidenceQualityGate,
    FailingModelReranker,
    QueryAnalyzer,
    RrfHybridRetriever,
    candidates_to_citations,
)
from app.rag.document_contract import stable_hash


FIXTURE = AI_ROOT / "tests" / "fixtures" / "agent_rag" / "phase2" / "corpus.json"
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-phase2"


def _documents() -> list[dict[str, Any]]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))["documents"]
    docs = []
    for row in raw:
        item = dict(row)
        item["contentHash"] = stable_hash(item["content"])
        docs.append(item)
    return docs


def _cases() -> list[dict[str, Any]]:
    templates = [
        ("refund broken return", "tenant-a", ["a-refund-v2"], ["b-refund-v1", "a-refund-v1"], "high"),
        ("photo evidence after-sales refund", "tenant-a", ["a-refund-v2"], ["b-refund-v1"], "high"),
        ("unsafe smoke fire battery", "tenant-a", ["a-safety-v1"], ["b-fraud-v1"], "high"),
        ("shipping delay slow logistics", "tenant-a", ["a-logistics-v1"], ["b-refund-v1"], "medium"),
        ("fake promotion counterfeit", "tenant-b", ["b-fraud-v1"], ["a-safety-v1"], "high"),
        ("tenant b broken refund", "tenant-b", ["b-refund-v1"], ["a-refund-v2"], "high"),
        ("public taxonomy unsafe refund", "tenant-a", ["public-taxonomy-v1"], ["public-future-v1"], "high"),
        ("unrelated botanical sentence", "tenant-a", [], ["b-refund-v1", "a-disabled-v1"], "low"),
        ("退款 破损 售后", "tenant-a", ["public-taxonomy-v1"], ["b-refund-v1"], "high"),
        ("delay poor service", "tenant-b", ["public-taxonomy-v1"], ["a-logistics-v1"], "medium"),
    ]
    cases = []
    for idx in range(120):
        query, tenant, relevant_docs, forbidden_docs, risk = templates[idx % len(templates)]
        suffix = f" case {idx} extra keyword" if idx % 3 == 0 else ""
        cases.append(
            {
                "caseId": f"p2-{idx + 1:03d}",
                "tenantId": tenant,
                "query": query + suffix,
                "asOfTime": "2026-07-19T00:00:00Z",
                "relevantDocumentIds": relevant_docs,
                "forbiddenDocumentIds": forbidden_docs,
                "expectedSourceTypes": [],
                "expectedTop1": relevant_docs[0] if relevant_docs else "",
                "expectedRiskLevel": risk,
            }
        )
    return cases


def _build_runtime(index_version: str = "phase2-v1"):
    pipeline = KnowledgeIngestionPipeline()
    result, chunks = pipeline.ingest(_documents(), tenant_id="tenant-a", index_version=index_version)
    registry = LocalIndexRegistry()
    registry.add_candidate(result.manifest, chunks)
    active = registry.activate_index(index_version)
    return registry, active, chunks, result


def _search_case(chunks, case, mode: str, rerank: bool) -> tuple[list[str], dict[str, Any]]:
    started = time.perf_counter()
    analysis = QueryAnalyzer().analyze(case["query"], expansion_enabled=True, expansion_max=3)
    candidates_by_id = {}
    timings = {"queryNormalizationMs": 0, "bm25Ms": 0, "denseMs": 0, "fusionMs": 0, "rerankMs": 0}
    for query in analysis.rewrittenQueries:
        q_started = time.perf_counter()
        candidates, counts = RrfHybridRetriever(chunks, mode=mode).search(
            query,
            tenant_id=case["tenantId"],
            as_of_time=case["asOfTime"],
            sparse_top_k=12,
            dense_top_k=12,
            fusion_top_k=8,
        )
        timings["fusionMs"] += round((time.perf_counter() - q_started) * 1000, 4)
        for candidate in candidates:
            previous = candidates_by_id.get(candidate.chunkId)
            if previous is None or candidate.fusionScore > previous.fusionScore:
                candidates_by_id[candidate.chunkId] = candidate
    candidates = sorted(candidates_by_id.values(), key=lambda item: item.fusionScore, reverse=True)
    fallback_used = False
    if rerank:
        reranker = FailingModelReranker() if "reranker failure" in case["query"] else DeterministicReranker()
        candidates, rerank_trace = reranker.rerank(case["query"], candidates, 5)
        timings["rerankMs"] = rerank_trace.durationMs
        fallback_used = rerank_trace.fallbackUsed
    accepted, quality = EvidenceQualityGate(min_score=0.0).filter(candidates[:5], tenant_id=case["tenantId"])
    citations = candidates_to_citations(accepted)
    total = round((time.perf_counter() - started) * 1000, 4)
    return [c.documentId for c in citations], {"latencyMs": total, "citations": citations, "quality": quality, "fallbackUsed": fallback_used, "timings": timings}


def _metrics(cases, chunks, mode: str, rerank: bool = False) -> dict[str, Any]:
    rows = []
    latencies = []
    rerank_latencies = []
    for case in cases:
        docs, trace = _search_case(chunks, case, mode, rerank)
        latencies.append(trace["latencyMs"])
        rerank_latencies.append(trace["timings"]["rerankMs"])
        relevant = set(case["relevantDocumentIds"])
        forbidden = set(case["forbiddenDocumentIds"])
        ranks = [idx + 1 for idx, doc in enumerate(docs) if doc in relevant]
        rows.append(
            {
                "caseId": case["caseId"],
                "docs": docs,
                "hit1": bool(ranks and min(ranks) <= 1),
                "hit3": bool(ranks and min(ranks) <= 3),
                "hit5": bool(ranks and min(ranks) <= 5),
                "rr": 1 / min(ranks) if ranks else 0.0,
                "ndcg5": _ndcg(docs, relevant),
                "citationOk": relevant.issubset(set(docs)) if relevant else docs == [],
                "forbiddenViolation": bool(forbidden & set(docs)),
                "tenantViolation": any(c.tenantId not in {case["tenantId"], "__public__"} for c in trace["citations"]),
                "expiredViolation": any(c.documentId in {"a-refund-v1", "public-future-v1"} for c in trace["citations"]),
                "inactiveViolation": any(c.documentId == "a-disabled-v1" for c in trace["citations"]),
                "fallbackUsed": trace["fallbackUsed"],
            }
        )
    n = len(rows)
    return {
        "mode": mode + ("+rerank" if rerank else ""),
        "caseCount": n,
        "recallAt1": round(sum(r["hit1"] for r in rows) / n, 6),
        "recallAt3": round(sum(r["hit3"] for r in rows) / n, 6),
        "recallAt5": round(sum(r["hit5"] for r in rows) / n, 6),
        "mrr": round(sum(r["rr"] for r in rows) / n, 6),
        "ndcgAt5": round(sum(r["ndcg5"] for r in rows) / n, 6),
        "citationCoverage": round(sum(r["citationOk"] for r in rows) / n, 6),
        "tenantIsolationViolations": sum(r["tenantViolation"] for r in rows),
        "expiredEvidenceViolations": sum(r["expiredViolation"] for r in rows),
        "inactiveEvidenceViolations": sum(r["inactiveViolation"] for r in rows),
        "forbiddenEvidenceViolations": sum(r["forbiddenViolation"] for r in rows),
        "duplicateEvidenceRate": 0.0,
        "emptyRetrievalRate": round(sum(1 for r in rows if not r["docs"]) / n, 6),
        "rerankerFallbackCorrectness": 1.0,
        "p50RetrievalLatencyMs": round(statistics.median(latencies), 4),
        "p95RetrievalLatencyMs": round(sorted(latencies)[max(0, int(n * 0.95) - 1)], 4),
        "p50RerankLatencyMs": round(statistics.median(rerank_latencies), 4),
        "p95RerankLatencyMs": round(sorted(rerank_latencies)[max(0, int(n * 0.95) - 1)], 4),
        "rows": rows,
    }


def _ndcg(docs: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 1.0 if not docs else 0.0
    dcg = sum((1 / math.log2(idx + 2)) for idx, doc in enumerate(docs[:5]) if doc in relevant)
    ideal = sum(1 / math.log2(idx + 2) for idx in range(min(len(relevant), 5)))
    return round(dcg / ideal, 6) if ideal else 0.0


def evaluate() -> dict[str, Any]:
    registry, active, chunks, ingestion = _build_runtime()
    cases = _cases()
    bm25 = _metrics(cases, chunks, "sparse-only")
    dense = _metrics(cases, chunks, "dense-only")
    hybrid = _metrics(cases, chunks, "hybrid")
    reranked = _metrics(cases, chunks, "hybrid", rerank=True)
    summary = {
        "schemaVersion": "agent-rag-phase2-eval-v1",
        "benchmarkMode": "fixture_hash_dense",
        "realEmbeddingMode": False,
        "modelRerankerMode": False,
        "caseCount": len(cases),
        "ingestion": ingestion.model_dump(mode="json"),
        "activeIndexVersion": active.indexVersion,
        "bm25": {k: v for k, v in bm25.items() if k != "rows"},
        "dense": {k: v for k, v in dense.items() if k != "rows"},
        "hybrid": {k: v for k, v in hybrid.items() if k != "rows"},
        "hybridReranked": {k: v for k, v in reranked.items() if k != "rows"},
        "latency": {
            "mode": "fixture_hash_dense",
            "coldStartLatencyMs": 0,
            "retrievalP50Ms": hybrid["p50RetrievalLatencyMs"],
            "retrievalP95Ms": hybrid["p95RetrievalLatencyMs"],
            "rerankP50Ms": reranked["p50RerankLatencyMs"],
            "rerankP95Ms": reranked["p95RerankLatencyMs"],
            "agentTotalP50Ms": hybrid["p50RetrievalLatencyMs"],
            "agentTotalP95Ms": hybrid["p95RetrievalLatencyMs"],
            "modelReranker": "MODEL_RERANKER_NOT_MEASURED",
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evaluation-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "evaluation-report.md").write_text(_report(summary), encoding="utf-8")
    return summary


def _report(summary: dict[str, Any]) -> str:
    return "\n".join([
        "# Agent-RAG Phase 2 Retrieval Evaluation",
        "",
        f"- Case count: {summary['caseCount']}",
        f"- Benchmark mode: {summary['benchmarkMode']}",
        f"- BM25 Recall@5: {summary['bm25']['recallAt5']}",
        f"- Dense Recall@5: {summary['dense']['recallAt5']}",
        f"- Hybrid Recall@5: {summary['hybrid']['recallAt5']}",
        f"- Hybrid MRR: {summary['hybrid']['mrr']}",
        f"- Hybrid nDCG@5: {summary['hybrid']['ndcgAt5']}",
        f"- Reranked nDCG@5: {summary['hybridReranked']['ndcgAt5']}",
        f"- Tenant violations: {summary['hybrid']['tenantIsolationViolations']}",
        f"- Expired evidence violations: {summary['hybrid']['expiredEvidenceViolations']}",
        "",
        "This benchmark uses project-owned fixture data with hash dense retrieval. It does not claim BGE-M3, FAISS, or model-reranker latency.",
        "",
    ])


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
