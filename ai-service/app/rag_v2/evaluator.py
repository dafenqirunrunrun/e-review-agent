import math
import statistics
import time
from collections import defaultdict
from typing import Dict, List


def _dcg(relevances: List[int]) -> float:
    return sum(value / math.log2(index + 2) for index, value in enumerate(relevances))


def evaluate_queries(retriever, queries: List[Dict], strategy: str, top_k: int = 5) -> Dict:
    hit1 = hit3 = hit5 = empty = 0
    reciprocal = []
    ndcgs = []
    coverages = []
    latencies = []
    type_hits = defaultdict(lambda: [0, 0])
    failures = []
    for query in queries:
        request = {
            "query_text": query["query_text"], "risk_type": query["expected_risk_type"],
            "risk_level": query["expected_risk_level"], "product_category": query["product_category"],
            "evidence_keywords": query["evidence_keywords"], "hard_negative_case_ids": query["hard_negative_case_ids"],
            "top_k": top_k, "strategy": strategy,
        }
        result = retriever.search(request)
        ids = [row["case_id"] for row in result["hits"]]
        relevant = set(query["relevant_case_ids"])
        ranks = [index + 1 for index, case_id in enumerate(ids) if case_id in relevant]
        hit1 += int(any(rank <= 1 for rank in ranks))
        hit3 += int(any(rank <= 3 for rank in ranks))
        hit5 += int(any(rank <= 5 for rank in ranks))
        empty += int(not ids)
        reciprocal.append(1.0 / min(ranks) if ranks else 0.0)
        relevance = [1 if case_id in relevant else 0 for case_id in ids[:5]]
        ideal = [1] * min(3, len(ids[:5])) + [0] * max(0, len(ids[:5]) - 3)
        ndcgs.append(_dcg(relevance) / _dcg(ideal) if _dcg(ideal) else 0.0)
        evidence_text = " ".join(" ".join(row.get("evidence") or []) for row in result["hits"])
        keywords = query.get("evidence_keywords") or []
        coverages.append(sum(1 for word in keywords if word in evidence_text) / max(1, len(keywords)))
        latencies.append(float(result["latency_ms"]))
        type_hits[query["expected_risk_type"]][0] += int(any(rank <= 5 for rank in ranks))
        type_hits[query["expected_risk_type"]][1] += 1
        if not ranks:
            failures.append({"query_id": query["query_id"], "strategy": strategy, "returned_case_ids": ids,
                             "relevant_case_ids": query["relevant_case_ids"]})
    total = len(queries)
    ordered = sorted(latencies)
    p95 = ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)] if ordered else 0.0
    return {
        "strategy": strategy, "query_count": total, "hit_at_1": hit1 / total, "hit_at_3": hit3 / total,
        "hit_at_5": hit5 / total, "mrr": statistics.mean(reciprocal), "ndcg_at_5": statistics.mean(ndcgs),
        "empty_retrieval_rate": empty / total, "evidence_keyword_coverage": statistics.mean(coverages),
        "avg_latency_ms": statistics.mean(latencies), "p95_latency_ms": p95,
        "risk_type_hit_at_5": {key: value[0] / value[1] for key, value in sorted(type_hits.items())},
        "failures": failures,
    }
