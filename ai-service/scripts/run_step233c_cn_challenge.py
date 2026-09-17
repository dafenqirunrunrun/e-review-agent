from __future__ import annotations

import argparse
import gc
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agentic_workflow.workflow import IntentRouterAgent
from app.contracts.review_semantics import risk_type_severity
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.reflection import PolicyReflectionEngine
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.schemas.review import ReviewAnalyzeRequest
from scripts.build_step233c_cn_challenge import DEFAULT_CHUNKS, DEFAULT_MANIFEST, DEFAULT_OUTPUT as DEFAULT_DATASET
from scripts.run_step16_benchmark import load_jsonl
from scripts.run_step233a_qwen_embedding_ab import (
    DEFAULT_V1_INDEX_DIR,
    DEFAULT_V2_INDEX_DIR,
    active_index_hashes,
    build_bm25_rankings,
    content_root_hash,
    current_config,
    release_provider,
    sha256_file,
)
from scripts.run_step233b_ranking_recovery import (
    DEFAULT_RERANKER,
    candidate_embedding_config,
    dense_rankings,
    encoding_matches_index,
    load_index_meta,
    load_reranker,
    passage_text,
    release_reranker,
    safe_provider_metadata,
    weighted_rrf,
)
from app.policy_rag.embedding import QwenOfficialTransformersEmbeddingProvider


DEFAULT_RESULT = ROOT / "artifacts" / "step233c" / "cn_independent_challenge.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen Chinese Step 23.3C independent ranking challenge.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--v1-index-dir", type=Path, default=DEFAULT_V1_INDEX_DIR)
    parser.add_argument("--v2-index-dir", type=Path, default=DEFAULT_V2_INDEX_DIR)
    parser.add_argument("--reranker-model", type=Path, default=DEFAULT_RERANKER)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--embedding-batch-size", type=int, default=4)
    parser.add_argument("--reranker-batch-size", type=int, default=8)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    manifest_path = args.manifest.resolve()
    chunks_path = args.chunks.resolve()
    v1_dir = args.v1_index_dir.resolve()
    v2_dir = args.v2_index_dir.resolve()
    reranker_path = args.reranker_model.resolve()
    if v1_dir == v2_dir:
        raise SystemExit("STEP233C_INDEX_ISOLATION_FAILED")
    if args.embedding_batch_size < 1 or args.reranker_batch_size < 1:
        raise SystemExit("STEP233C_BATCH_SIZE_INVALID")

    manifest = assert_frozen_dataset(dataset, manifest_path)
    assert_reranker_ready(reranker_path)
    all_cases = load_jsonl(dataset)
    cases = [case for case in all_cases if case.get("policyRelevance")]
    chunks = load_policy_chunks(chunks_path)
    if len(all_cases) != 120 or len(cases) != 105 or len(chunks) != 71:
        raise SystemExit("STEP233C_INPUT_COUNT_MISMATCH")

    expected_root = content_root_hash(chunks)
    if expected_root != manifest["validation"]["contentRootHash"]:
        raise SystemExit("STEP233C_CORPUS_CHANGED_AFTER_FREEZE")
    active_before = active_index_hashes(v1_dir)
    candidate_before = active_index_hashes(v2_dir)
    v1_meta = load_index_meta(v1_dir, expected_root, "v1")
    v2_meta = load_index_meta(v2_dir, expected_root, "v2")

    queries = [
        " ".join([case["reviewText"], PolicyEvidenceRetriever._expand_risk_hints(case["riskTypes"])]).strip()
        for case in cases
    ]
    bm25_rankings = build_bm25_rankings(chunks, cases)
    config = current_config(batch_size=args.embedding_batch_size)

    from scripts.run_step233b_ranking_recovery import create_legacy_provider

    v1_provider = create_legacy_provider(config)
    v1_dense, v1_embedding_ms = dense_rankings(v1_provider, v1_dir, chunks, queries)
    release_provider(v1_provider)

    v2_provider = QwenOfficialTransformersEmbeddingProvider(candidate_embedding_config(config, v2_meta))
    v2_dense, v2_embedding_ms = dense_rankings(v2_provider, v2_dir, chunks, queries)
    v2_provider_meta = safe_provider_metadata(v2_provider.metadata())
    candidate_encoding_matches = encoding_matches_index(v2_provider_meta, v2_meta.get("provider", {}))
    release_provider(v2_provider)

    v1_rankings = [weighted_rrf(bm25, dense, top_k=5) for bm25, dense in zip(bm25_rankings, v1_dense, strict=True)]
    b0_rankings = [weighted_rrf(bm25, dense, top_k=5) for bm25, dense in zip(bm25_rankings, v2_dense, strict=True)]

    reranker, reranker_meta = load_reranker(reranker_path)
    b2_rankings, rerank_ms, pair_count = rerank_top_k(
        reranker,
        queries,
        b0_rankings,
        batch_size=args.reranker_batch_size,
    )
    release_reranker(reranker)
    del reranker
    gc.collect()

    variants = {
        "v1": evaluate_variant(v1_rankings, cases),
        "B0": evaluate_variant(b0_rankings, cases),
        "B2": evaluate_variant(b2_rankings, cases),
    }
    route_diagnostic = deterministic_route_diagnostic(all_cases)
    pairwise = paired_comparison(variants["v1"]["caseResults"], variants["B2"]["caseResults"])

    active_after = active_index_hashes(v1_dir)
    candidate_after = active_index_hashes(v2_dir)
    integrity = {
        "frozenDatasetUnchanged": sha256_file(dataset) == manifest["sha256"],
        "manifestFrozen": manifest.get("status") == "FROZEN",
        "labelsPrecedeCandidateExecution": bool(manifest.get("construction", {}).get("labelsAssignedBeforeCandidateExecution")),
        "activeIndexUntouched": active_before == active_after,
        "candidateIndexUntouched": candidate_before == candidate_after,
        "sameCorpus": v1_meta.get("contentRootHash") == v2_meta.get("contentRootHash") == expected_root,
        "candidateEncodingMatchesIndex": candidate_encoding_matches,
        "allQueriesChinese": all(case.get("language") == "zh" for case in all_cases),
    }
    promotion = promotion_gate(variants["v1"], variants["B2"], integrity)
    report = {
        "schemaVersion": "step23.3c-cn-independent-challenge-result-v1",
        "experimentGate": "PASS" if all(integrity.values()) else "FAIL",
        "promotionGate": promotion["status"],
        "evaluationScope": "Policy ranking plus deterministic Reflection and governance decision over annotated risk types; Router is diagnostic only.",
        "frozenDataset": {
            "version": manifest["datasetVersion"],
            "sha256": manifest["sha256"],
            "caseCount": len(all_cases),
            "rankingCaseCount": len(cases),
            "language": "zh",
        },
        "corpus": {"chunkCount": len(chunks), "contentRootHash": expected_root},
        "integrity": integrity,
        "runtime": {
            "v1EmbeddingMs": v1_embedding_ms,
            "v2EmbeddingMs": v2_embedding_ms,
            "rerankerMs": rerank_ms,
            "rerankerPairCount": pair_count,
        },
        "candidateProvider": v2_provider_meta,
        "reranker": {**reranker_meta, "pairCount": pair_count, "durationMs": rerank_ms},
        "variants": variants,
        "pairwiseB2VsV1": pairwise,
        "routeDiagnostic": route_diagnostic,
        "promotion": promotion,
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2))
    return 0 if report["experimentGate"] == "PASS" else 1


def assert_frozen_dataset(dataset: Path, manifest_path: Path) -> dict[str, Any]:
    if not dataset.exists() or not manifest_path.exists():
        raise SystemExit("STEP233C_FROZEN_DATASET_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    actual = sha256_file(dataset)
    if manifest.get("status") != "FROZEN":
        raise SystemExit("STEP233C_DATASET_NOT_FROZEN")
    if actual != manifest.get("sha256"):
        raise SystemExit(f"STEP233C_DATASET_HASH_MISMATCH expected={manifest.get('sha256')} actual={actual}")
    if manifest.get("language") != "zh":
        raise SystemExit("STEP233C_DATASET_LANGUAGE_MISMATCH")
    return manifest


def assert_reranker_ready(path: Path) -> None:
    required = (path / "config.json", path / "tokenizer.json", path / "model.safetensors")
    if not all(item.exists() for item in required):
        raise SystemExit("STEP233C_RERANKER_NOT_READY")


def rerank_top_k(
    model: Any,
    queries: list[str],
    rankings: list[list[tuple[float, Any]]],
    *,
    batch_size: int,
) -> tuple[list[list[tuple[float, Any]]], float, int]:
    pairs = [(query, passage_text(chunk)) for query, ranking in zip(queries, rankings, strict=True) for _, chunk in ranking]
    started = time.perf_counter()
    scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    if len(scores) != len(pairs):
        raise SystemExit("STEP233C_RERANKER_OUTPUT_SIZE_MISMATCH")
    output: list[list[tuple[float, Any]]] = []
    offset = 0
    for ranking in rankings:
        row_scores = scores[offset : offset + len(ranking)]
        offset += len(ranking)
        original = {chunk.chunkId: rank for rank, (_, chunk) in enumerate(ranking, start=1)}
        rescored = [(float(score), chunk) for score, (_, chunk) in zip(row_scores, ranking, strict=True)]
        rescored.sort(key=lambda item: (-item[0], original[item[1].chunkId], item[1].chunkId))
        output.append(rescored)
    return output, elapsed_ms, len(pairs)


def evaluate_variant(rankings: list[list[tuple[float, Any]]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [evaluate_case(case, ranking) for case, ranking in zip(cases, rankings, strict=True)]
    aggregate = aggregate_rows(rows)
    by_slice = {
        slice_name: aggregate_rows([row for row in rows if row["slice"] == slice_name])
        for slice_name in sorted({row["slice"] for row in rows})
    }
    bad_cases = [
        row for row in rows
        if not row["primaryAt1"] or not row["primaryInTop3"] or not row["reflectionCorrect"]
    ]
    return {"metrics": aggregate, "slices": by_slice, "badCases": bad_cases, "caseResults": rows}


def evaluate_case(case: dict[str, Any], ranking: list[tuple[float, Any]]) -> dict[str, Any]:
    qrels = {row["chunkId"]: row for row in case["policyRelevance"]}
    top_ids = [chunk.chunkId for _, chunk in ranking]
    relevances = [int(qrels.get(chunk_id, {}).get("relevance", 0)) for chunk_id in top_ids]
    primary_at_1 = bool(relevances and relevances[0] == 3)
    primary_in_top3 = 3 in relevances[:3]
    primary_in_top5 = 3 in relevances[:5]
    top3_support = {
        risk
        for chunk_id in top_ids[:3]
        for risk in qrels.get(chunk_id, {}).get("supports", [])
    }
    multi_risk_covered = set(case["riskTypes"]).issubset(top3_support)
    citation_valid = all(chunk.sourceUrl.startswith("http") and chunk.sectionPath and chunk.contentHash for _, chunk in ranking[:3])
    evidence = [
        PolicyEvidenceRetriever._to_result(chunk, score, rank=index, mode="evaluation_hybrid")
        for index, (score, chunk) in enumerate(ranking[:3], start=1)
    ]
    risk_level = expected_risk_level(case["riskTypes"])
    reflection = PolicyReflectionEngine().reflect(
        risk_level=risk_level,
        risk_types=case["riskTypes"],
        confidence=0.9,
        policy_evidence=evidence,
        action="suggest_action",
    )
    decision = governance_decision(risk_level, reflection.evidenceStatus)
    return {
        "caseId": case["caseId"],
        "slice": case["slice"],
        "riskTypes": case["riskTypes"],
        "primaryRiskType": case["primaryRiskType"],
        "primaryAt1": primary_at_1,
        "primaryInTop3": primary_in_top3,
        "primaryInTop5": primary_in_top5,
        "ndcgAt3": round(ndcg_at_k(relevances, [row["relevance"] for row in case["policyRelevance"]], 3), 6),
        "multiRisk": len(case["riskTypes"]) > 1,
        "multiRiskCoveredAt3": multi_risk_covered,
        "citationValid": citation_valid,
        "reflectionStatus": reflection.evidenceStatus,
        "reflectionCorrect": reflection.evidenceStatus == case["expectedEvidenceStatus"],
        "decision": decision,
        "decisionCorrect": decision == case["expectedDecision"],
        "top5": [
            {
                "rank": index,
                "chunkId": chunk.chunkId,
                "sourceName": chunk.sourceName,
                "clauseId": chunk.clauseId,
                "score": round(float(score), 6),
                "relevance": relevances[index - 1],
                "supports": qrels.get(chunk.chunkId, {}).get("supports", []),
            }
            for index, (score, chunk) in enumerate(ranking[:5], start=1)
        ],
        "expectedPrimaryChunks": sorted(row["chunkId"] for row in case["policyRelevance"] if row["relevance"] == 3),
        "unsupportedRiskTypes": reflection.unsupportedRiskTypes,
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"caseCount": 0}
    multi = [row for row in rows if row["multiRisk"]]
    high = [row for row in rows if expected_risk_level(row["riskTypes"]) == "high"]
    return {
        "caseCount": len(rows),
        "primaryPolicyAccuracyAt1": ratio(sum(row["primaryAt1"] for row in rows), len(rows)),
        "primaryPolicyRecallAt3": ratio(sum(row["primaryInTop3"] for row in rows), len(rows)),
        "candidateRecallAt5": ratio(sum(row["primaryInTop5"] for row in rows), len(rows)),
        "ndcgAt3": round(sum(row["ndcgAt3"] for row in rows) / len(rows), 4),
        "multiRiskCaseCount": len(multi),
        "multiRiskCoverageAt3": ratio(sum(row["multiRiskCoveredAt3"] for row in multi), len(multi)) if multi else None,
        "citationValidity": ratio(sum(row["citationValid"] for row in rows), len(rows)),
        "reflectionAccuracy": ratio(sum(row["reflectionCorrect"] for row in rows), len(rows)),
        "decisionAccuracy": ratio(sum(row["decisionCorrect"] for row in rows), len(rows)),
        "highRiskCaseCount": len(high),
        "highRiskPrimaryOmissionCount": sum(not row["primaryInTop3"] for row in high),
    }


def expected_risk_level(risk_types: list[str]) -> str:
    severities = {risk_type_severity(risk) for risk in risk_types}
    return "high" if "高" in severities else "medium" if "中" in severities else "low"


def governance_decision(risk_level: str, evidence_status: str) -> str:
    if evidence_status != "supported" or risk_level == "high":
        return "human_review"
    return "suggest_action"


def ndcg_at_k(observed: list[int], ideal_candidates: list[int], k: int) -> float:
    dcg = sum((2 ** relevance - 1) / math.log2(rank + 1) for rank, relevance in enumerate(observed[:k], start=1))
    ideal = sorted((int(value) for value in ideal_candidates), reverse=True)[:k]
    idcg = sum((2 ** relevance - 1) / math.log2(rank + 1) for rank, relevance in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


def paired_comparison(baseline: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = list(zip(baseline, candidate, strict=True))
    candidate_wins = sum(not left["primaryAt1"] and right["primaryAt1"] for left, right in pairs)
    baseline_wins = sum(left["primaryAt1"] and not right["primaryAt1"] for left, right in pairs)
    deltas = [right["ndcgAt3"] - left["ndcgAt3"] for left, right in pairs]
    low, high = bootstrap_mean_ci(deltas, seed=233, samples=2000)
    return {
        "caseCount": len(pairs),
        "primaryAt1": {
            "b2Wins": candidate_wins,
            "v1Wins": baseline_wins,
            "ties": len(pairs) - candidate_wins - baseline_wins,
            "mcnemarExactP": round(exact_two_sided_binomial(candidate_wins, baseline_wins), 6),
        },
        "ndcgAt3Delta": {
            "mean": round(sum(deltas) / len(deltas), 6),
            "bootstrap95PercentCI": [round(low, 6), round(high, 6)],
        },
    }


def exact_two_sided_binomial(left: int, right: int) -> float:
    n = left + right
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, index) for index in range(0, min(left, right) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def bootstrap_mean_ci(values: list[float], *, seed: int, samples: int) -> tuple[float, float]:
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    return means[int(samples * 0.025)], means[min(samples - 1, int(samples * 0.975))]


def deterministic_route_diagnostic(cases: list[dict[str, Any]]) -> dict[str, Any]:
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    rows = []
    for case in cases:
        payload = ReviewAnalyzeRequest(
            review_id=case["caseId"],
            product_id="STEP233C",
            product_name="中文挑战集商品",
            review_text=case["reviewText"],
            image_urls=[],
            rating=case["rating"],
            rating_source=case["ratingSource"],
        )
        decision = router._route_with_rules(payload)
        rows.append(
            {
                "caseId": case["caseId"],
                "expectedRoute": case["expectedRoute"],
                "actualRoute": decision.route,
                "correct": decision.route == case["expectedRoute"],
                "riskTypes": decision.risk_hints,
                "reasonCodes": decision.reason_codes,
            }
        )
    missed = [row for row in rows if not row["correct"]]
    return {
        "scope": "Current deterministic rules only; shared diagnostic and not a B2 promotion gate.",
        "caseCount": len(rows),
        "routeAccuracy": ratio(len(rows) - len(missed), len(rows)),
        "missCount": len(missed),
        "misses": missed,
    }


def promotion_gate(baseline: dict[str, Any], candidate: dict[str, Any], integrity: dict[str, bool]) -> dict[str, Any]:
    base = baseline["metrics"]
    current = candidate["metrics"]
    base_multi = baseline["slices"]["multi_risk_precedence"]
    current_multi = candidate["slices"]["multi_risk_precedence"]
    checks = {
        "integrity": all(integrity.values()),
        "primaryPolicyAccuracyAt1NoRegression": current["primaryPolicyAccuracyAt1"] >= base["primaryPolicyAccuracyAt1"],
        "ndcgAt3NoRegression": current["ndcgAt3"] >= base["ndcgAt3"],
        "multiRiskCoverageAt3NoRegression": current["multiRiskCoverageAt3"] >= base["multiRiskCoverageAt3"],
        "candidateRecallAt5NoRegression": current["candidateRecallAt5"] >= base["candidateRecallAt5"],
        "reflectionAccuracyNoRegression": current["reflectionAccuracy"] >= base["reflectionAccuracy"],
        "decisionAccuracyNoRegression": current["decisionAccuracy"] >= base["decisionAccuracy"],
        "highRiskPrimaryOmissionZero": current["highRiskPrimaryOmissionCount"] == 0,
        "citationValidityComplete": current["citationValidity"] == 1.0,
        "multiRiskPrimaryAt1NoRegression": current_multi["primaryPolicyAccuracyAt1"] >= base_multi["primaryPolicyAccuracyAt1"],
    }
    return {"status": "PASS" if all(checks.values()) else "HOLD", "checks": checks}


def report_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "experimentGate": report["experimentGate"],
        "promotionGate": report["promotionGate"],
        "frozenDataset": report["frozenDataset"],
        "metrics": {name: value["metrics"] for name, value in report["variants"].items()},
        "pairwiseB2VsV1": report["pairwiseB2VsV1"],
        "routeDiagnostic": {
            "routeAccuracy": report["routeDiagnostic"]["routeAccuracy"],
            "missCount": report["routeDiagnostic"]["missCount"],
        },
        "promotion": report["promotion"],
        "integrity": report["integrity"],
        "runtime": report["runtime"],
    }


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
