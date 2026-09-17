from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any

from v23_retrieval_common import (
    DOCS,
    EVALUATION_TIME_UTC,
    OUT,
    build_dataset_manifest,
    build_v23_cases,
    hash_json,
    prepare_runtime,
    read_json,
    score_ids,
    sparse_top_ids,
    stable_hash,
    summarize_metric_rows,
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

from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.asset_manifest:
        os.environ["AGENT_RAG_V22_ASSET_MANIFEST"] = args.asset_manifest
        apply_asset_manifest(Path(args.asset_manifest))
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    cases = build_v23_cases()
    manifest = build_dataset_manifest(cases)
    answerable_cases = [case for case in cases if case["label"] == "answerable"]
    payload = benchmark_payload()
    provider, runtime = prepare_runtime(payload)
    try:
        baseline = run_baseline(answerable_cases, manifest, runtime)
    finally:
        try:
            provider.close()
        except Exception:
            pass
    write_json(OUT / "v23-current-retrieval-baseline.json", baseline)
    write_text(DOCS / "V23_CURRENT_RETRIEVAL_BASELINE.md", render_doc(baseline))
    print("E_REVIEW_V23_RETRIEVAL_BASELINE_RECORDED")
    print(baseline["baselineMetricsHash"])
    return 0


def run_baseline(cases: list[dict[str, Any]], manifest: dict[str, Any], runtime: Any) -> dict[str, Any]:
    bm25_rows = []
    dense_rows = []
    rrf_rows = []
    union_rows = []
    rows_light = []
    latencies = []
    trace_samples = []
    for case in cases:
        relevant = set(case["expectedRelevantChunkIds"]) | set(case["acceptableRelevantChunkIds"])
        started = time.perf_counter()
        bm25_ids = sparse_top_ids(case["query"], case["tenantId"], 100)
        bm25_ms = round((time.perf_counter() - started) * 1000, 3)

        started = time.perf_counter()
        dense_candidates, dense_trace = runtime.search(
            case["query"],
            tenant_id=case["tenantId"],
            mode="real-dense",
            sparse_top_k=100,
            dense_top_k=100,
            fusion_top_k=100,
            rerank_top_k=None,
            evaluation_time_utc=EVALUATION_TIME_UTC,
        )
        dense_ms = round((time.perf_counter() - started) * 1000, 3)
        dense_ids = [item.chunkId for item in dense_candidates]

        started = time.perf_counter()
        rrf_candidates, rrf_trace = runtime.search(
            case["query"],
            tenant_id=case["tenantId"],
            mode="hybrid-real",
            sparse_top_k=100,
            dense_top_k=100,
            fusion_top_k=100,
            rerank_top_k=None,
            evaluation_time_utc=EVALUATION_TIME_UTC,
        )
        rrf_ms = round((time.perf_counter() - started) * 1000, 3)
        rrf_ids = [item.chunkId for item in rrf_candidates]
        union_ids = union_ranked_ids(bm25_ids, dense_ids)
        bm25_score = score_ids(bm25_ids, relevant)
        dense_score = score_ids(dense_ids, relevant)
        rrf_score = score_ids(rrf_ids, relevant)
        union_score = score_ids(union_ids, relevant)
        bm25_rows.append(bm25_score)
        dense_rows.append(dense_score)
        rrf_rows.append(rrf_score)
        union_rows.append(union_score)
        latencies.append({"bm25Ms": bm25_ms, "denseMs": dense_ms, "rrfMs": rrf_ms})
        if len(trace_samples) < 5:
            trace_samples.append(safe_trace(dense_trace, rrf_trace))
        rows_light.append(
            {
                "caseId": case["caseId"],
                "split": case["split"],
                "queryIntent": case["queryIntent"],
                "relevantChunkIdsHash": hash_json(case["expectedRelevantChunkIds"]),
                "bm25BestRelevantRank": best_rank(bm25_ids, relevant),
                "denseBestRelevantRank": best_rank(dense_ids, relevant),
                "rrfBestRelevantRank": best_rank(rrf_ids, relevant),
                "unionBestRelevantRank": best_rank(union_ids, relevant),
            }
        )
    metrics = {
        "bm25Metrics": summarize_metric_rows(bm25_rows),
        "denseMetrics": summarize_metric_rows(dense_rows),
        "rrfMetrics": summarize_metric_rows(rrf_rows),
        "unionOracleMetrics": summarize_metric_rows(union_rows),
        "candidateCoverage": {
            "coverageAt5": summarize_metric_rows(rrf_rows).get("recallAt5", 0.0),
            "coverageAt10": summarize_metric_rows(rrf_rows).get("recallAt10", 0.0),
            "coverageAt20": summarize_metric_rows(rrf_rows).get("recallAt20", 0.0),
            "coverageAt50": summarize_metric_rows(rrf_rows).get("recallAt50", 0.0),
            "coverageAt100": summarize_metric_rows(rrf_rows).get("recallAt100", 0.0),
        },
        "latencyP50": latency_summary(latencies, "rrfMs", 0.5),
        "latencyP95": latency_summary(latencies, "rrfMs", 0.95),
        "latencyP99": latency_summary(latencies, "rrfMs", 0.99),
    }
    return {
        "schemaVersion": "agent-rag-v23-current-retrieval-baseline-v1",
        "status": "COMPLETE",
        "datasetHash": manifest["datasetHash"],
        "knowledgeSnapshotHash": manifest["knowledgeSnapshotHash"],
        "configurationHash": read_json(OUT / "v23-current-retrieval-configuration.json").get("configurationHash", ""),
        **metrics,
        "bm25Executions": len(cases),
        "denseExecutions": len(cases),
        "rrfExecutions": len(cases),
        "indexSize": len(payload_chunks()),
        "memoryObservation": "not measured in this diagnostic baseline",
        "traceSamples": trace_samples,
        "rowsLightHash": hash_json(rows_light),
        "baselineMetricsHash": stable_hash(metrics),
        "rowsArtifactPolicy": "case-level rows are kept in hash/light form only; no full query or chunk text is persisted",
        "createdAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def payload_chunks() -> list[Any]:
    return benchmark_payload()["chunks"]


def union_ranked_ids(left: list[str], right: list[str]) -> list[str]:
    seen = set()
    rows = []
    for ids in (left, right):
        for rank, chunk_id in enumerate(ids, start=1):
            if chunk_id not in seen:
                seen.add(chunk_id)
                rows.append((min(rank, 100), chunk_id))
    return [chunk_id for _rank, chunk_id in sorted(rows, key=lambda item: (item[0], item[1]))]


def best_rank(ids: list[str], relevant: set[str]) -> int:
    for index, chunk_id in enumerate(ids, start=1):
        if chunk_id in relevant:
            return index
    return 0


def latency_summary(rows: list[dict[str, float]], key: str, percentile: float) -> float:
    values = sorted(row[key] for row in rows)
    if not values:
        return 0.0
    if percentile == 0.5:
        return round(float(median(values)), 3)
    index = min(len(values) - 1, int(len(values) * percentile))
    return round(values[index], 3)


def safe_trace(dense_trace: Any, rrf_trace: Any) -> dict[str, Any]:
    return {
        "denseProvider": getattr(dense_trace, "denseProvider", ""),
        "denseFallbackUsed": bool(getattr(dense_trace, "denseFallbackUsed", False)),
        "embeddingDimension": int(getattr(dense_trace, "embeddingDimension", 0) or 0),
        "faissIndexType": getattr(dense_trace, "faissIndexType", ""),
        "faissMetric": getattr(dense_trace, "faissMetric", ""),
        "rrfEffectiveRetrievalMode": getattr(rrf_trace, "effectiveRetrievalMode", ""),
    }


def render_doc(baseline: dict[str, Any]) -> str:
    return f"""# V2.3 Current Retrieval Baseline

This document freezes the current retrieval baseline on `v23-retrieval-qualification-v1`.

No BM25, dense, RRF, chunking, query, sparse, or multi-vector tuning was performed in Phase 9.0-9.1.

| Metric | BM25 | Dense | RRF | Union Oracle |
|---|---:|---:|---:|---:|
| Recall@10 | {baseline['bm25Metrics']['recallAt10']} | {baseline['denseMetrics']['recallAt10']} | {baseline['rrfMetrics']['recallAt10']} | {baseline['unionOracleMetrics']['recallAt10']} |
| Recall@20 | {baseline['bm25Metrics']['recallAt20']} | {baseline['denseMetrics']['recallAt20']} | {baseline['rrfMetrics']['recallAt20']} | {baseline['unionOracleMetrics']['recallAt20']} |
| Recall@50 | {baseline['bm25Metrics']['recallAt50']} | {baseline['denseMetrics']['recallAt50']} | {baseline['rrfMetrics']['recallAt50']} | {baseline['unionOracleMetrics']['recallAt50']} |
| Recall@100 | {baseline['bm25Metrics']['recallAt100']} | {baseline['denseMetrics']['recallAt100']} | {baseline['rrfMetrics']['recallAt100']} | {baseline['unionOracleMetrics']['recallAt100']} |
| MRR | {baseline['bm25Metrics']['mrr']} | {baseline['denseMetrics']['mrr']} | {baseline['rrfMetrics']['mrr']} | {baseline['unionOracleMetrics']['mrr']} |
| nDCG@5 | {baseline['bm25Metrics']['ndcgAt5']} | {baseline['denseMetrics']['ndcgAt5']} | {baseline['rrfMetrics']['ndcgAt5']} | {baseline['unionOracleMetrics']['ndcgAt5']} |

Baseline metrics hash: `{baseline['baselineMetricsHash']}`

This is a frozen comparison baseline for Phase 9.2 experiments. It does not claim retrieval quality improvement.
"""


if __name__ == "__main__":
    raise SystemExit(main())
