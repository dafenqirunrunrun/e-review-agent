from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.retriever import PolicyEvidenceRetriever


CASES = [
    ("刷单", ["fake_review"]),
    ("好评返现", ["rating_manipulation"]),
    ("五星截图", ["rating_manipulation"]),
    ("删除差评", ["review_suppression"]),
    ("虚假评价", ["fake_review"]),
    ("评分操纵", ["rating_manipulation"]),
    ("paid review", ["rating_manipulation", "fake_review"]),
    ("fake engagement", ["fake_review", "rating_manipulation"]),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal verification for the free-local Policy RAG index.")
    parser.add_argument("--chunks", required=True, help="Path to policy_chunks.jsonl.")
    parser.add_argument("--dense", action="store_true", help="Try optional Qwen embedding + FAISS retrieval.")
    parser.add_argument("--summary-only", action="store_true", help="Print compact recall and Top1 summary.")
    args = parser.parse_args()

    retriever = PolicyEvidenceRetriever.from_jsonl(args.chunks, enable_dense=args.dense)
    modes = ["bm25", "dense", "hybrid"] if args.dense else ["bm25"]
    metrics = {mode: _run_mode(retriever, mode) for mode in modes}
    output = {
        "status": "pass" if metrics["bm25"]["citationValid"] and metrics["bm25"]["recall@3"] == "8/8" else "fail",
        "queryCount": len(CASES),
        "denseEnabled": args.dense,
        "denseFallbackUsed": retriever.last_fallback_used,
        "denseError": retriever.last_dense_error,
        "metrics": metrics,
        "hybridVsBm25": _compare(metrics.get("bm25"), metrics.get("hybrid")),
    }
    print(json.dumps(_summary(output) if args.summary_only else output, ensure_ascii=False, indent=2))
    return 0 if output["status"] == "pass" else 1


def _run_mode(retriever: PolicyEvidenceRetriever, mode: str) -> dict:
    rows = []
    recall_at_3 = 0
    recall_at_5 = 0
    citation_valid = True
    for query, risk_hints in CASES:
        top3 = retriever.search(query, risk_hints=risk_hints, top_k=3, mode=mode)
        top5 = retriever.search(query, risk_hints=risk_hints, top_k=5, mode=mode)
        match3 = _has_matching_policy_hit(top3, risk_hints)
        match5 = _has_matching_policy_hit(top5, risk_hints)
        recall_at_3 += int(match3)
        recall_at_5 += int(match5)
        citation_valid = citation_valid and all(hit.sourceUrl and hit.sectionPath and hit.contentHash for hit in top5)
        rows.append(
            {
                "query": query,
                "expectedRiskHints": risk_hints,
                "hitAt3": match3,
                "hitAt5": match5,
                "topK": [
                    {
                        "rank": index,
                        "chunkId": hit.evidenceId,
                        "score": hit.score,
                        "source": hit.sourceName,
                        "sectionPath": hit.sectionPath,
                        "tags": hit.evidenceTags,
                        "mode": hit.retrievalMode,
                    }
                    for index, hit in enumerate(top3, start=1)
                ],
            }
        )
    return {
        "recall@3": f"{recall_at_3}/{len(CASES)}",
        "recall@5": f"{recall_at_5}/{len(CASES)}",
        "citationValid": citation_valid,
        "rows": rows,
    }


def _compare(bm25: dict | None, hybrid: dict | None) -> str:
    if not bm25 or not hybrid:
        return "not_available"
    bm25_hits = _metric_count(bm25["recall@3"])
    hybrid_hits = _metric_count(hybrid["recall@3"])
    if hybrid_hits > bm25_hits:
        return "improved"
    if hybrid_hits < bm25_hits:
        return "regressed"
    return "flat"


def _summary(output: dict) -> dict:
    compact = {
        "status": output["status"],
        "denseEnabled": output["denseEnabled"],
        "denseFallbackUsed": output["denseFallbackUsed"],
        "denseError": output["denseError"],
        "hybridVsBm25": output["hybridVsBm25"],
        "metrics": {},
    }
    for mode, metric in output["metrics"].items():
        compact["metrics"][mode] = {
            "recall@3": metric["recall@3"],
            "recall@5": metric["recall@5"],
            "citationValid": metric["citationValid"],
            "top1": [
                {
                    "query": row["query"],
                    "chunkId": row["topK"][0]["chunkId"] if row["topK"] else "",
                    "score": row["topK"][0]["score"] if row["topK"] else 0,
                    "source": row["topK"][0]["source"] if row["topK"] else "",
                    "mode": row["topK"][0]["mode"] if row["topK"] else "",
                }
                for row in metric["rows"]
            ],
        }
    return compact


def _metric_count(value: str) -> int:
    return int(value.split("/", 1)[0])


def _has_matching_policy_hit(results, risk_hints):
    expected = set(risk_hints)
    for hit in results:
        tags = set(hit.riskTypes + hit.evidenceTags)
        if tags & expected:
            return True
        if "rating_manipulation" in expected and tags & {"incentivized_review", "rating_manipulation"}:
            return True
        if "fake_review" in expected and tags & {"fake_engagement", "fake_review"}:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
