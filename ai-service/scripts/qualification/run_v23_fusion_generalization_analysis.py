from __future__ import annotations

import argparse
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload
from v23_candidate_fusion_common import DOCS, OUT, FusionConfig, case_relevant, load_dataset, prepare_runtime, retrieve_depths, rrf_fuse, score_list, split_answerable, write_json, write_text
from v23_retrieval_common import hash_json


SELECTED = FusionConfig(20, 100, 100, 20, bm25Weight=0.75, denseWeight=1.25)
EQUAL_WEIGHT_SELECTED_K = FusionConfig(20, 100, 100, 20, bm25Weight=1.0, denseWeight=1.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        apply_asset_manifest(Path(args.asset_manifest))

    cases, manifest = load_dataset()
    payload = benchmark_payload()
    chunks = {chunk.chunkId: chunk for chunk in payload["chunks"]}
    provider, runtime = prepare_runtime(payload)
    try:
        calibration_rows = analyze_split(split_answerable(cases, "calibration"), runtime, chunks)
        evaluation_rows = analyze_split(split_answerable(cases, "evaluation"), runtime, chunks)
    finally:
        try:
            provider.close()
        except Exception:
            pass

    calibration_summary = summarize(calibration_rows)
    evaluation_summary = summarize(evaluation_rows)
    comparison = compare(calibration_summary, evaluation_summary)
    conclusion = conclude(comparison)
    payload_out = {
        "schemaVersion": "agent-rag-v23-candidate-fusion-generalization-analysis-v1",
        "datasetHash": manifest["datasetHash"],
        "phase92Consumed": {
            "calibration": True,
            "evaluation": True,
            "challenge": False,
            "futureQualificationAllowedForCalibration": False,
            "futureQualificationAllowedForEvaluation": False,
            "futureQualificationAllowedForChallenge": False,
        },
        "selectedConfigurationHash": SELECTED.configuration_hash,
        "selectedConfiguration": SELECTED.as_dict(),
        "calibration": calibration_summary,
        "evaluation": evaluation_summary,
        "comparison": comparison,
        "conclusion": conclusion,
        "rowHashes": {
            "calibrationRowsHash": hash_json(light_rows(calibration_rows)),
            "evaluationRowsHash": hash_json(light_rows(evaluation_rows)),
        },
    }
    write_json(OUT / "v23-candidate-fusion-generalization-analysis.json", payload_out)
    write_text(DOCS / "V23_PHASE_93_DATA_CONSUMPTION_BOUNDARY.md", render_boundary_doc(payload_out))
    write_text(DOCS / "V23_CANDIDATE_FUSION_GENERALIZATION_ANALYSIS.md", render_analysis_doc(payload_out))
    print("E_REVIEW_V23_CANDIDATE_FUSION_GENERALIZATION_ANALYSIS_COMPLETE")
    print(conclusion["primaryCause"])
    return 0


def analyze_split(cases: list[dict[str, Any]], runtime: Any, chunks: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        relevant = case_relevant(case)
        bm25, dense = retrieve_depths(case, runtime, bm25_k=100, dense_k=100)
        fused_selected = rrf_fuse(bm25, dense, SELECTED)
        fused_equal = rrf_fuse(bm25, dense, EQUAL_WEIGHT_SELECTED_K)
        bm25_ids = [item.chunkId for item in bm25]
        dense_ids = [item.chunkId for item in dense]
        selected_ids = [item.chunkId for item in fused_selected]
        equal_ids = [item.chunkId for item in fused_equal]
        bm25_rank = best_rank(bm25_ids, relevant)
        dense_rank = best_rank(dense_ids, relevant)
        selected_rank = best_rank(selected_ids, relevant)
        equal_rank = best_rank(equal_ids, relevant)
        query_tokens = case["query"].split()
        relevant_token_count = sum(len((chunks.get(chunk_id).text if chunks.get(chunk_id) else "").split()) for chunk_id in relevant)
        rows.append(
            {
                "caseId": case["caseId"],
                "queryIntent": case["queryIntent"],
                "caseFamilyHash": hash_json(case["caseFamilyId"]),
                "documentFamilyHash": hash_json(case["documentFamilyId"]),
                "queryTokenCount": len(query_tokens),
                "relevantChunkTokenCount": relevant_token_count,
                "bm25BestRelevantRank": bm25_rank,
                "denseBestRelevantRank": dense_rank,
                "selectedRrfBestRelevantRank": selected_rank,
                "equalWeightRrfBestRelevantRank": equal_rank,
                "bm25RankBucket": rank_bucket(bm25_rank),
                "denseRankBucket": rank_bucket(dense_rank),
                "selectedRrfRankBucket": rank_bucket(selected_rank),
                "dependencyClass": dependency_class(bm25_rank, dense_rank, selected_rank),
                "bm25OnlyHitAt20": bm25_rank > 0 and bm25_rank <= 20 and (dense_rank == 0 or dense_rank > 20),
                "denseOnlyHitAt20": dense_rank > 0 and dense_rank <= 20 and (bm25_rank == 0 or bm25_rank > 20),
                "bothHitAt20": bm25_rank > 0 and bm25_rank <= 20 and dense_rank > 0 and dense_rank <= 20,
                "neitherHitAt20": not ((bm25_rank > 0 and bm25_rank <= 20) or (dense_rank > 0 and dense_rank <= 20)),
                "candidateOverlapAt20": overlap(bm25_ids[:20], dense_ids[:20]),
                "retrieverAgreement": retriever_agreement(bm25_rank, dense_rank),
                "selectedCoverageAt20": score_list(selected_ids, relevant, (20,))["coverageAt20"],
                "equalWeightCoverageAt20": score_list(equal_ids, relevant, (20,))["coverageAt20"],
                "denseWeightHelped": selected_rank > 0 and (equal_rank == 0 or selected_rank < equal_rank),
                "denseWeightHurt": equal_rank > 0 and (selected_rank == 0 or selected_rank > equal_rank),
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_intent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_intent[row["queryIntent"]].append(row)
    return {
        "caseCount": len(rows),
        "intentDistribution": pct_counter(row["queryIntent"] for row in rows),
        "dependencyDistribution": pct_counter(row["dependencyClass"] for row in rows),
        "denseRankDistribution": pct_counter(row["denseRankBucket"] for row in rows),
        "selectedRrfRankDistribution": pct_counter(row["selectedRrfRankBucket"] for row in rows),
        "bm25DominantRate": ratio(rows, lambda row: row["dependencyClass"] == "BM25_DOMINANT"),
        "denseDominantRate": ratio(rows, lambda row: row["dependencyClass"] == "DENSE_DOMINANT"),
        "deepRankRate": ratio(rows, lambda row: row["dependencyClass"] == "DEEP_RANK_ONLY"),
        "retrieverDisagreementRate": ratio(rows, lambda row: row["dependencyClass"] == "RETRIEVER_DISAGREEMENT"),
        "averageCandidateOverlapAt20": round(sum(row["candidateOverlapAt20"] for row in rows) / max(1, len(rows)), 6),
        "averageQueryTokenCount": round(sum(row["queryTokenCount"] for row in rows) / max(1, len(rows)), 6),
        "averageRelevantChunkTokenCount": round(sum(row["relevantChunkTokenCount"] for row in rows) / max(1, len(rows)), 6),
        "selectedCoverageAt20": ratio(rows, lambda row: row["selectedCoverageAt20"] > 0),
        "equalWeightCoverageAt20": ratio(rows, lambda row: row["equalWeightCoverageAt20"] > 0),
        "denseWeightHelpedRate": ratio(rows, lambda row: row["denseWeightHelped"]),
        "denseWeightHurtRate": ratio(rows, lambda row: row["denseWeightHurt"]),
        "intentWeightSensitivity": {
            intent: {
                "caseCount": len(items),
                "selectedCoverageAt20": ratio(items, lambda row: row["selectedCoverageAt20"] > 0),
                "equalWeightCoverageAt20": ratio(items, lambda row: row["equalWeightCoverageAt20"] > 0),
                "denseWeightHelped": sum(1 for row in items if row["denseWeightHelped"]),
                "denseWeightHurt": sum(1 for row in items if row["denseWeightHurt"]),
            }
            for intent, items in sorted(by_intent.items())
        },
    }


def compare(calibration: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    return {
        "selectedCoverageAt20Gap": round(calibration["selectedCoverageAt20"] - evaluation["selectedCoverageAt20"], 6),
        "bm25DominantDeltaEvalMinusCal": round(evaluation["bm25DominantRate"] - calibration["bm25DominantRate"], 6),
        "denseDominantDeltaEvalMinusCal": round(evaluation["denseDominantRate"] - calibration["denseDominantRate"], 6),
        "deepRankDeltaEvalMinusCal": round(evaluation["deepRankRate"] - calibration["deepRankRate"], 6),
        "retrieverDisagreementDeltaEvalMinusCal": round(evaluation["retrieverDisagreementRate"] - calibration["retrieverDisagreementRate"], 6),
        "candidateOverlapDeltaEvalMinusCal": round(evaluation["averageCandidateOverlapAt20"] - calibration["averageCandidateOverlapAt20"], 6),
        "denseWeightHurtDeltaEvalMinusCal": round(evaluation["denseWeightHurtRate"] - calibration["denseWeightHurtRate"], 6),
        "denseWeightHelpedDeltaEvalMinusCal": round(evaluation["denseWeightHelpedRate"] - calibration["denseWeightHelpedRate"], 6),
    }


def conclude(comparison: dict[str, Any]) -> dict[str, Any]:
    causes = []
    if comparison["selectedCoverageAt20Gap"] >= 0.08:
        causes.append("CALIBRATION_TO_EVALUATION_GENERALIZATION_GAP")
    if comparison["bm25DominantDeltaEvalMinusCal"] >= 0.05:
        causes.append("EVALUATION_MORE_BM25_DOMINANT")
    if comparison["deepRankDeltaEvalMinusCal"] >= 0.05:
        causes.append("EVALUATION_MORE_DEEP_RANK")
    if comparison["denseWeightHurtDeltaEvalMinusCal"] >= 0.03:
        causes.append("GLOBAL_DENSE_WEIGHT_INTENT_SENSITIVE")
    if not causes:
        causes.append("ROOT_CAUSE_UNRESOLVED")
    weight = "GLOBAL_WEIGHT_INTENT_SENSITIVE" if "GLOBAL_DENSE_WEIGHT_INTENT_SENSITIVE" in causes else "ROOT_CAUSE_UNRESOLVED"
    return {
        "primaryCause": "+".join(causes),
        "globalWeightConclusion": weight,
        "runtimeIntegrationAllowed": False,
        "nextExperimentRecommendation": "build balanced v23-retrieval-qualification-v2 before testing structured retrieval content and BGE-M3 sparse",
    }


def best_rank(ids: list[str], relevant: set[str]) -> int:
    for index, chunk_id in enumerate(ids, start=1):
        if chunk_id in relevant:
            return index
    return 0


def rank_bucket(rank: int) -> str:
    if rank == 0:
        return ">100"
    if rank <= 5:
        return "1-5"
    if rank <= 10:
        return "6-10"
    if rank <= 20:
        return "11-20"
    if rank <= 30:
        return "21-30"
    if rank <= 50:
        return "31-50"
    if rank <= 75:
        return "51-75"
    if rank <= 100:
        return "76-100"
    return ">100"


def dependency_class(bm25_rank: int, dense_rank: int, rrf_rank: int) -> str:
    bm25_hit20 = 0 < bm25_rank <= 20
    dense_hit20 = 0 < dense_rank <= 20
    if bm25_hit20 and dense_hit20:
        return "BOTH_SUPPORT"
    if bm25_hit20 and not dense_hit20:
        return "BM25_DOMINANT"
    if dense_hit20 and not bm25_hit20:
        return "DENSE_DOMINANT"
    if (0 < bm25_rank <= 100) or (0 < dense_rank <= 100) or (0 < rrf_rank <= 20):
        return "DEEP_RANK_ONLY"
    return "RETRIEVER_DISAGREEMENT"


def retriever_agreement(bm25_rank: int, dense_rank: int) -> str:
    if bm25_rank == 0 and dense_rank == 0:
        return "NEITHER_HIT"
    if bm25_rank == 0 or dense_rank == 0:
        return "ONE_ROUTE_ONLY"
    if abs(bm25_rank - dense_rank) <= 10:
        return "AGREE_WITHIN_10"
    return "DISAGREE_BY_RANK"


def overlap(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    return round(len(left_set & right_set) / max(1, len(left_set | right_set)), 6)


def pct_counter(values: Any) -> dict[str, Any]:
    values = list(values)
    counts = Counter(values)
    total = max(1, len(values))
    return {key: {"count": count, "rate": round(count / total, 6)} for key, count in sorted(counts.items())}


def ratio(rows: list[dict[str, Any]], predicate: Any) -> float:
    return round(sum(1 for row in rows if predicate(row)) / max(1, len(rows)), 6)


def light_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "caseId": row["caseId"],
            "queryIntent": row["queryIntent"],
            "bm25BestRelevantRank": row["bm25BestRelevantRank"],
            "denseBestRelevantRank": row["denseBestRelevantRank"],
            "selectedRrfBestRelevantRank": row["selectedRrfBestRelevantRank"],
            "dependencyClass": row["dependencyClass"],
        }
        for row in rows
    ]


def render_boundary_doc(payload: dict[str, Any]) -> str:
    boundary = payload["phase92Consumed"]
    return f"""# V2.3 Phase 9.3 Data Consumption Boundary

Phase 9.2 consumed the original v23 calibration and evaluation splits. They are now diagnostic-only and cannot be reused for final unbiased qualification.

```json
{__import__("json").dumps(boundary, ensure_ascii=False, indent=2, sort_keys=True)}
```

Decision: Phase 9.3 must build a new balanced benchmark before any new retrieval representation is qualified.
"""


def render_analysis_doc(payload: dict[str, Any]) -> str:
    comparison = payload["comparison"]
    conclusion = payload["conclusion"]
    return f"""# V2.3 Candidate Fusion Generalization Analysis

Decision: `{conclusion["primaryCause"]}`

## Key Findings

```text
Calibration selected Coverage@20 = {payload["calibration"]["selectedCoverageAt20"]}
Evaluation selected Coverage@20 = {payload["evaluation"]["selectedCoverageAt20"]}
Generalization gap = {comparison["selectedCoverageAt20Gap"]}

BM25-dominant delta = {comparison["bm25DominantDeltaEvalMinusCal"]}
Dense-dominant delta = {comparison["denseDominantDeltaEvalMinusCal"]}
Deep-rank delta = {comparison["deepRankDeltaEvalMinusCal"]}
Retriever-disagreement delta = {comparison["retrieverDisagreementDeltaEvalMinusCal"]}
Dense-weight hurt delta = {comparison["denseWeightHurtDeltaEvalMinusCal"]}
```

## Engineering Interpretation

Phase 9.2 improved the calibration split, but the selected global Dense-heavy RRF configuration did not generalize to the frozen evaluation split. The result supports moving away from more candidate-budget tuning and toward a new balanced benchmark plus retrieval representation experiments.

## Resume-Ready Note

Analyzed a Hybrid RAG generalization failure after a calibration-only optimization passed but held-out evaluation failed. Quantified split shift across retriever dependency classes, rank buckets, candidate overlap, and intent-level weight sensitivity, then blocked runtime rollout and redirected the next experiment toward structured retrieval content and sparse lexical representation.

```json
{__import__("json").dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
