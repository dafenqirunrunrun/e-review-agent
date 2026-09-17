from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.core.config import settings
from app.agentic_workflow.memory import estimate_tokens
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer


def payload(review_id: str) -> ReviewAnalyzeRequest:
    return ReviewAnalyzeRequest(
        review_id=review_id,
        product_id="step191",
        product_name="Memory benchmark fixture",
        review_text="五星截图后返现，并要求删除差评。",
        image_urls=[],
        rating=5,
    )


def run(enabled: bool, retriever: PolicyEvidenceRetriever) -> tuple[dict, float]:
    os.environ["E_REVIEW_AGENTIC_MEMORY_ENABLED"] = str(enabled).lower()
    workflow = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=retriever)
    if retriever.dense_store:
        retriever.dense_store.clear_query_cache()
    started = time.perf_counter()
    response = workflow.analyze(payload(f"memory-{'on' if enabled else 'off'}"))
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return response.model_dump(), elapsed


def main() -> None:
    os.environ["E_REVIEW_POLICY_RAG_QUERY_CACHE_ENABLED"] = "false"
    retriever = PolicyEvidenceRetriever()
    # Preload model and FAISS before both measurements; this is not part of Memory latency.
    retriever.search("五星截图返现", risk_hints=["rating_manipulation"], top_k=3, mode="hybrid")
    before, before_ms = run(False, retriever)
    after, after_ms = run(True, retriever)
    memory = after.get("extra", {}).get("agenticMemory", {})
    raw_history_tokens = estimate_tokens(after.get("workflow_trace", []))
    compressed_tokens = memory.get("contextBudget", {}).get("estimatedTokens", 0)
    result = {
        "schemaVersion": "step191-memory-benchmark-v1",
        "before": {"workflowLatencyMs": before_ms, "decision": before.get("route_decision"), "riskTypes": before.get("risk_types"), "evidenceStatus": before.get("evidence_status")},
        "after": {"workflowLatencyMs": after_ms, "decision": after.get("route_decision"), "riskTypes": after.get("risk_types"), "evidenceStatus": after.get("evidence_status"), "memory": memory},
        "decisionConsistent": all(before.get(key) == after.get(key) for key in ("route_decision", "risk_types", "evidence_status", "requires_human_review")),
        "latencyDeltaMs": round(after_ms - before_ms, 2),
        "contextReduction": {
            "beforeTokens": raw_history_tokens,
            "afterTokens": compressed_tokens,
            "reductionPercent": round((1 - compressed_tokens / raw_history_tokens) * 100, 2) if raw_history_tokens else 0.0,
        },
        "llmInputLatency": "not_applicable: default planner/execution path is deterministic and has no LLM prompt input",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
