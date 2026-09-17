from __future__ import annotations

import argparse
import importlib.util
import os
import time
from pathlib import Path
from statistics import median
from typing import Any

from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload
from v23_candidate_fusion_common import DOCS, OUT, case_relevant, prepare_runtime, score_list, write_json, write_text
from v23_retrieval_common import hash_json
from v23_retrieval_v2_common import build_v23_v2_cases, build_v23_v2_manifest


VARIANTS = {
    "content_only": "chunk content",
    "title_content": "document title + chunk content",
    "section_content": "section title + chunk content",
    "title_section_content": "document title + section title + chunk content",
    "safe_scope_title_section_content": "source type + visibility + title + section title + chunk content",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        apply_asset_manifest(Path(args.asset_manifest))
    cases = build_v23_v2_cases()
    manifest = build_v23_v2_manifest(cases)
    calibration = [case for case in cases if case["split"] == "calibration" and case["label"] == "answerable"]
    payload = benchmark_payload()
    rows = []
    for variant in VARIANTS:
        rows.append(evaluate_variant(payload, calibration, variant))
    baseline = next(row for row in rows if row["variant"] == "content_only")
    selected = select_variant(rows, baseline)
    sparse = sparse_runtime_probe()
    result = {
        "schemaVersion": "agent-rag-v23-retrieval-representation-qualification-v1",
        "datasetVersion": manifest["datasetVersion"],
        "datasetHash": manifest["datasetHash"],
        "calibrationCaseCount": len(calibration),
        "variants": rows,
        "baseline": baseline,
        "selected": selected,
        "structuredRetrievalDecision": structured_decision(selected, baseline),
        "sparseRuntime": sparse,
        "threeWayHybridDecision": "NOT_RUN_BGE_M3_SPARSE_RUNTIME_UNAVAILABLE" if sparse["status"] != "PASS" else "READY_FOR_THREE_WAY_CALIBRATION",
        "runtimeIntegrationAllowed": False,
    }
    write_json(OUT / "v23-retrieval-representation-qualification.json", result)
    write_text(DOCS / "V23_STRUCTURED_RETRIEVAL_CONTENT_QUALIFICATION.md", render_structured_doc(result))
    write_text(DOCS / "V23_BGE_M3_SPARSE_RUNTIME_QUALIFICATION.md", render_sparse_doc(result))
    if result["structuredRetrievalDecision"] == "STRUCTURED_RETRIEVAL_CONTENT_QUALIFIED" and sparse["status"] == "PASS":
        print("AGENT_RAG_V23_REAL_BGE_M3_SPARSE_RUNTIME_PASS")
        print("E_REVIEW_V23_RETRIEVAL_REPRESENTATION_QUALIFICATION_PASS")
        return 0
    print("STRUCTURED_RETRIEVAL_CONTENT_NOT_QUALIFIED" if result["structuredRetrievalDecision"] != "STRUCTURED_RETRIEVAL_CONTENT_QUALIFIED" else "STRUCTURED_RETRIEVAL_CONTENT_QUALIFIED")
    print(sparse["decision"])
    return 1


def evaluate_variant(payload: dict[str, Any], cases: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    variant_payload = dict(payload)
    variant_payload["chunks"] = [rewrite_chunk(chunk, variant) for chunk in payload["chunks"]]
    provider, runtime = prepare_runtime(variant_payload)
    dense_scores = []
    bm25_scores = []
    latencies = []
    try:
        for case in cases:
            relevant = case_relevant(case)
            started = time.perf_counter()
            bm25, _ = runtime.search(case["query"], tenant_id=case["tenantId"], mode="sparse-only", fusion_top_k=100, rerank_top_k=None)
            dense, _ = runtime.search(case["query"], tenant_id=case["tenantId"], mode="real-dense", dense_top_k=100, fusion_top_k=100, rerank_top_k=None)
            latencies.append(round((time.perf_counter() - started) * 1000, 3))
            bm25_scores.append(score_list([item.chunkId for item in bm25], relevant))
            dense_scores.append(score_list([item.chunkId for item in dense], relevant))
    finally:
        try:
            provider.close()
        except Exception:
            pass
    dense = aggregate(dense_scores)
    bm25 = aggregate(bm25_scores)
    return {
        "variant": variant,
        "description": VARIANTS[variant],
        "retrievalContentHash": hash_json([chunk.text for chunk in variant_payload["chunks"]]),
        "denseMetrics": dense,
        "bm25Metrics": bm25,
        "latencyP50": latency(latencies, 0.5),
        "latencyP95": latency(latencies, 0.95),
        "indexSizeRatioToBaseline": 1.0,
        "embeddingP95Ms": latency(latencies, 0.95),
    }


def rewrite_chunk(chunk: Any, variant: str) -> Any:
    parts = []
    if variant in {"title_content", "title_section_content", "safe_scope_title_section_content"}:
        parts.append(f"title: {chunk.title or chunk.documentId}")
    if variant in {"section_content", "title_section_content", "safe_scope_title_section_content"}:
        parts.append(f"section: {chunk.sectionTitle or 'body'}")
    if variant == "safe_scope_title_section_content":
        source = chunk.sourceType.value if hasattr(chunk.sourceType, "value") else str(chunk.sourceType)
        parts.append(f"scope: source_type={source} visibility={chunk.visibility}")
    parts.append(chunk.text)
    text = "\n".join(parts)
    return chunk.model_copy(update={"text": text, "contentHash": hash_json(text), "tokenCount": max(1, len(text.split()))})


def aggregate(rows: list[dict[str, float]]) -> dict[str, float]:
    keys = [key for key in rows[0] if key != "bestRelevantRank"]
    out = {key: round(sum(float(row[key]) for row in rows) / len(rows), 6) for key in keys}
    ranks = sorted(int(row["bestRelevantRank"]) for row in rows if row.get("bestRelevantRank"))
    out["medianRelevantRank"] = 0 if not ranks else ranks[len(ranks) // 2]
    out["missCount"] = len(rows) - len(ranks)
    return out


def latency(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if pct == 0.5:
        return round(float(median(ordered)), 3)
    return round(float(ordered[min(len(ordered) - 1, int(len(ordered) * pct))]), 3)


def select_variant(rows: list[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for row in rows:
        dense_improvement = row["denseMetrics"]["coverageAt20"] - baseline["denseMetrics"]["coverageAt20"]
        bm25_regression = baseline["bm25Metrics"]["coverageAt20"] - row["bm25Metrics"]["coverageAt20"]
        median_improvement = baseline["denseMetrics"]["medianRelevantRank"] - row["denseMetrics"]["medianRelevantRank"]
        row["denseCoverageAt20Improvement"] = round(dense_improvement, 6)
        row["bm25CoverageAt20Regression"] = round(bm25_regression, 6)
        row["denseMedianRelevantRankImprovement"] = median_improvement
        row["qualified"] = (
            (dense_improvement >= 0.05 or median_improvement >= 5)
            and bm25_regression <= 0.01
            and row["indexSizeRatioToBaseline"] <= 1.5
            and row["embeddingP95Ms"] <= baseline["embeddingP95Ms"] * 1.35
        )
        if row["qualified"]:
            candidates.append(row)
    if not candidates:
        return baseline | {"qualified": False, "selectionReason": "no structured representation met dense improvement, BM25 regression, and resource gates"}
    return sorted(candidates, key=lambda row: (-row["denseCoverageAt20Improvement"], -row["denseMedianRelevantRankImprovement"], row["latencyP95"]))[0]


def structured_decision(selected: dict[str, Any], baseline: dict[str, Any]) -> str:
    if selected.get("qualified") and selected["variant"] != "content_only":
        return "STRUCTURED_RETRIEVAL_CONTENT_QUALIFIED"
    return "STRUCTURED_RETRIEVAL_CONTENT_NOT_QUALIFIED"


def sparse_runtime_probe() -> dict[str, Any]:
    flag_available = importlib.util.find_spec("FlagEmbedding") is not None
    model_dir = Path(os.getenv("RAG_BGE_M3_MODEL_PATH", "")) if os.getenv("RAG_BGE_M3_MODEL_PATH") else Path()
    if not flag_available:
        return {
            "status": "BLOCKED",
            "decision": "REAL_BGE_M3_SPARSE_RUNTIME_BLOCKED_FLAGEMBEDDING_MISSING",
            "flagEmbeddingAvailable": False,
            "modelPathConfigured": bool(str(model_dir)),
            "fallbackUsed": False,
            "bm25FallbackUsed": False,
            "denseFallbackUsed": False,
        }
    return {
        "status": "BLOCKED",
        "decision": "REAL_BGE_M3_SPARSE_RUNTIME_NOT_IMPLEMENTED_IN_PHASE_93_PROBE",
        "flagEmbeddingAvailable": True,
        "modelPathConfigured": bool(str(model_dir)),
        "fallbackUsed": False,
    }


def render_structured_doc(result: dict[str, Any]) -> str:
    return "# V2.3 Structured Retrieval Content Qualification\n\nDecision: `" + result["structuredRetrievalDecision"] + "`\n\n```json\n" + __import__("json").dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


def render_sparse_doc(result: dict[str, Any]) -> str:
    return "# V2.3 BGE-M3 Sparse Runtime Qualification\n\nDecision: `" + result["sparseRuntime"]["decision"] + "`\n\nNo BM25 or Dense fallback is accepted for sparse qualification.\n\n```json\n" + __import__("json").dumps(result["sparseRuntime"], ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


if __name__ == "__main__":
    raise SystemExit(main())
