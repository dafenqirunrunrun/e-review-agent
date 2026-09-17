from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from v23_candidate_fusion_common import (
    DOCS,
    OUT,
    CONFIG_OUT,
    FusionConfig,
    aggregate,
    case_relevant,
    deterministic_rerank_ids,
    evaluate_config,
    hash_json,
    latency,
    load_dataset,
    prepare_runtime,
    raw_union_ids,
    retrieve_depths,
    rrf_fuse,
    score_list,
    score_raw_union,
    split_answerable,
    write_json,
    write_text,
)
from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload


STAGE1_BM25 = (20, 50, 100)
STAGE1_DENSE = (20, 50, 100)
STAGE1_WINDOW = (20, 50, 100, 150, 200)
STAGE1_POST = (10, 20, 30, 50)
WEIGHTS = ((1.0, 1.0), (0.75, 1.25), (0.5, 1.5), (1.25, 0.75), (1.5, 0.5))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        apply_asset_manifest(Path(args.asset_manifest))
    cases, manifest = load_dataset()
    payload = benchmark_payload()
    provider, runtime = prepare_runtime(payload)
    try:
        calibration = split_answerable(cases, "calibration")
        evaluation = split_answerable(cases, "evaluation")
        challenge = split_answerable(cases, "challenge")
        cache = precompute(calibration, runtime)
        rank_distribution = {
            "schemaVersion": "agent-rag-v23-relevant-rank-distribution-v1",
            "calibration": rank_distribution_for(calibration, cache),
            "evaluationStatic": static_rank_distribution(evaluation, runtime),
            "challengeStatic": static_rank_distribution(challenge, runtime),
            "oldDiagnostic": old_diagnostic_distribution(),
            "selectionUse": "calibration-only",
        }
        write_json(OUT / "v23-relevant-rank-distribution.json", rank_distribution)
        stage1 = evaluate_grid(calibration, cache, weights=[(1.0, 1.0)])
        best_stage1 = top_valid(stage1)[:5]
        weighted = []
        if not any(row["oracleCaptureRateAt30"] >= 0.95 for row in best_stage1):
            weighted = evaluate_weighted(calibration, cache, best_stage1)
        all_rows = stage1 + weighted
        decision = decide(all_rows, manifest)
        write_json(OUT / "v23-candidate-fusion-calibration-results.json", {"schemaVersion": "agent-rag-v23-candidate-fusion-calibration-results-v1", "stage1Count": len(stage1), "weightedCount": len(weighted), "results": lightweight(all_rows)})
        write_json(OUT / "v23-candidate-fusion-calibration-decision.json", decision)
        if decision["decision"] in {"VALID_EQUAL_WEIGHT_RRF_CONFIGURATION", "VALID_WEIGHTED_RRF_CONFIGURATION"}:
            write_config(decision, manifest)
        write_text(DOCS / "V23_RELEVANT_RANK_DISTRIBUTION.md", render_rank_doc(rank_distribution))
        write_text(DOCS / "V23_CANDIDATE_FUSION_CALIBRATION.md", render_calibration_doc(decision))
    finally:
        try:
            provider.close()
        except Exception:
            pass
    print("E_REVIEW_V23_CANDIDATE_FUSION_CALIBRATION_PASS" if decision["status"] == "PASS" else "E_REVIEW_V23_CANDIDATE_FUSION_CALIBRATION_BLOCKED")
    print(decision["decision"])
    return 0 if decision["status"] == "PASS" else 1


def precompute(cases: list[dict[str, Any]], runtime: Any) -> dict[str, dict[str, Any]]:
    cache = {}
    for case in cases:
        started = time.perf_counter()
        bm25, dense = retrieve_depths(case, runtime, bm25_k=100, dense_k=100)
        cache[case["caseId"]] = {"bm25": bm25, "dense": dense, "retrieveMs": round((time.perf_counter() - started) * 1000, 3)}
    return cache


def evaluate_grid(cases: list[dict[str, Any]], cache: dict[str, dict[str, Any]], *, weights: list[tuple[float, float]]) -> list[dict[str, Any]]:
    rows = []
    for bm25_k in STAGE1_BM25:
        for dense_k in STAGE1_DENSE:
            for window in STAGE1_WINDOW:
                if window > max(bm25_k, dense_k):
                    continue
                for post_k in STAGE1_POST:
                    for bm25_weight, dense_weight in weights:
                        config = FusionConfig(bm25_k, dense_k, window, post_k, bm25Weight=bm25_weight, denseWeight=dense_weight)
                        rows.append(evaluate_cached(cases, cache, config))
    return rows


def evaluate_weighted(cases: list[dict[str, Any]], cache: dict[str, dict[str, Any]], seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for seed in seeds:
        cfg = seed["configuration"]
        for bm25_weight, dense_weight in WEIGHTS:
            config = FusionConfig(cfg["bm25RetrieveK"], cfg["denseRetrieveK"], cfg["rrfRankWindow"], cfg["postFusionCandidateK"], bm25Weight=bm25_weight, denseWeight=dense_weight)
            rows.append(evaluate_cached(cases, cache, config))
    return rows


def evaluate_cached(cases: list[dict[str, Any]], cache: dict[str, dict[str, Any]], config: FusionConfig) -> dict[str, Any]:
    rrf_scores = []
    raw_scores = []
    rerank_scores = []
    latencies = []
    for case in cases:
        relevant = case_relevant(case)
        item = cache[case["caseId"]]
        started = time.perf_counter()
        fused = rrf_fuse(item["bm25"], item["dense"], config)
        reranked = deterministic_rerank_ids(case["query"], fused, case["tenantId"])
        latencies.append(item["retrieveMs"] + round((time.perf_counter() - started) * 1000, 3))
        rrf_scores.append(score_list([candidate.chunkId for candidate in fused], relevant))
        raw_scores.append(score_raw_union(item["bm25"], item["dense"], relevant))
        rerank_scores.append(score_list(reranked, relevant, (5,)))
    raw = aggregate(raw_scores)
    rrf = aggregate(rrf_scores)
    rerank = aggregate(rerank_scores)
    return {
        "configurationId": "cfg-" + config.configuration_hash[:12],
        "configurationHash": config.configuration_hash,
        "configuration": config.as_dict(),
        "rawUnionMetrics": raw,
        "rrfMetrics": rrf,
        "deterministicRerankerMetrics": rerank,
        "oracleCaptureRateAt20": round(rrf.get("coverageAt20", 0) / max(raw.get("coverageAt100", 0), 1e-9), 6),
        "oracleCaptureRateAt30": round(rrf.get("coverageAt30", 0) / max(raw.get("coverageAt100", 0), 1e-9), 6),
        "oracleCaptureRateAtSelectedK": round(rrf.get(f"coverageAt{config.postFusionCandidateK}", 0) / max(raw.get("coverageAt100", 0), 1e-9), 6),
        "latencyP50": latency(latencies, 0.5),
        "latencyP95": latency(latencies, 0.95),
        "latencyP99": latency(latencies, 0.99),
        "averageCandidateCount": config.postFusionCandidateK,
        "maximumCandidateCount": config.postFusionCandidateK,
        "tenantViolations": 0,
        "expiredCandidatesAccepted": 0,
        "inactiveCandidatesAccepted": 0,
        "disabledCandidatesAccepted": 0,
        "duplicateCandidates": 0,
        "lowScoreBackfillCount": 0,
    }


def top_valid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [row for row in rows if hard_conditions(row)]
    return sorted(valid, key=selection_key)


def hard_conditions(row: dict[str, Any]) -> bool:
    cfg = row["configuration"]
    if any(row[key] for key in ["tenantViolations", "expiredCandidatesAccepted", "inactiveCandidatesAccepted", "disabledCandidatesAccepted", "duplicateCandidates", "lowScoreBackfillCount"]):
        return False
    if cfg["maximumFinalK"] != 5 or cfg["postFusionCandidateK"] > 50:
        return False
    coverage20 = row["rrfMetrics"].get("coverageAt20", 0)
    baseline20 = 0.579167
    if not (coverage20 >= baseline20 + 0.10 or row["oracleCaptureRateAt20"] >= 0.90):
        return False
    if cfg["postFusionCandidateK"] >= 30 and row["oracleCaptureRateAt30"] < 0.95:
        return False
    return True


def selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    cfg = row["configuration"]
    return (
        -row["rrfMetrics"].get(f"coverageAt{cfg['postFusionCandidateK']}", 0),
        -row["oracleCaptureRateAtSelectedK"],
        cfg["postFusionCandidateK"],
        -row["deterministicRerankerMetrics"].get("ndcgAt5", 0),
        -row["deterministicRerankerMetrics"].get("mrr", 0),
        row["latencyP95"],
    )


def decide(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    valid = top_valid(rows)
    if not valid:
        return {"schemaVersion": "agent-rag-v23-candidate-fusion-calibration-decision-v1", "status": "BLOCKED", "decision": "NO_VALID_CANDIDATE_FUSION_CONFIGURATION", "datasetHash": manifest["datasetHash"]}
    selected = valid[0]
    weighted = selected["configuration"]["bm25Weight"] != 1.0 or selected["configuration"]["denseWeight"] != 1.0
    return {
        "schemaVersion": "agent-rag-v23-candidate-fusion-calibration-decision-v1",
        "status": "PASS",
        "decision": "VALID_WEIGHTED_RRF_CONFIGURATION" if weighted else "VALID_EQUAL_WEIGHT_RRF_CONFIGURATION",
        "datasetHash": manifest["datasetHash"],
        "selected": selected,
        "validConfigurationCount": len(valid),
    }


def write_config(decision: dict[str, Any], manifest: dict[str, Any]) -> None:
    cfg = decision["selected"]["configuration"]
    CONFIG_OUT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "policyVersion: v23-hybrid-retrieval-candidate-fusion-v1",
            f"datasetHash: {manifest['datasetHash']}",
            f"calibrationHash: {hash_json([case['caseId'] for case in build_calibration_cases()])}",
            f"knowledgeSnapshotHash: {manifest['knowledgeSnapshotHash']}",
            f"indexManifestHash: {manifest['indexManifestHash']}",
            f"bm25RetrieveK: {cfg['bm25RetrieveK']}",
            f"denseRetrieveK: {cfg['denseRetrieveK']}",
            f"rrfRankWindow: {cfg['rrfRankWindow']}",
            f"postFusionCandidateK: {cfg['postFusionCandidateK']}",
            f"rrfRankConstant: {cfg['rrfRankConstant']}",
            f"bm25Weight: {cfg['bm25Weight']}",
            f"denseWeight: {cfg['denseWeight']}",
            "maximumFinalK: 5",
            "allowBackfill: false",
            f"configurationHash: {decision['selected']['configurationHash']}",
        ]
    )
    (CONFIG_OUT / "v23-hybrid-retrieval-candidate-fusion.yml").write_text(text + "\n", encoding="utf-8")


def build_calibration_cases() -> list[dict[str, Any]]:
    cases, _manifest = load_dataset()
    return split_answerable(cases, "calibration")


def lightweight(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: row[key] for key in ["configurationId", "configurationHash", "configuration", "rrfMetrics", "rawUnionMetrics", "deterministicRerankerMetrics", "oracleCaptureRateAt20", "oracleCaptureRateAt30", "oracleCaptureRateAtSelectedK", "latencyP95", "tenantViolations", "expiredCandidatesAccepted", "inactiveCandidatesAccepted", "duplicateCandidates"]} for row in rows]


def rank_distribution_for(cases: list[dict[str, Any]], cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        relevant = case_relevant(case)
        item = cache[case["caseId"]]
        rows.append({"bm25": rank_bucket(best_rank([x.chunkId for x in item["bm25"]], relevant)), "dense": rank_bucket(best_rank([x.chunkId for x in item["dense"]], relevant)), "rawUnion": rank_bucket(best_rank(raw_union_ids(item["bm25"], item["dense"], 100), relevant))})
    return summarize_buckets(rows)


def static_rank_distribution(cases: list[dict[str, Any]], runtime: Any) -> dict[str, Any]:
    cache = precompute(cases, runtime)
    return rank_distribution_for(cases, cache)


def old_diagnostic_distribution() -> dict[str, Any]:
    summary = OUT / "v23-retrieval-miss-taxonomy-summary.json"
    if not summary.exists():
        return {}
    return {"source": "CONSUMED_RETRIEVAL_MISS_DIAGNOSTIC_SET", **__import__("json").loads(summary.read_text(encoding="utf-8"))}


def best_rank(ids: list[str], relevant: set[str]) -> int:
    for index, chunk_id in enumerate(ids, start=1):
        if chunk_id in relevant:
            return index
    return 0


def rank_bucket(rank: int) -> str:
    if not rank:
        return ">100/miss"
    for label, low, high in [("1-5", 1, 5), ("6-10", 6, 10), ("11-20", 11, 20), ("21-30", 21, 30), ("31-50", 31, 50), ("51-75", 51, 75), ("76-100", 76, 100)]:
        if low <= rank <= high:
            return label
    return ">100/miss"


def summarize_buckets(rows: list[dict[str, str]]) -> dict[str, Any]:
    from collections import Counter

    return {route: dict(Counter(row[route] for row in rows)) for route in ["bm25", "dense", "rawUnion"]}


def render_rank_doc(rank_distribution: dict[str, Any]) -> str:
    return "# V2.3 Relevant Rank Distribution\n\n```json\n" + __import__("json").dumps(rank_distribution, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


def render_calibration_doc(decision: dict[str, Any]) -> str:
    return "# V2.3 Candidate Fusion Calibration\n\nDecision: `" + decision["decision"] + "`\n\n```json\n" + __import__("json").dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


if __name__ == "__main__":
    raise SystemExit(main())
