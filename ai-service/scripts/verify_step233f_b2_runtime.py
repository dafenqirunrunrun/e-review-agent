from __future__ import annotations

import json

from app.policy_rag.reranker import PolicyEvidenceReranker
from app.policy_rag.retriever import PolicyEvidenceRetriever


def main() -> None:
    query = "五星好评截图返现，晒图后联系客服退现金。"
    retriever = PolicyEvidenceRetriever()
    reranker = PolicyEvidenceReranker()
    readiness = reranker.readiness()
    if readiness["status"] != "ready":
        raise SystemExit(f"STEP233F_RERANKER_NOT_READY:{readiness['status']}")

    candidates = retriever.search(
        query,
        risk_hints=["fake_review", "rating_manipulation"],
        top_k=reranker.candidate_k,
        mode="hybrid",
    )
    outcome = reranker.rerank(query, candidates, chunk_resolver=retriever.chunk_for_id)
    citations_valid = all(
        item.sourceUrl and item.sectionPath and item.contentHash and len(item.snippet) <= 220
        for item in outcome.evidence
    )
    result = {
        "gate": "PASS"
        if outcome.metadata.get("effectiveMode") == "hybrid_bge_reranked" and citations_valid
        else "FAIL",
        "candidateCount": len(candidates),
        "candidateChunkIds": [item.chunkId for item in candidates],
        "outputCount": len(outcome.evidence),
        "outputChunkIds": [item.chunkId for item in outcome.evidence],
        "citationsValid": citations_valid,
        "retrievalMode": retriever.readiness().get("retrievalMode"),
        "reranker": {
            key: value
            for key, value in outcome.metadata.items()
            if key not in {"topScores"}
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["gate"] != "PASS":
        raise SystemExit("STEP233F_B2_RUNTIME_GATE_FAILED")


if __name__ == "__main__":
    main()
