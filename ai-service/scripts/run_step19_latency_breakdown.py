from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.core.config import settings
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer

INDEX = ROOT / "data/policy_rag_real/index/policy_chunks.jsonl"
FIELDS = (
    "intentRouterMs", "safetyGateMs", "riskDetectionMs", "evidenceQueryBuildMs",
    "embeddingQueueWaitMs", "embeddingComputeMs", "bm25Ms", "faissSearchMs",
    "rrfMs", "evidenceAgentMs", "reflectionMs", "persistenceMs", "totalMs",
)


def percentile(rows: list[float], ratio: float) -> float:
    ordered = sorted(rows)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * ratio))], 2)


def aggregate(samples: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    return {
        field: {
            "avg": round(statistics.mean(row.get(field, 0.0) for row in samples), 2),
            "p50": percentile([row.get(field, 0.0) for row in samples], 0.5),
            "p95": percentile([row.get(field, 0.0) for row in samples], 0.95),
            "p99": percentile([row.get(field, 0.0) for row in samples], 0.99),
            "max": round(max(row.get(field, 0.0) for row in samples), 2),
        }
        for field in FIELDS
    }


def payload(review_id: str) -> ReviewAnalyzeRequest:
    return ReviewAnalyzeRequest(
        review_id=review_id,
        product_id="step19",
        product_name="Performance fixture",
        review_text="五星截图后返现，并要求删除差评。",
        image_urls=[],
        rating=5,
    )


def run_case(name: str, *, fresh_process_semantics: bool, cache_enabled: bool, repeats: int) -> dict:
    samples: list[dict[str, float]] = []
    workflow = None
    for index in range(repeats):
        if fresh_process_semantics or workflow is None:
            retriever = PolicyEvidenceRetriever.from_jsonl(INDEX, enable_dense=True)
            workflow = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=retriever)
        settings.policy_rag.query_cache_enabled = cache_enabled
        if workflow.policy_retriever.dense_store and not cache_enabled:
            workflow.policy_retriever.dense_store.clear_query_cache()
        if cache_enabled and index == 0:
            # Prime the exact strict workflow query before measuring the cached path.
            workflow.analyze(payload(f"{name}-warmup"))
        response = workflow.analyze(payload(f"{name}-{index}"))
        samples.append(response.extra["latencyBreakdown"])
    return {"sampleCount": repeats, "stages": aggregate(samples), "finalReadiness": workflow.policy_retriever.readiness()}


def main() -> None:
    results = {
        "schemaVersion": "step19-latency-breakdown-v1",
        "coldStrict": run_case("cold-strict", fresh_process_semantics=True, cache_enabled=False, repeats=1),
        "warmStrictUncached": run_case("warm-uncached", fresh_process_semantics=False, cache_enabled=False, repeats=8),
        "warmStrictCached": run_case("warm-cached", fresh_process_semantics=False, cache_enabled=True, repeats=8),
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
