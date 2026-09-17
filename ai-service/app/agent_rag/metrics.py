from __future__ import annotations

import math
from typing import Any


METRIC_SCHEMA_VERSION = "2.0.0"


def dcg_at_k(relevance: list[float], k: int) -> float:
    return sum(((2**rel) - 1) / math.log2(index + 2) for index, rel in enumerate(relevance[:k]))


def ndcg_at_k(relevance: list[float], ideal_relevance: list[float], k: int) -> float:
    ideal = dcg_at_k(sorted(ideal_relevance, reverse=True), k)
    if ideal == 0:
        return 0.0
    value = dcg_at_k(relevance, k) / ideal
    if value < -1e-9 or value > 1 + 1e-9:
        raise ValueError("NDCG_OUT_OF_RANGE")
    return min(1.0, max(0.0, value))


def score_query(
    *,
    retrieved_chunk_ids: list[str],
    relevant_chunk_ids: set[str],
    forbidden_chunk_ids: set[str] | None = None,
    relevance_grades: dict[str, int] | None = None,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> dict[str, Any]:
    forbidden = forbidden_chunk_ids or set()
    grades = relevance_grades or {chunk_id: 1 for chunk_id in relevant_chunk_ids}
    deduped: list[str] = []
    seen: set[str] = set()
    duplicate_count = 0
    for chunk_id in retrieved_chunk_ids:
        if chunk_id in seen:
            duplicate_count += 1
            continue
        seen.add(chunk_id)
        deduped.append(chunk_id)
    first_rank = next((index + 1 for index, chunk_id in enumerate(deduped) if chunk_id in relevant_chunk_ids and chunk_id not in forbidden), None)
    metrics: dict[str, Any] = {
        "mrr": 0.0 if first_rank is None else 1.0 / first_rank,
        "duplicateCount": duplicate_count,
        "forbiddenHitCount": sum(1 for chunk_id in deduped if chunk_id in forbidden),
    }
    total_relevant = len(relevant_chunk_ids)
    for k in k_values:
        top_k = deduped[:k]
        relevant_hits = {chunk_id for chunk_id in top_k if chunk_id in relevant_chunk_ids and chunk_id not in forbidden}
        metrics[f"hitRateAt{k}"] = 1.0 if relevant_hits else 0.0
        metrics[f"recallAt{k}"] = 0.0 if total_relevant == 0 else len(relevant_hits) / total_relevant
    rel = [0 if chunk_id in forbidden else int(grades.get(chunk_id, 0)) for chunk_id in deduped[:5]]
    ideal = [int(value) for value in grades.values()]
    metrics["ndcgAt5"] = ndcg_at_k(rel, ideal, 5)
    return metrics


def macro_average(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, float]:
    if not rows:
        return {key: 0.0 for key in keys}
    return {key: sum(float(row[key]) for row in rows) / len(rows) for key in keys}


def validate_metric_ranges(summary: dict[str, Any], *, modes: list[str]) -> list[str]:
    errors: list[str] = []
    bounded = [
        "hitRateAt1",
        "hitRateAt3",
        "hitRateAt5",
        "recallAt1",
        "recallAt3",
        "recallAt5",
        "mrr",
        "ndcgAt5",
        "citationCoverage",
        "duplicateEvidenceRate",
        "emptyRetrievalRate",
    ]
    for mode in modes:
        metrics = summary.get(mode)
        if not isinstance(metrics, dict):
            errors.append(f"METRIC_MODE_MISSING:{mode}")
            continue
        for key in bounded:
            value = metrics.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                errors.append(f"METRIC_INVALID:{mode}:{key}")
                continue
            if float(value) < -1e-9 or float(value) > 1 + 1e-9:
                errors.append(f"METRIC_OUT_OF_RANGE:{mode}:{key}:{value}")
    return errors
