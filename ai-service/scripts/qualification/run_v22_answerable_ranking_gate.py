from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for item in (AI_ROOT, SCRIPTS, AI_ROOT / "scripts" / "qualification"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.agent_rag.eligibility import ELIGIBILITY_VERSION, evaluate_evidence_eligibility  # noqa: E402
from app.agent_rag.metrics import macro_average, score_query  # noqa: E402
from app.agent_rag.reranker import GovernedReranker, RerankerConfig  # noqa: E402
from app.rag.document_contract import stable_hash  # noqa: E402
from run_v22_real_reranker_benchmark import (  # noqa: E402
    apply_asset_manifest,
    benchmark_payload,
    build_manifest,
    hash_ids,
    prepare_runtime,
)


OUT = ROOT / "artifacts" / "real-model-chain"
DOCS = ROOT / "docs" / "real-model-chain"
EVALUATION_TIME_UTC = "2026-07-22T00:00:00Z"
SELECTED = {"candidateK": 8, "maximumFinalK": 5, "batchSize": 8, "maxLength": 384}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        os.environ["AGENT_RAG_V22_ASSET_MANIFEST"] = args.asset_manifest
        apply_asset_manifest(Path(args.asset_manifest))
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    payload = benchmark_payload()
    manifest = build_manifest(payload)
    candidate_manifest, rows_by_case = build_candidate_pool_manifest(payload, manifest)
    write_json(OUT / "v22-answerability-canonical-candidate-pool-manifest.json", candidate_manifest)
    if candidate_manifest["status"] != "PASS":
        write_json(OUT / "v22-answerable-ranking-gate.json", blocked_gate(manifest, candidate_manifest, "CANONICAL_CANDIDATE_POOL_INVALID"))
        print("CANONICAL_CANDIDATE_POOL_INVALID")
        return 2

    ranking = run_answerable_ranking(payload, manifest, rows_by_case)
    write_json(OUT / "v22-answerable-ranking-gate.json", ranking)
    write_report(candidate_manifest, ranking)
    if ranking["decision"] == "ANSWERABLE_RANKING_IMPROVED":
        print("ANSWERABLE_RANKING_IMPROVED")
        return 0
    print("REAL_RERANKER_ANSWERABLE_RANKING_FAILED")
    print(ranking["decision"])
    print("MODEL_RERANKER_NOT_VERIFIED")
    print("AGENT_RAG_V22_REAL_MODEL_CHAIN_BLOCKED")
    return 2


def build_candidate_pool_manifest(payload: dict[str, Any], manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    provider, runtime = prepare_runtime(payload)
    rows_by_case: dict[str, list[Any]] = {}
    all_rows: list[dict[str, Any]] = []
    try:
        for case in payload["cases"]:
            rows, _trace = runtime.search(
                case["query"],
                tenant_id=case["tenantId"],
                mode="hybrid-real",
                sparse_top_k=20,
                dense_top_k=20,
                fusion_top_k=SELECTED["candidateK"],
                rerank_top_k=None,
                evaluation_time_utc=EVALUATION_TIME_UTC,
            )
            rows_by_case[case["caseId"]] = rows
            all_rows.append({"caseId": case["caseId"], "candidateIds": [item.chunkId for item in rows]})
    finally:
        try:
            provider.close()
        except Exception:
            pass
    flat = [item for values in rows_by_case.values() for item in values]
    counts = {
        "expiredCandidateCount": sum(_reason(item, item.tenantId) == "EXPIRED" for item in flat),
        "inactiveCandidateCount": sum(_reason(item, item.tenantId) in {"INACTIVE", "DISABLED"} for item in flat),
        "disabledCandidateCount": sum(_reason(item, item.tenantId) == "DISABLED" for item in flat),
        "tenantMismatchCount": sum(_reason(item, item.tenantId) in {"TENANT_MISMATCH", "TENANT_SCOPE_INVALID"} for item in flat),
        "notYetEffectiveCount": sum(_reason(item, item.tenantId) == "NOT_YET_EFFECTIVE" for item in flat),
    }
    candidate_pool_hash = stable_hash(
        {
            "version": "v22-answerability-canonical-candidate-pool-v1",
            "evaluationTimeUtc": EVALUATION_TIME_UTC,
            "rows": all_rows,
        }
    )
    return (
        {
            "schemaVersion": "agent-rag-v22-answerability-canonical-candidate-pool-manifest-v1",
            "candidatePoolVersion": "v22-answerability-canonical-candidate-pool-v1",
            "candidatePoolHash": candidate_pool_hash,
            "knowledgeSnapshotHash": manifest["knowledgeHash"],
            "benchmarkHash": manifest["benchmarkHash"],
            "evaluationTimeUtc": EVALUATION_TIME_UTC,
            "timezone": "UTC",
            "queryCount": len(payload["cases"]),
            "candidateCount": len(flat),
            "expiredRemoved": 0,
            "inactiveRemoved": 0,
            "disabledRemoved": 0,
            "tenantMismatchRemoved": 0,
            "notYetEffectiveRemoved": 0,
            "duplicateRemoved": 0,
            **counts,
            "status": "PASS" if all(value == 0 for value in counts.values()) else "FAIL",
        },
        rows_by_case,
    )


def run_answerable_ranking(payload: dict[str, Any], manifest: dict[str, Any], rows_by_case: dict[str, list[Any]]) -> dict[str, Any]:
    det = GovernedReranker(RerankerConfig(requested_type="deterministic", candidate_k=SELECTED["candidateK"], final_k=SELECTED["maximumFinalK"]))
    real = GovernedReranker(
        RerankerConfig(
            requested_type="local-model",
            model_path=os.getenv("RAG_RERANKER_MODEL_PATH", ""),
            model_name="BAAI/bge-reranker-v2-m3",
            device=os.getenv("RAG_RERANKER_DEVICE", "cuda"),
            use_fp16=True,
            batch_size=SELECTED["batchSize"],
            max_length=SELECTED["maxLength"],
            candidate_k=SELECTED["candidateK"],
            final_k=SELECTED["maximumFinalK"],
            timeout_ms=60000,
            real_required=True,
            provider_impl=os.getenv("RAG_RERANKER_PROVIDER_IMPL", "flagembedding"),
            normalize=True,
            model_id="BAAI/bge-reranker-v2-m3",
            model_revision="953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        )
    )
    rows = []
    retrieval_missed = []
    started_all = time.perf_counter()
    for case in payload["cases"]:
        if not case["relevantChunkIds"]:
            continue
        base = rows_by_case[case["caseId"]]
        relevant = set(case["relevantChunkIds"])
        present = relevant & {item.chunkId for item in base}
        valid_relevant = [chunk_id for chunk_id in case["relevantChunkIds"] if any(item.chunkId == chunk_id and _reason(item, case["tenantId"]) == "ELIGIBLE" for item in base)]
        if not present or not valid_relevant:
            retrieval_missed.append({"caseId": case["caseId"], "category": normalize_category(case["retrievalChallengeType"]), "expectedChunkIdsHash": hash_ids(case["relevantChunkIds"])})
            continue
        started = time.perf_counter()
        det_result = det.rerank(case["query"], base, top_k=SELECTED["maximumFinalK"], tenant_id=case["tenantId"], request_id=case["caseId"], evaluation_time_utc=EVALUATION_TIME_UTC)
        real_result = real.rerank(case["query"], base, top_k=SELECTED["maximumFinalK"], tenant_id=case["tenantId"], request_id=case["caseId"], evaluation_time_utc=EVALUATION_TIME_UTC)
        latency = round((time.perf_counter() - started) * 1000, 3)
        rows.append(score_row(case, base, det_result.candidates, real_result.candidates, latency, real_result))
    metrics = aggregate_rows(rows)
    decision = decision_for(metrics)
    return {
        "schemaVersion": "agent-rag-v22-answerable-ranking-gate-v1",
        "status": "PASS" if decision == "ANSWERABLE_RANKING_IMPROVED" else "BLOCKED",
        "decision": decision,
        "benchmarkHash": manifest["benchmarkHash"],
        "knowledgeHash": manifest["knowledgeHash"],
        "calibrationHash": manifest["calibrationHash"],
        "evaluationHash": manifest["evaluationHash"],
        "evaluationTimeUtc": EVALUATION_TIME_UTC,
        "selected": SELECTED,
        "answerableCases": sum(1 for case in payload["cases"] if case["relevantChunkIds"]),
        "retrievalEligibleAnswerableCases": len(rows),
        "retrievalMissedAnswerableCases": len(retrieval_missed),
        "retrievalMissedLight": retrieval_missed[:50],
        **metrics,
        "durationMs": round((time.perf_counter() - started_all) * 1000, 3),
    }


def score_row(case: dict[str, Any], hybrid: list[Any], det: list[Any], real: list[Any], latency_ms: float, real_result: Any) -> dict[str, Any]:
    relevant = set(case["relevantChunkIds"])
    hybrid_ids = [item.chunkId for item in hybrid[: SELECTED["maximumFinalK"]]]
    det_ids = [item.chunkId for item in det]
    real_ids = [item.chunkId for item in real]
    return {
        "caseId": case["caseId"],
        "category": normalize_category(case["retrievalChallengeType"]),
        "hybrid": score_mode(case, hybrid_ids),
        "deterministic": score_mode(case, det_ids),
        "real": score_mode(case, real_ids),
        "promotion": promotion_value(hybrid_ids, real_ids, relevant),
        "demotion": demotion_value(hybrid_ids, real_ids, relevant),
        "tenantViolation": any(item.tenantId not in {case["tenantId"], "__public__"} for item in real),
        "expiredEvidenceAccepted": any(_reason(item, case["tenantId"]) == "EXPIRED" for item in real),
        "identityMappingError": len({item.chunkId for item in real}) != len(real),
        "realRuntime": real_result.effectiveType == "local-model" and not real_result.fallbackUsed,
        "latencyMs": latency_ms,
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    subsets = {}
    for category in ["overall", "lexical", "semantic", "mixed", "temporal", "tenant-isolation"]:
        selected = rows if category == "overall" else [row for row in rows if row["category"] == category]
        subsets[category] = {
            "caseCount": len(selected),
            "hybrid": aggregate_mode([row["hybrid"] for row in selected]),
            "deterministic": aggregate_mode([row["deterministic"] for row in selected]),
            "real": aggregate_mode([row["real"] for row in selected]),
        }
    latencies = [row["latencyMs"] for row in rows]
    promotions = [row["promotion"] for row in rows if row["promotion"] is not None]
    demotions = [row["demotion"] for row in rows if row["demotion"] is not None]
    return {
        "subsets": subsets,
        "tenantViolations": sum(row["tenantViolation"] for row in rows),
        "expiredEvidenceAccepted": sum(row["expiredEvidenceAccepted"] for row in rows),
        "identityMappingErrors": sum(row["identityMappingError"] for row in rows),
        "realRuntimeExecutions": sum(row["realRuntime"] for row in rows),
        "relevantPromotionRate": round(sum(1 for value in promotions if value > 0) / max(1, len(promotions)), 6),
        "relevantDemotionRate": round(sum(1 for value in demotions if value > 0) / max(1, len(demotions)), 6),
        "latency": {"p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95)},
        "categoryCounts": dict(Counter(row["category"] for row in rows)),
    }


def decision_for(metrics: dict[str, Any]) -> str:
    if metrics["tenantViolations"] or metrics["expiredEvidenceAccepted"] or metrics["identityMappingErrors"]:
        return "ANSWERABLE_RANKING_REGRESSION"
    semantic_det = metrics["subsets"]["semantic"]["deterministic"]
    semantic_real = metrics["subsets"]["semantic"]["real"]
    overall_det = metrics["subsets"]["overall"]["deterministic"]
    overall_real = metrics["subsets"]["overall"]["real"]
    semantic_improved = semantic_real["ndcgAt5"] > semantic_det["ndcgAt5"] and semantic_real["mrr"] > semantic_det["mrr"]
    overall_no_regression = overall_real["ndcgAt5"] + 0.01 >= overall_det["ndcgAt5"] and overall_real["mrr"] + 0.01 >= overall_det["mrr"]
    if semantic_improved and overall_no_regression and metrics["relevantDemotionRate"] <= 0.5:
        return "ANSWERABLE_RANKING_IMPROVED"
    if overall_no_regression:
        return "ANSWERABLE_RANKING_PARITY"
    return "ANSWERABLE_RANKING_REGRESSION"


def score_mode(case: dict[str, Any], chunk_ids: list[str]) -> dict[str, float]:
    return score_query(
        retrieved_chunk_ids=chunk_ids,
        relevant_chunk_ids=set(case["relevantChunkIds"]),
        forbidden_chunk_ids=set(case["forbiddenChunkIds"]),
        relevance_grades=case["relevanceGrades"],
    )


def promotion_value(hybrid_ids: list[str], real_ids: list[str], relevant: set[str]) -> int | None:
    values = []
    for chunk_id in relevant:
        old = first_rank(hybrid_ids, chunk_id)
        new = first_rank(real_ids, chunk_id)
        if old and new:
            values.append(old - new)
    return max(values) if values else None


def demotion_value(hybrid_ids: list[str], real_ids: list[str], relevant: set[str]) -> int | None:
    value = promotion_value(hybrid_ids, real_ids, relevant)
    return -value if value is not None and value < 0 else 0 if value is not None else None


def aggregate_mode(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {"hitRateAt5": 0.0, "recallAt5": 0.0, "mrr": 0.0, "ndcgAt5": 0.0}
    return macro_average(rows, ["hitRateAt5", "recallAt5", "mrr", "ndcgAt5"])


def blocked_gate(manifest: dict[str, Any], candidate_manifest: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "schemaVersion": "agent-rag-v22-answerable-ranking-gate-v1",
        "status": "BLOCKED",
        "decision": "ANSWERABLE_RANKING_REGRESSION",
        "blockedReason": reason,
        "benchmarkHash": manifest["benchmarkHash"],
        "candidatePoolHash": candidate_manifest.get("candidatePoolHash", ""),
    }


def write_report(candidate_manifest: dict[str, Any], ranking: dict[str, Any]) -> None:
    path = DOCS / "V22_PHASE_87_ANSWERABLE_RANKING_REPORT.md"
    text = f"""# V2.2 Phase 8.7 Answerable Ranking Report

## Candidate Pool

- Candidate pool hash: `{candidate_manifest['candidatePoolHash']}`
- Query count: `{candidate_manifest['queryCount']}`
- Candidate count: `{candidate_manifest['candidateCount']}`
- Expired candidates: `{candidate_manifest['expiredCandidateCount']}`
- Inactive candidates: `{candidate_manifest['inactiveCandidateCount']}`
- Tenant mismatches: `{candidate_manifest['tenantMismatchCount']}`
- Status: `{candidate_manifest['status']}`

## Answerable-Only Ranking

- Decision: `{ranking['decision']}`
- Retrieval-eligible answerable cases: `{ranking['retrievalEligibleAnswerableCases']}`
- Retrieval-missed answerable cases: `{ranking['retrievalMissedAnswerableCases']}`
- Real runtime executions: `{ranking['realRuntimeExecutions']}`
- Tenant violations: `{ranking['tenantViolations']}`
- Expired evidence accepted: `{ranking['expiredEvidenceAccepted']}`
- Identity mapping errors: `{ranking['identityMappingErrors']}`

## Metrics

- Deterministic semantic nDCG@5: `{ranking['subsets']['semantic']['deterministic']['ndcgAt5']}`
- Real semantic nDCG@5: `{ranking['subsets']['semantic']['real']['ndcgAt5']}`
- Deterministic semantic MRR: `{ranking['subsets']['semantic']['deterministic']['mrr']}`
- Real semantic MRR: `{ranking['subsets']['semantic']['real']['mrr']}`
- Deterministic overall nDCG@5: `{ranking['subsets']['overall']['deterministic']['ndcgAt5']}`
- Real overall nDCG@5: `{ranking['subsets']['overall']['real']['ndcgAt5']}`
- Deterministic overall MRR: `{ranking['subsets']['overall']['deterministic']['mrr']}`
- Real overall MRR: `{ranking['subsets']['overall']['real']['mrr']}`

## Boundary

If the decision is not `ANSWERABLE_RANKING_IMPROVED`, balanced answerability benchmark v2 and runtime policy integration remain blocked.
"""
    path.write_text(text, encoding="utf-8")


def _reason(item: Any, tenant_id: str) -> str:
    return evaluate_evidence_eligibility(item, tenant_id, EVALUATION_TIME_UTC).reasonCode


def normalize_category(value: str) -> str:
    return "no-answer" if value == "negative/no-answer" else value


def first_rank(values: list[str], target: str) -> int:
    try:
        return values.index(target) + 1
    except ValueError:
        return 0


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = round((len(ordered) - 1) * fraction)
    return round(ordered[max(0, min(index, len(ordered) - 1))], 3)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
