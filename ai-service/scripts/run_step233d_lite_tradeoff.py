from __future__ import annotations

import argparse
import gc
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.contracts.review_semantics import risk_type_severity
from app.policy_rag.embedding import QwenOfficialTransformersEmbeddingProvider
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.risk_priority import build_primary_evidence_query, prioritize_risks
from app.policy_rag.vector_store import DEFAULT_FAISS_META_NAME, DEFAULT_FAISS_NAME
from scripts.build_step233c_cn_challenge_v2 import (
    DEFAULT_CHUNKS,
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT as DEFAULT_DATASET,
)
from scripts.run_step16_benchmark import load_jsonl
from scripts.run_step233a_qwen_embedding_ab import (
    DEFAULT_V1_INDEX_DIR,
    DEFAULT_V2_INDEX_DIR,
    active_index_hashes,
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
from scripts.run_step233c_cn_challenge import rerank_top_k


DEFAULT_OUTPUT = ROOT / "artifacts" / "step233d" / "lite_tradeoff.json"
TARGETS = {
    "primaryPolicyRecallAt5": 0.90,
    "highRiskPrimaryOmissionReduction": 0.50,
    "conditionalRerankSaving": 0.20,
}


# Reflection deliberately accepts broad related tags. Primary ordering needs a
# narrower contract so a secondary rating tag cannot impersonate fake-review
# support (and vice versa).
PRIMARY_SUPPORT_TAGS = {
    "fake_review": {"fake_review", "fake_engagement"},
    "rating_manipulation": {"rating_manipulation", "incentivized_review", "paid_review"},
    "review_suppression": {"review_suppression"},
    "privacy_risk": {"privacy_risk", "privacy", "personal_information"},
    "after_sales_risk": {"after_sales_risk", "after_sales", "consumer_rights"},
    "safety_or_fraud_risk": {"safety_or_fraud_risk", "safety_or_fraud", "safety", "fraud"},
    "harassment_or_abuse": {"harassment_or_abuse", "harassment", "abuse"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Step 23.3D Lite primary-risk and reranker trade-off experiment.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--active-index-dir", type=Path, default=DEFAULT_V1_INDEX_DIR)
    parser.add_argument("--candidate-index-dir", type=Path, default=DEFAULT_V2_INDEX_DIR)
    parser.add_argument("--reranker-model", type=Path, default=DEFAULT_RERANKER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--embedding-batch-size", type=int, default=4)
    parser.add_argument("--reranker-batch-size", type=int, default=8)
    parser.add_argument("--latency-samples-per-slice", type=int, default=1)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    dataset_path = args.dataset.resolve()
    manifest_path = args.manifest.resolve()
    chunks_path = args.chunks.resolve()
    active_dir = args.active_index_dir.resolve()
    candidate_dir = args.candidate_index_dir.resolve()
    reranker_path = args.reranker_model.resolve()
    if args.embedding_batch_size < 1 or args.reranker_batch_size < 1 or args.latency_samples_per_slice < 0:
        raise SystemExit("STEP233D_INVALID_BATCH_OR_SAMPLE_SIZE")
    if active_dir == candidate_dir:
        raise SystemExit("STEP233D_INDEX_ISOLATION_FAILED")

    manifest = assert_diagnostic_dataset(dataset_path, manifest_path)
    assert_reranker_ready(reranker_path)
    all_cases = load_jsonl(dataset_path)
    cases = [case for case in all_cases if case.get("policyJudgments")]
    chunks = load_policy_chunks(chunks_path)
    if len(all_cases) != 120 or len(cases) != 95 or len(chunks) != 71:
        raise SystemExit("STEP233D_INPUT_COUNT_MISMATCH")

    expected_root = content_root_hash(chunks)
    if expected_root != manifest["validation"]["contentRootHash"]:
        raise SystemExit("STEP233D_CORPUS_CHANGED")
    active_before = active_index_hashes(active_dir)
    candidate_before = active_index_hashes(candidate_dir)
    candidate_meta = load_index_meta(candidate_dir, expected_root, "v2")

    decisions = [prioritize_risks(case["riskTypes"], case["reviewText"]) for case in cases]
    d0_queries = [
        " ".join([case["reviewText"], PolicyEvidenceRetriever._expand_risk_hints(case["riskTypes"])]).strip()
        for case in cases
    ]
    primary_queries = [build_primary_evidence_query(case["reviewText"], decision) for case, decision in zip(cases, decisions, strict=True)]

    d0_bm25, d0_bm25_ms = build_bm25_rankings(chunks, cases, d0_queries, [case["riskTypes"] for case in cases])
    primary_hints = [[decision.primary_risk_type] for decision in decisions]
    primary_bm25, primary_bm25_ms = build_bm25_rankings(chunks, cases, primary_queries, primary_hints)

    config = current_config(batch_size=args.embedding_batch_size)
    provider = QwenOfficialTransformersEmbeddingProvider(candidate_embedding_config(config, candidate_meta))
    warmup_started = time.perf_counter()
    provider.embed_queries([primary_queries[0]])
    embedding_warmup_ms = elapsed_ms(warmup_started)
    d0_dense, d0_embedding_ms = dense_rankings(provider, candidate_dir, chunks, d0_queries)
    primary_dense, primary_embedding_ms = dense_rankings(provider, candidate_dir, chunks, primary_queries)
    provider_meta = safe_provider_metadata(provider.metadata())
    encoding_matches = encoding_matches_index(provider_meta, candidate_meta.get("provider", {}))

    d0_rankings = [weighted_rrf(bm25, dense, top_k=5) for bm25, dense in zip(d0_bm25, d0_dense, strict=True)]
    d1_rankings = [weighted_rrf(bm25, dense, top_k=5) for bm25, dense in zip(primary_bm25, primary_dense, strict=True)]

    reranker, reranker_meta = load_reranker(reranker_path)
    rerank_warmup_started = time.perf_counter()
    reranker.predict([(primary_queries[0], passage_text(d1_rankings[0][0][1]))], batch_size=1)
    rerank_warmup_ms = elapsed_ms(rerank_warmup_started)

    d0r_rankings, d0r_rerank_ms, d0r_pairs = rerank_top_k(
        reranker,
        d0_queries,
        d0_rankings,
        batch_size=args.reranker_batch_size,
    )
    d2_rankings, d2_rerank_ms, d2_pairs = rerank_top_k(
        reranker,
        primary_queries,
        d1_rankings,
        batch_size=args.reranker_batch_size,
    )
    conditional_mask = [
        should_conditionally_rerank(case, ranking, decision.primary_risk_type)
        for case, ranking, decision in zip(cases, d1_rankings, decisions, strict=True)
    ]
    d3_rankings, d3_rerank_ms, d3_pairs = rerank_conditionally(
        reranker,
        primary_queries,
        d1_rankings,
        conditional_mask,
        [decision.primary_risk_type for decision in decisions],
        batch_size=args.reranker_batch_size,
    )

    latency_cases = select_latency_cases(cases, args.latency_samples_per_slice)
    latency = measure_warm_latency(
        latency_cases=latency_cases,
        chunks=chunks,
        provider=provider,
        reranker=reranker,
        faiss_context=load_faiss_context(candidate_dir, chunks),
    )

    release_reranker(reranker)
    del reranker
    release_provider(provider)
    gc.collect()

    variants = {
        "D0": variant_record(
            "v2_equal_risk_hybrid",
            evaluate_variant(d0_rankings, cases),
            rerank_count=0,
            rerank_ms=0.0,
            pair_count=0,
            query_mode="all_risk_expansion",
        ),
        "D0R": variant_record(
            "v2_equal_risk_hybrid_always_rerank_top5",
            evaluate_variant(d0r_rankings, cases),
            rerank_count=len(cases),
            rerank_ms=d0r_rerank_ms,
            pair_count=d0r_pairs,
            query_mode="all_risk_expansion",
        ),
        "D1": variant_record(
            "primary_aware_hybrid",
            evaluate_variant(d1_rankings, cases),
            rerank_count=0,
            rerank_ms=0.0,
            pair_count=0,
            query_mode="predicted_primary_plus_secondary_labels",
        ),
        "D2": variant_record(
            "primary_aware_always_rerank_top5",
            evaluate_variant(d2_rankings, cases),
            rerank_count=len(cases),
            rerank_ms=d2_rerank_ms,
            pair_count=d2_pairs,
            query_mode="predicted_primary_plus_secondary_labels",
        ),
        "D3": variant_record(
            "primary_aware_conditional_guarded_rerank_top5",
            evaluate_variant(d3_rankings, cases),
            rerank_count=sum(conditional_mask),
            rerank_ms=d3_rerank_ms,
            pair_count=d3_pairs,
            query_mode="predicted_primary_plus_secondary_labels",
        ),
    }
    priority_quality = evaluate_priority(decisions, cases)
    tradeoff = choose_tradeoff(variants, priority_quality)

    active_after = active_index_hashes(active_dir)
    candidate_after = active_index_hashes(candidate_dir)
    integrity = {
        "diagnosticDatasetUnchanged": sha256_file(dataset_path) == manifest["dataset"]["sha256"],
        "diagnosticOnly": manifest.get("promotionEligible") is False,
        "humanAdjudicationPendingRecorded": manifest.get("humanAdjudication", {}).get("status") == "PENDING",
        "qrelsPartialRecorded": all(case.get("qrelCompleteness") == "pooled_partial" for case in cases),
        "activeIndexUntouched": active_before == active_after,
        "candidateIndexUntouched": candidate_before == candidate_after,
        "candidateEncodingMatchesIndex": encoding_matches,
        "onlineRuntimeUnchanged": True,
    }
    experiment_gate = "PASS" if all(integrity.values()) else "FAIL"
    report = {
        "schemaVersion": "step23.3d-lite-tradeoff-v1",
        "experimentGate": experiment_gate,
        "candidateGate": tradeoff["candidateGate"] if experiment_gate == "PASS" else "FAIL",
        "runtimePromotionGate": "HOLD",
        "runtimePromotionReason": "Candidate-exposed diagnostic qrels are partial and still await independent human adjudication.",
        "dataset": {
            "version": manifest["datasetVersion"],
            "sha256": manifest["dataset"]["sha256"],
            "caseCount": len(all_cases),
            "rankingCaseCount": len(cases),
            "normalBypassCount": len(all_cases) - len(cases),
            "promotionEligible": False,
        },
        "corpus": {"chunkCount": len(chunks), "contentRootHash": expected_root},
        "integrity": integrity,
        "priority": priority_quality,
        "provider": provider_meta,
        "reranker": {
            **reranker_meta,
            "warmupMs": rerank_warmup_ms,
            "alwaysPairCount": d2_pairs,
            "deconfoundedControlPairCount": d0r_pairs,
            "conditionalPairCount": d3_pairs,
        },
        "runtime": {
            "embeddingWarmupMs": embedding_warmup_ms,
            "d0Bm25Ms": d0_bm25_ms,
            "primaryBm25Ms": primary_bm25_ms,
            "d0BatchEmbeddingMs": d0_embedding_ms,
            "primaryBatchEmbeddingMs": primary_embedding_ms,
            "latencyMethod": "warm sequential component path over deterministic per-slice sample; excludes model loading and HTTP/agent overhead",
            "warmSequential": latency,
        },
        "variants": variants,
        "tradeoff": tradeoff,
        "targets": TARGETS,
        "limitations": [
            "The dataset reuses candidate-exposed texts and cannot authorize runtime promotion.",
            "Qrels cover only a judged pool; unjudged results are reported separately rather than treated as known irrelevant.",
            "Retrieval receives annotated risk types, so this is conditional retrieval quality, not end-to-end risk detection.",
            "Latency is measured locally on a small deterministic warm sample and is not a production SLO.",
        ],
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report_summary(report) if args.summary_only else report, ensure_ascii=False, indent=2))
    return 0 if experiment_gate == "PASS" else 1


def assert_diagnostic_dataset(dataset_path: Path, manifest_path: Path) -> dict[str, Any]:
    if not dataset_path.exists() or not manifest_path.exists():
        raise SystemExit("STEP233D_DIAGNOSTIC_DATASET_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("status") != "FROZEN_DIAGNOSTIC" or manifest.get("promotionEligible") is not False:
        raise SystemExit("STEP233D_DATASET_ROLE_INVALID")
    expected = manifest.get("dataset", {}).get("sha256")
    actual = sha256_file(dataset_path)
    if actual != expected:
        raise SystemExit(f"STEP233D_DATASET_HASH_MISMATCH expected={expected} actual={actual}")
    return manifest


def assert_reranker_ready(path: Path) -> None:
    required = (path / "config.json", path / "tokenizer.json", path / "model.safetensors")
    if not all(item.exists() for item in required):
        raise SystemExit("STEP233D_RERANKER_NOT_READY")


def build_bm25_rankings(
    chunks: list[Any],
    cases: list[dict[str, Any]],
    queries: list[str],
    risk_hints: list[list[str]],
) -> tuple[list[list[tuple[float, Any]]], float]:
    if not (len(cases) == len(queries) == len(risk_hints)):
        raise ValueError("STEP233D_BM25_INPUT_SIZE_MISMATCH")
    retriever = PolicyEvidenceRetriever(chunks)
    started = time.perf_counter()
    rankings = [
        retriever._bm25_search(query, hints, top_k=20)
        for query, hints in zip(queries, risk_hints, strict=True)
    ]
    return rankings, elapsed_ms(started)


def should_conditionally_rerank(case: dict[str, Any], ranking: list[tuple[float, Any]], primary_risk: str) -> bool:
    return len(case["riskTypes"]) > 1 or not ranking or not chunk_supports_risk(ranking[0][1], primary_risk)


def chunk_supports_risk(chunk: Any, risk: str) -> bool:
    available = set(chunk.riskTypes) | set(chunk.evidenceTags)
    return bool(available.intersection(PRIMARY_SUPPORT_TAGS.get(risk, {risk})))


def rerank_conditionally(
    model: Any,
    queries: list[str],
    rankings: list[list[tuple[float, Any]]],
    selected: list[bool],
    primary_risks: list[str],
    *,
    batch_size: int,
) -> tuple[list[list[tuple[float, Any]]], float, int]:
    selected_indexes = [index for index, enabled in enumerate(selected) if enabled]
    if not selected_indexes:
        return rankings, 0.0, 0
    selected_queries = [queries[index] for index in selected_indexes]
    selected_rankings = [rankings[index] for index in selected_indexes]
    rescored, duration_ms, pair_count = rerank_top_k(model, selected_queries, selected_rankings, batch_size=batch_size)
    output = [list(ranking) for ranking in rankings]
    for case_index, reranked in zip(selected_indexes, rescored, strict=True):
        primary = primary_risks[case_index]
        supported = [item for item in reranked if chunk_supports_risk(item[1], primary)]
        unsupported = [item for item in reranked if not chunk_supports_risk(item[1], primary)]
        output[case_index] = supported + unsupported if supported else reranked
    return output, duration_ms, pair_count


def evaluate_variant(rankings: list[list[tuple[float, Any]]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [evaluate_case(case, ranking) for case, ranking in zip(cases, rankings, strict=True)]
    return {
        "metrics": aggregate_rows(rows),
        "slices": {
            name: aggregate_rows([row for row in rows if row["slice"] == name])
            for name in sorted({row["slice"] for row in rows})
        },
        "badCases": [row for row in rows if not row["primaryAt1"] or not row["primaryInTop3"]],
        "caseResults": rows,
    }


def evaluate_case(case: dict[str, Any], ranking: list[tuple[float, Any]]) -> dict[str, Any]:
    judgments = {row["chunkId"]: row for row in case["policyJudgments"]}
    primary_ids = set(case["primaryPolicyChunkIds"])
    top_ids = [chunk.chunkId for _, chunk in ranking[:5]]
    primary_at_1 = bool(top_ids and top_ids[0] in primary_ids)
    primary_in_top3 = bool(primary_ids.intersection(top_ids[:3]))
    primary_in_top5 = bool(primary_ids.intersection(top_ids[:5]))
    judged_relevances = [judgments.get(chunk_id, {}).get("semanticRelevance") for chunk_id in top_ids]
    pooled_relevances = [int(value or 0) for value in judged_relevances]
    top3_support = {
        risk
        for chunk_id in top_ids[:3]
        for risk in judgments.get(chunk_id, {}).get("supports", [])
    }
    citation_valid = all(
        chunk.sourceUrl.startswith("http") and chunk.sectionPath and chunk.contentHash
        for _, chunk in ranking[:3]
    )
    high_risk = any(risk_type_severity(risk) == "高" for risk in case["riskTypes"])
    return {
        "caseId": case["caseId"],
        "slice": case["slice"],
        "riskTypes": case["riskTypes"],
        "primaryRiskType": case["primaryRiskType"],
        "primaryAt1": primary_at_1,
        "primaryInTop3": primary_in_top3,
        "primaryInTop5": primary_in_top5,
        "pooledNdcgAt3": round(ndcg_at_k(pooled_relevances, [row["semanticRelevance"] for row in case["policyJudgments"]], 3), 6),
        "unjudgedAt1": bool(top_ids and top_ids[0] not in judgments),
        "unjudgedCountAt3": sum(chunk_id not in judgments for chunk_id in top_ids[:3]),
        "multiRisk": len(case["riskTypes"]) > 1,
        "judgedMultiRiskCoverageAt3": set(case["riskTypes"]).issubset(top3_support),
        "citationValid": citation_valid,
        "highRisk": high_risk,
        "top5": [
            {
                "rank": rank,
                "chunkId": chunk.chunkId,
                "sourceName": chunk.sourceName,
                "clauseId": chunk.clauseId,
                "score": round(float(score), 6),
                "judged": chunk.chunkId in judgments,
                "semanticRelevance": judgments.get(chunk.chunkId, {}).get("semanticRelevance"),
                "supports": judgments.get(chunk.chunkId, {}).get("supports", []),
            }
            for rank, (score, chunk) in enumerate(ranking[:5], start=1)
        ],
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"caseCount": 0}
    multi = [row for row in rows if row["multiRisk"]]
    high = [row for row in rows if row["highRisk"]]
    return {
        "caseCount": len(rows),
        "primaryPolicyAccuracyAt1": ratio(sum(row["primaryAt1"] for row in rows), len(rows)),
        "primaryPolicyRecallAt3": ratio(sum(row["primaryInTop3"] for row in rows), len(rows)),
        "primaryPolicyRecallAt5": ratio(sum(row["primaryInTop5"] for row in rows), len(rows)),
        "pooledNdcgAt3": round(sum(row["pooledNdcgAt3"] for row in rows) / len(rows), 4),
        "unjudgedAt1Rate": ratio(sum(row["unjudgedAt1"] for row in rows), len(rows)),
        "unjudgedAt3Rate": ratio(sum(row["unjudgedCountAt3"] for row in rows), len(rows) * 3),
        "multiRiskCaseCount": len(multi),
        "judgedMultiRiskCoverageAt3": ratio(sum(row["judgedMultiRiskCoverageAt3"] for row in multi), len(multi)) if multi else None,
        "citationValidity": ratio(sum(row["citationValid"] for row in rows), len(rows)),
        "highRiskCaseCount": len(high),
        "highRiskPrimaryOmissionCount": sum(not row["primaryInTop3"] for row in high),
    }


def evaluate_priority(decisions: list[Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for decision, case in zip(decisions, cases, strict=True):
        acceptable = set(case["acceptablePrimaryRiskTypes"])
        rows.append(
            {
                "caseId": case["caseId"],
                "slice": case["slice"],
                "expected": case["primaryRiskType"],
                "acceptable": sorted(acceptable),
                "predicted": decision.primary_risk_type,
                "correct": decision.primary_risk_type in acceptable,
                "exact": decision.primary_risk_type == case["primaryRiskType"],
                "ambiguous": decision.ambiguous,
                "scores": decision.scores,
                "reasonCodes": decision.reason_codes,
            }
        )
    stable = [row for row, case in zip(rows, cases, strict=True) if not case["requiresAdjudication"]]
    return {
        "scope": "Orders annotated upstream risks only; does not detect new risks and does not read gold primary labels.",
        "caseCount": len(rows),
        "acceptableAccuracy": ratio(sum(row["correct"] for row in rows), len(rows)),
        "exactAccuracy": ratio(sum(row["exact"] for row in rows), len(rows)),
        "nonAdjudicationAccuracy": ratio(sum(row["correct"] for row in stable), len(stable)),
        "ambiguousCount": sum(row["ambiguous"] for row in rows),
        "misses": [row for row in rows if not row["correct"]],
    }


def variant_record(
    name: str,
    evaluation: dict[str, Any],
    *,
    rerank_count: int,
    rerank_ms: float,
    pair_count: int,
    query_mode: str,
) -> dict[str, Any]:
    case_count = evaluation["metrics"]["caseCount"]
    return {
        "name": name,
        "queryMode": query_mode,
        "rerank": {
            "invocationCount": rerank_count,
            "invocationRateGovernance": ratio(rerank_count, case_count),
            "invocationRateAllRequests": ratio(rerank_count, 120),
            "pairCount": pair_count,
            "batchDurationMs": rerank_ms,
            "batchAmortizedMsPerGovernanceRequest": round(rerank_ms / case_count, 2) if case_count else 0.0,
        },
        **evaluation,
    }


def choose_tradeoff(variants: dict[str, dict[str, Any]], priority: dict[str, Any]) -> dict[str, Any]:
    baseline = variants["D0"]["metrics"]
    checks = {}
    for name in ("D0R", "D1", "D2", "D3"):
        current = variants[name]["metrics"]
        checks[name] = {
            "top1NoRegression": current["primaryPolicyAccuracyAt1"] >= baseline["primaryPolicyAccuracyAt1"],
            "recallAt5NoRegression": current["primaryPolicyRecallAt5"] >= baseline["primaryPolicyRecallAt5"],
            "ndcgNoRegression": current["pooledNdcgAt3"] >= baseline["pooledNdcgAt3"],
            "multiRiskCoverageNoRegression": current["judgedMultiRiskCoverageAt3"] >= baseline["judgedMultiRiskCoverageAt3"],
            "highRiskOmissionsNoRegression": current["highRiskPrimaryOmissionCount"] <= baseline["highRiskPrimaryOmissionCount"],
            "citationValid": current["citationValidity"] == 1.0,
        }
    qualified = [name for name in ("D0R", "D1", "D2", "D3") if all(checks[name].values())]
    d2_count = variants["D0R"]["rerank"]["invocationCount"]
    d3_count = variants["D3"]["rerank"]["invocationCount"]
    saving = 1.0 - d3_count / d2_count if d2_count else 0.0

    selected = None
    best_quality = max(qualified, key=lambda name: quality_key(variants[name])) if qualified else None
    if "D3" in qualified and best_quality:
        best = variants[best_quality]["metrics"]
        d3 = variants["D3"]["metrics"]
        near_best_quality = (
            d3["primaryPolicyAccuracyAt1"] >= best["primaryPolicyAccuracyAt1"] - 0.01
            and d3["pooledNdcgAt3"] >= best["pooledNdcgAt3"] - 0.01
        )
        if near_best_quality and saving >= TARGETS["conditionalRerankSaving"]:
            selected = "D3"
    if selected is None:
        selected = best_quality

    candidate_checks = {}
    if selected:
        current = variants[selected]["metrics"]
        base_omissions = baseline["highRiskPrimaryOmissionCount"]
        omission_reduction = 1.0 - current["highRiskPrimaryOmissionCount"] / base_omissions if base_omissions else 1.0
        candidate_checks = {
            "priorityAccuracyAtLeast85Percent": priority["acceptableAccuracy"] >= 0.85,
            "primaryRecallAt5AtLeast90Percent": current["primaryPolicyRecallAt5"] >= TARGETS["primaryPolicyRecallAt5"],
            "highRiskOmissionsReducedByHalf": omission_reduction >= TARGETS["highRiskPrimaryOmissionReduction"],
            "baselineNoRegression": all(checks[selected].values()),
        }
    candidate_gate = "PASS_FOR_BLIND_VALIDATION" if selected and all(candidate_checks.values()) else "HOLD"
    return {
        "selectedDiagnosticVariant": selected,
        "candidateGate": candidate_gate,
        "runtimePromotionAllowed": False,
        "conditionalRerankSavingVsAlways": round(saving, 4),
        "variantChecksVsD0": checks,
        "candidateChecks": candidate_checks,
        "selectionRule": "Choose the strongest D0-qualified candidate; prefer D3 only when it stays within 1 point of the strongest Top-1/NDCG result and saves at least 20% of reranks.",
    }


def quality_key(variant: dict[str, Any]) -> tuple[float, ...]:
    metrics = variant["metrics"]
    return (
        metrics["primaryPolicyAccuracyAt1"],
        metrics["pooledNdcgAt3"],
        metrics["primaryPolicyRecallAt5"],
        metrics["judgedMultiRiskCoverageAt3"],
        -metrics["highRiskPrimaryOmissionCount"],
        -variant["rerank"]["invocationCount"],
    )


def select_latency_cases(cases: list[dict[str, Any]], per_slice: int) -> list[dict[str, Any]]:
    if per_slice == 0:
        return []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[case["slice"]].append(case)
    return [case for name in sorted(grouped) for case in grouped[name][:per_slice]]


def load_faiss_context(index_dir: Path, chunks: list[Any]) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    import faiss

    meta = json.loads((index_dir / DEFAULT_FAISS_META_NAME).read_text(encoding="utf-8-sig"))
    index = faiss.deserialize_index(np.frombuffer((index_dir / DEFAULT_FAISS_NAME).read_bytes(), dtype="uint8"))
    return index, meta, {chunk.chunkId: chunk for chunk in chunks}


def measure_warm_latency(
    *,
    latency_cases: list[dict[str, Any]],
    chunks: list[Any],
    provider: Any,
    reranker: Any,
    faiss_context: tuple[Any, dict[str, Any], dict[str, Any]],
) -> dict[str, Any]:
    if not latency_cases:
        return {"sampleCount": 0}
    retriever = PolicyEvidenceRetriever(chunks)
    measurements: dict[str, list[float]] = {name: [] for name in ("D0", "D0R", "D1", "D2", "D3")}
    d3_invocations = 0
    for case in latency_cases:
        decision = prioritize_risks(case["riskTypes"], case["reviewText"])
        d0_query = " ".join([case["reviewText"], retriever._expand_risk_hints(case["riskTypes"])]).strip()
        primary_query = build_primary_evidence_query(case["reviewText"], decision)
        for name in ("D0", "D0R", "D1", "D2", "D3"):
            query = d0_query if name in {"D0", "D0R"} else primary_query
            hints = case["riskTypes"] if name in {"D0", "D0R"} else [decision.primary_risk_type]
            started = time.perf_counter()
            ranking = rank_one(retriever, provider, faiss_context, query, hints)
            if name in {"D0R", "D2"}:
                ranking, _, _ = rerank_top_k(reranker, [query], [ranking], batch_size=5)
            elif name == "D3" and should_conditionally_rerank(case, ranking, decision.primary_risk_type):
                d3_invocations += 1
                ranking, _, _ = rerank_conditionally(
                    reranker,
                    [query],
                    [ranking],
                    [True],
                    [decision.primary_risk_type],
                    batch_size=5,
                )
            if not ranking:
                raise RuntimeError("STEP233D_LATENCY_RANKING_EMPTY")
            measurements[name].append(elapsed_ms(started))
    return {
        "sampleCount": len(latency_cases),
        "sampleCaseIds": [case["caseId"] for case in latency_cases],
        "d3RerankInvocationCount": d3_invocations,
        "variants": {name: latency_summary(values) for name, values in measurements.items()},
    }


def rank_one(
    retriever: PolicyEvidenceRetriever,
    provider: Any,
    faiss_context: tuple[Any, dict[str, Any], dict[str, Any]],
    query: str,
    risk_hints: list[str],
) -> list[tuple[float, Any]]:
    index, meta, chunk_by_id = faiss_context
    bm25 = retriever._bm25_search(query, risk_hints, top_k=20)
    vectors = provider.embed_queries([query])
    scores, positions = index.search(np.asarray(vectors, dtype="float32"), 20)
    dense = [
        (float(score), chunk_by_id[meta["rows"][int(position)]["chunkId"]])
        for score, position in zip(scores[0], positions[0], strict=True)
        if position >= 0
    ]
    return weighted_rrf(bm25, dense, top_k=5)


def latency_summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "meanMs": round(statistics.fmean(values), 2),
        "p50Ms": percentile(ordered, 0.50),
        "p95Ms": percentile(ordered, 0.95),
        "maxMs": round(max(values), 2),
    }


def percentile(ordered: list[float], fraction: float) -> float:
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return round(ordered[index], 2)


def ndcg_at_k(observed: list[int], ideal_candidates: list[int], k: int) -> float:
    dcg = sum((2 ** relevance - 1) / math.log2(rank + 1) for rank, relevance in enumerate(observed[:k], start=1))
    ideal = sorted((int(value) for value in ideal_candidates), reverse=True)[:k]
    idcg = sum((2 ** relevance - 1) / math.log2(rank + 1) for rank, relevance in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


def report_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "experimentGate": report["experimentGate"],
        "candidateGate": report["candidateGate"],
        "runtimePromotionGate": report["runtimePromotionGate"],
        "dataset": report["dataset"],
        "priority": {key: value for key, value in report["priority"].items() if key != "misses"},
        "metrics": {name: row["metrics"] for name, row in report["variants"].items()},
        "rerank": {name: row["rerank"] for name, row in report["variants"].items()},
        "warmSequential": report["runtime"]["warmSequential"],
        "tradeoff": report["tradeoff"],
        "integrity": report["integrity"],
        "limitations": report["limitations"],
    }


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
