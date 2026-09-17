from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.retriever import PolicyEvidenceRetriever


SMOKE_CASES = [
    ("刷单", ["fake_review"]),
    ("好评返现", ["rating_manipulation"]),
    ("五星截图", ["rating_manipulation"]),
    ("删除差评", ["review_suppression"]),
    ("虚假评价", ["fake_review"]),
    ("评分操纵", ["rating_manipulation"]),
    ("paid review", ["rating_manipulation", "fake_review"]),
    ("fake engagement", ["fake_review", "rating_manipulation"]),
]

HARD_CASES = [
    ("merchant offers a rebate after I upload a five-star screenshot", ["rating_manipulation"]),
    ("buyer was pressured to take down a negative review", ["review_suppression"]),
    ("评价不是本人真实体验，像是商家组织写的", ["fake_review"]),
    ("商家说给红包让我改成五星", ["rating_manipulation"]),
    ("platform hides critical comments from product page", ["review_suppression"]),
    ("利益相关人员给自己的店铺写推荐", ["fake_review", "rating_manipulation"]),
    ("undisclosed compensation for customer testimonial", ["rating_manipulation"]),
    ("用户评论里暴露了电话号码和住址", ["privacy_risk"]),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify real Policy RAG ingestion and retrieval quality.")
    parser.add_argument("--chunks", required=True)
    parser.add_argument("--dense", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    chunks = load_policy_chunks(args.chunks)
    retriever = PolicyEvidenceRetriever.from_jsonl(args.chunks, enable_dense=args.dense)
    metrics = {}
    for mode in (["bm25", "dense", "hybrid"] if args.dense else ["bm25"]):
        metrics[mode] = {
            "smoke": _run_cases(retriever, mode, SMOKE_CASES),
            "hard": _run_cases(retriever, mode, HARD_CASES),
        }
    report = {
        "status": "pass" if metrics["bm25"]["smoke"]["recall@3"] == "8/8" else "fail",
        "sourceStats": _source_stats(chunks),
        "chunkStats": _chunk_stats(chunks),
        "denseEnabled": args.dense,
        "denseFallbackUsed": retriever.last_fallback_used,
        "denseError": retriever.last_dense_error,
        "metrics": metrics,
        "hybridVsBm25": {
            "smoke": _compare(metrics.get("bm25", {}).get("smoke"), metrics.get("hybrid", {}).get("smoke")),
            "hard": _compare(metrics.get("bm25", {}).get("hard"), metrics.get("hybrid", {}).get("hard")),
        },
        "badCases": _bad_cases(metrics),
        "citationExample": _citation_example(retriever),
    }
    print(json.dumps(_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


def _run_cases(retriever: PolicyEvidenceRetriever, mode: str, cases: list[tuple[str, list[str]]]) -> dict:
    rows = []
    hit3 = 0
    hit5 = 0
    citation_valid = True
    for query, risk_hints in cases:
        top3 = retriever.search(query, risk_hints=risk_hints, top_k=3, mode=mode)
        top5 = retriever.search(query, risk_hints=risk_hints, top_k=5, mode=mode)
        ok3 = _has_match(top3, risk_hints)
        ok5 = _has_match(top5, risk_hints)
        hit3 += int(ok3)
        hit5 += int(ok5)
        citation_valid = citation_valid and all(hit.sourceName and hit.sourceUrl and hit.sectionPath and hit.contentHash for hit in top5)
        rows.append(
            {
                "query": query,
                "expectedRiskHints": risk_hints,
                "hitAt3": ok3,
                "hitAt5": ok5,
                "topK": [
                    {
                        "rank": index,
                        "chunkId": hit.evidenceId,
                        "score": hit.score,
                        "source": hit.sourceName,
                        "sectionPath": hit.sectionPath,
                        "clauseId": hit.clauseId,
                        "tags": hit.evidenceTags,
                        "mode": hit.retrievalMode,
                    }
                    for index, hit in enumerate(top3, start=1)
                ],
            }
        )
    return {"recall@3": f"{hit3}/{len(cases)}", "recall@5": f"{hit5}/{len(cases)}", "citationValid": citation_valid, "rows": rows}


def _source_stats(chunks) -> dict:
    by_source = Counter(chunk.sourceName for chunk in chunks)
    by_type = Counter(chunk.sourceType for chunk in chunks)
    return {"sourceCount": len(by_source), "chunksBySource": dict(by_source), "chunksByType": dict(by_type)}


def _chunk_stats(chunks) -> dict:
    lengths = [chunk.tokenCount for chunk in chunks]
    block_types = Counter(str(chunk.metadata.get("blockType", "")) for chunk in chunks)
    missing = {
        "sourceUrl": sum(1 for chunk in chunks if not chunk.sourceUrl),
        "sectionPath": sum(1 for chunk in chunks if not chunk.sectionPath),
        "contentHash": sum(1 for chunk in chunks if not chunk.contentHash),
        "parentChunkId": sum(1 for chunk in chunks if not chunk.parentChunkId),
    }
    return {
        "chunkCount": len(chunks),
        "minTokens": min(lengths) if lengths else 0,
        "medianTokens": statistics.median(lengths) if lengths else 0,
        "maxTokens": max(lengths) if lengths else 0,
        "longChunksOver260": sum(1 for value in lengths if value > 260),
        "tinyChunksUnder8": sum(1 for value in lengths if value < 8),
        "blockTypes": dict(block_types),
        "missingMetadata": missing,
        "clauseChunkCount": sum(1 for chunk in chunks if chunk.clauseId),
    }


def _citation_example(retriever: PolicyEvidenceRetriever) -> dict:
    hits = retriever.search("paid review incentive", risk_hints=["rating_manipulation"], top_k=1, mode="hybrid")
    if not hits:
        return {}
    hit = hits[0]
    return {
        "sourceName": hit.sourceName,
        "sourceUrl": hit.sourceUrl,
        "sectionPath": hit.sectionPath,
        "clauseId": hit.clauseId,
        "snippet": hit.snippet,
        "contentHash": hit.contentHash,
    }


def _bad_cases(metrics: dict) -> list[dict]:
    rows = []
    for mode, suites in metrics.items():
        for suite_name, suite in suites.items():
            for row in suite["rows"]:
                if not row["hitAt3"]:
                    rows.append({"mode": mode, "suite": suite_name, "query": row["query"], "topK": row["topK"]})
    return rows[:12]


def _compare(bm25: dict | None, hybrid: dict | None) -> str:
    if not bm25 or not hybrid:
        return "not_available"
    b = int(bm25["recall@3"].split("/", 1)[0])
    h = int(hybrid["recall@3"].split("/", 1)[0])
    if h > b:
        return "improved"
    if h < b:
        return "regressed"
    return "flat"


def _has_match(results, risk_hints) -> bool:
    expected = set(risk_hints)
    alias = {
        "rating_manipulation": {"rating_manipulation", "incentivized_review"},
        "fake_review": {"fake_review", "fake_engagement"},
    }
    expanded = set(expected)
    for item in expected:
        expanded.update(alias.get(item, set()))
    return any(set(hit.riskTypes + hit.evidenceTags) & expanded for hit in results)


def _summary(report: dict) -> dict:
    compact_metrics = {}
    for mode, suites in report["metrics"].items():
        compact_metrics[mode] = {}
        for suite_name, suite in suites.items():
            compact_metrics[mode][suite_name] = {
                "recall@3": suite["recall@3"],
                "recall@5": suite["recall@5"],
                "citationValid": suite["citationValid"],
                "top1": [
                    {
                        "query": row["query"],
                        "chunkId": row["topK"][0]["chunkId"] if row["topK"] else "",
                        "source": row["topK"][0]["source"] if row["topK"] else "",
                        "score": row["topK"][0]["score"] if row["topK"] else 0,
                        "mode": row["topK"][0]["mode"] if row["topK"] else "",
                    }
                    for row in suite["rows"]
                ],
            }
    return {
        "status": report["status"],
        "sourceStats": report["sourceStats"],
        "chunkStats": report["chunkStats"],
        "denseEnabled": report["denseEnabled"],
        "denseFallbackUsed": report["denseFallbackUsed"],
        "denseError": report["denseError"],
        "metrics": compact_metrics,
        "hybridVsBm25": report["hybridVsBm25"],
        "badCaseCount": len(report["badCases"]),
        "citationExample": report["citationExample"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
