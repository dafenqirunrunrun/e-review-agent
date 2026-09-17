from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for item in (AI_ROOT, SCRIPTS, AI_ROOT / "scripts" / "qualification"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.agent_rag.metrics import macro_average, score_query  # noqa: E402
from app.agent_rag.reranker import GovernedReranker, RerankerConfig  # noqa: E402
from run_v22_real_reranker_benchmark import benchmark_payload, build_manifest, prepare_runtime  # noqa: E402


OUT = ROOT / "artifacts" / "real-model-chain"
DOCS = ROOT / "docs" / "real-model-chain"
THRESHOLD_GRID = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
MARGIN_GRID = [0.00, 0.02, 0.05, 0.10, 0.15, 0.20]
POLICY_VERSION = "v22-reranker-rejection-v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    parser.add_argument("--phase", choices=["all", "calibration", "evaluation"], default="all")
    args = parser.parse_args()
    if args.asset_manifest:
        os.environ["AGENT_RAG_V22_ASSET_MANIFEST"] = args.asset_manifest
        apply_asset_manifest(Path(args.asset_manifest))

    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    lock_baseline()

    payload = benchmark_payload()
    manifest = build_manifest(payload)
    assert_frozen_hashes(manifest)
    selected = read_json(OUT / "v22-real-reranker-benchmark-summary.json").get("selected") or {"candidateK": 8, "finalK": 5, "batchSize": 8, "maxLength": 384}
    calibration_rows = collect_rows(payload, payload["split"]["calibration"], selected)
    evaluation_rows = collect_rows(payload, payload["split"]["evaluation"], selected)
    audit = build_false_evidence_audit(manifest, evaluation_rows, selected)
    write_json(OUT / "v22-reranker-false-evidence-audit.json", audit)

    calibration = calibrate_policy(manifest, calibration_rows, selected)
    write_json(OUT / "v22-reranker-rejection-calibration-decision.json", calibration)
    if calibration["status"] != "PASS":
        write_markdown(DOCS / "V22_PHASE_85_REJECTION_CALIBRATION_REPORT.md", render_report(audit, calibration, None))
        print("NO_VALID_REJECTION_POLICY")
        print("MODEL_RERANKER_NOT_VERIFIED")
        return 2

    evaluation = evaluate_policy(manifest, evaluation_rows, calibration["selectedPolicy"], selected)
    write_json(OUT / "v22-reranker-rejection-evaluation-summary.json", evaluation)
    write_policy_config(calibration["selectedPolicy"])
    write_markdown(DOCS / "V22_PHASE_85_REJECTION_CALIBRATION_REPORT.md", render_report(audit, calibration, evaluation))
    if evaluation["status"] == "PASS":
        print("AGENT_RAG_V22_REAL_RERANKER_REJECTION_PASS")
        print(evaluation["qualityDecision"])
        return 0
    print(evaluation["qualityDecision"])
    print(evaluation["modelBoundary"])
    return 2


def lock_baseline() -> None:
    files = {
        "llmGateSha256": OUT / "v22-real-llm-gate.json",
        "oldSoakSha256": OUT / "v22-real-model-soak-summary.json",
        "oldE2eSha256": OUT / "v22-real-model-chain-e2e-summary.json",
        "markerGateSha256": OUT / "v22-real-marker-regression-gate.json",
        "adminLintGateSha256": OUT / "v22-admin-lint-regression-gate.json",
        "rerankerBenchmarkSha256": OUT / "v22-real-reranker-benchmark-summary.json",
    }
    assets = read_json(OUT / "model-assets-summary.json").get("assets", {})
    manifest = read_json(OUT / "v22-reranker-benchmark-manifest.json")
    payload = {
        "schemaVersion": "agent-rag-v22-phase85-evidence-baseline-lock-v1",
        "createdAtUtc": now(),
        "baselineCommit": "1dfa8359",
        "rerankerModelId": assets.get("reranker", {}).get("modelId"),
        "rerankerRevision": assets.get("reranker", {}).get("revision"),
        "rerankerFingerprint": assets.get("reranker", {}).get("assetFingerprint"),
        "benchmarkHash": manifest.get("benchmarkHash"),
        "knowledgeHash": manifest.get("knowledgeHash"),
        "calibrationHash": manifest.get("calibrationHash"),
        "evaluationHash": manifest.get("evaluationHash"),
        "evidenceHashes": {name: sha256(path) for name, path in files.items() if path.exists()},
        "notes": [
            "The old soak proves stability of the always-return-top-k runtime only.",
            "If a formal evidence rejection policy is integrated into runtime, E2E and 1800-second soak must be rerun.",
            "Local asset paths are intentionally omitted.",
        ],
    }
    write_markdown(
        DOCS / "V22_PHASE_85_EVIDENCE_BASELINE_LOCK.md",
        "# V2.2 Phase 8.5 Evidence Baseline Lock\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )


def collect_rows(payload: dict[str, Any], cases: list[dict[str, Any]], selected: dict[str, Any]) -> list[dict[str, Any]]:
    provider, runtime = prepare_runtime(payload)
    try:
        real = GovernedReranker(
            RerankerConfig(
                requested_type="local-model",
                model_path=os.getenv("RAG_RERANKER_MODEL_PATH", ""),
                model_name="BAAI/bge-reranker-v2-m3",
                device=os.getenv("RAG_RERANKER_DEVICE", "cuda"),
                use_fp16=True,
                batch_size=int(selected["batchSize"]),
                max_length=int(selected["maxLength"]),
                candidate_k=int(selected["candidateK"]),
                final_k=int(selected["candidateK"]),
                timeout_ms=60000,
                real_required=True,
                provider_impl=os.getenv("RAG_RERANKER_PROVIDER_IMPL", "flagembedding"),
                normalize=True,
                model_id="BAAI/bge-reranker-v2-m3",
                model_revision="953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
            )
        )
        rows = []
        for case in cases:
            started = time.perf_counter()
            base, _trace = runtime.search(
                case["query"],
                tenant_id=case["tenantId"],
                mode="hybrid-real",
                sparse_top_k=20,
                dense_top_k=20,
                fusion_top_k=int(selected["candidateK"]),
                rerank_top_k=None,
            )
            result = real.rerank(case["query"], base, top_k=int(selected["candidateK"]), tenant_id=case["tenantId"], request_id=case["caseId"])
            rows.append(
                {
                    "caseId": case["caseId"],
                    "category": normalize_category(case["retrievalChallengeType"]),
                    "tenantIdHash": stable(case["tenantId"]),
                    "isNoAnswerCase": case["retrievalChallengeType"] == "negative/no-answer",
                    "expectedRelevantCount": len(case["relevantChunkIds"]),
                    "expectedChunkIdsHash": hash_ids(case["relevantChunkIds"]),
                    "candidateCount": len(base),
                    "candidatePoolContainsRelevantEvidence": bool(set(case["relevantChunkIds"]) & {item.chunkId for item in base}),
                    "relevantOriginalRanks": [first_rank([item.chunkId for item in base], chunk_id) for chunk_id in case["relevantChunkIds"]],
                    "reranked": [
                        {
                            "chunkId": item.chunkId,
                            "normalizedRelevanceScore": float(score),
                            "rawRank": int(item.rawRank or 0),
                            "tenantAllowed": item.tenantId in {case["tenantId"], "__public__", ""},
                            "active": not bool((item.row or {}).get("deleted", False)) and bool((item.row or {}).get("active", True)),
                            "expired": bool((item.row or {}).get("effective_to") or (item.row or {}).get("effectiveTo")),
                            "isRelevant": item.chunkId in set(case["relevantChunkIds"]),
                        }
                        for item, score in zip(result.candidates, result.scores, strict=True)
                    ],
                    "latencyMs": round((time.perf_counter() - started) * 1000, 3),
                    "realRuntime": result.effectiveType == "local-model" and not result.fallbackUsed,
                }
            )
        return rows
    finally:
        try:
            provider.close()
        except Exception:
            pass


def build_false_evidence_audit(manifest: dict[str, Any], rows: list[dict[str, Any]], selected: dict[str, Any]) -> dict[str, Any]:
    no_answer_false = []
    final_rows = [row["reranked"][: int(selected["finalK"])] for row in rows]
    accepted_tenant_violations = sum(1 for returned in final_rows for item in returned if not item["tenantAllowed"])
    accepted_inactive_evidence = sum(1 for returned in final_rows for item in returned if not item["active"])
    accepted_expired_evidence = sum(1 for returned in final_rows for item in returned if item["expired"])
    for row in rows:
        returned = row["reranked"][: int(selected["finalK"])]
        if row["isNoAnswerCase"] and returned:
            no_answer_false.append(safe_case(row, returned, "NO_ANSWER_FORCED_TOP_K"))
    top1_no_answer = [row["reranked"][0]["normalizedRelevanceScore"] for row in rows if row["isNoAnswerCase"] and row["reranked"]]
    top1_answerable = [row["reranked"][0]["normalizedRelevanceScore"] for row in rows if not row["isNoAnswerCase"] and row["reranked"]]
    return {
        "schemaVersion": "agent-rag-v22-reranker-false-evidence-audit-v1",
        "createdAtUtc": now(),
        "benchmarkHash": manifest["benchmarkHash"],
        "calibrationHash": manifest["calibrationHash"],
        "evaluationHash": manifest["evaluationHash"],
        "falseEvidenceTotal": len(no_answer_false) * int(selected["finalK"]),
        "falseEvidenceCaseCount": len(no_answer_false),
        "allFalseEvidenceFromNoAnswerCases": True,
        "noAnswerCaseTotal": sum(1 for row in rows if row["isNoAnswerCase"]),
        "currentRuntimeAlwaysReturnsFinalK": True,
        "lowScoreBackfillToFinalK": True,
        "top1NoAnswerDistribution": distribution(top1_no_answer),
        "top1AnswerableDistribution": distribution(top1_answerable),
        "containsTenantInactiveExpiredIdentityIssue": bool(
            accepted_tenant_violations or accepted_inactive_evidence or accepted_expired_evidence
        ),
        "acceptedTenantViolationCount": accepted_tenant_violations,
        "acceptedInactiveEvidenceCount": accepted_inactive_evidence,
        "acceptedExpiredEvidenceCount": accepted_expired_evidence,
        "categoryCounts": dict(Counter(case["diagnosis"] for case in no_answer_false)),
        "cases": no_answer_false,
    }


def calibrate_policy(manifest: dict[str, Any], rows: list[dict[str, Any]], selected: dict[str, Any]) -> dict[str, Any]:
    det_baseline = metrics_for_rows(rows, int(selected["finalK"]), None)
    candidates = []
    for policy in policy_grid(rows):
        metrics = metrics_for_rows(rows, int(selected["finalK"]), policy)
        hard = hard_checks(metrics, det_baseline)
        candidates.append({"policy": policy, "metrics": metrics, "hardChecks": hard, "pass": all(hard.values())})
    passing = [item for item in candidates if item["pass"]]
    selected_policy = sorted(passing, key=policy_sort_key)[0] if passing else None
    result = {
        "schemaVersion": "agent-rag-v22-reranker-rejection-calibration-decision-v1",
        "createdAtUtc": now(),
        "status": "PASS" if selected_policy else "BLOCKED",
        "policyVersion": POLICY_VERSION,
        "modelId": "BAAI/bge-reranker-v2-m3",
        "revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        "scoreType": "normalized-relevance",
        "benchmarkHash": manifest["benchmarkHash"],
        "calibrationHash": manifest["calibrationHash"],
        "evaluationHash": manifest["evaluationHash"],
        "configurationHash": configuration_hash(selected),
        "baseline": det_baseline,
        "candidateCount": len(candidates),
        "passingCandidateCount": len(passing),
        "selectedPolicy": selected_policy["policy"] if selected_policy else None,
        "selectedMetrics": selected_policy["metrics"] if selected_policy else None,
        "blockedReasons": [] if selected_policy else ["NO_VALID_REJECTION_POLICY", "MODEL_RERANKER_NOT_VERIFIED"],
        "candidatesLight": light_candidates(candidates),
    }
    return result


def evaluate_policy(manifest: dict[str, Any], rows: list[dict[str, Any]], policy: dict[str, Any], selected: dict[str, Any]) -> dict[str, Any]:
    baseline = metrics_for_rows(rows, int(selected["finalK"]), None)
    metrics = metrics_for_rows(rows, int(selected["finalK"]), policy)
    checks = hard_checks(metrics, baseline)
    status = "PASS" if all(checks.values()) else "FAIL"
    quality = "AGENT_RAG_V22_REAL_RERANKER_QUALITY_IMPROVED" if status == "PASS" else "AGENT_RAG_V22_REAL_RERANKER_QUALITY_REGRESSION"
    return {
        "schemaVersion": "agent-rag-v22-reranker-rejection-evaluation-summary-v1",
        "createdAtUtc": now(),
        "status": status,
        "benchmarkHash": manifest["benchmarkHash"],
        "calibrationHash": manifest["calibrationHash"],
        "evaluationHash": manifest["evaluationHash"],
        "policy": policy,
        "baseline": baseline,
        "metrics": metrics,
        "hardChecks": checks,
        "qualityDecision": quality,
        "modelBoundary": "MODEL_RERANKER_VERIFIED" if status == "PASS" else "MODEL_RERANKER_NOT_VERIFIED",
    }


def metrics_for_rows(rows: list[dict[str, Any]], final_k: int, policy: dict[str, Any] | None) -> dict[str, Any]:
    scored_rows = []
    accepted_counts = []
    rejected_counts = []
    for row in rows:
        accepted = apply_policy(row, final_k, policy)
        accepted_counts.append(len(accepted))
        rejected_counts.append(max(0, len(row["reranked"]) - len(accepted)))
        scored_rows.append(
            {
                "caseId": row["caseId"],
                "category": row["category"],
                "isNoAnswerCase": row["isNoAnswerCase"],
                "accepted": accepted,
                "score": score_row(row, accepted),
                "tenantViolation": any(not item["tenantAllowed"] for item in accepted),
                "inactiveEvidenceLeak": any(not item["active"] for item in accepted),
                "expiredEvidenceLeak": any(item["expired"] for item in accepted),
                "falseEvidenceCount": len(accepted) if row["isNoAnswerCase"] else 0,
            }
        )
    subsets = {}
    for category in ["overall", "lexical", "semantic", "mixed", "temporal", "tenant-isolation", "no-answer"]:
        chosen = scored_rows if category == "overall" else [row for row in scored_rows if row["category"] == category]
        subsets[category] = {"caseCount": len(chosen), **aggregate_scores([row["score"] for row in chosen])}
    answerable = [row for row in scored_rows if not row["isNoAnswerCase"]]
    no_answer = [row for row in scored_rows if row["isNoAnswerCase"]]
    latencies = [float(row["latencyMs"]) for row in rows]
    return {
        "caseCount": len(rows),
        "subsets": subsets,
        "tenantViolations": sum(row["tenantViolation"] for row in scored_rows),
        "inactiveEvidenceLeaks": sum(row["inactiveEvidenceLeak"] for row in scored_rows),
        "expiredEvidenceLeaks": sum(row["expiredEvidenceLeak"] for row in scored_rows),
        "falseEvidenceCount": sum(row["falseEvidenceCount"] for row in scored_rows),
        "noAnswerCorrectRejection": round(sum(1 for row in no_answer if not row["accepted"]) / max(1, len(no_answer)), 4),
        "answerableAcceptanceRate": round(sum(1 for row in answerable if row["accepted"]) / max(1, len(answerable)), 4),
        "answerableRecallAt5": round(statistics.mean(row["score"]["recallAt5"] for row in answerable), 6) if answerable else 0.0,
        "falseNegativeCount": sum(1 for row in answerable if not row["accepted"]),
        "acceptedEvidenceCountDistribution": dict(Counter(str(value) for value in accepted_counts)),
        "averageEvidenceCount": round(statistics.mean(accepted_counts), 4) if accepted_counts else 0.0,
        "rejectedEvidenceCount": sum(rejected_counts),
        "latency": {"p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95)},
    }


def hard_checks(metrics: dict[str, Any], baseline: dict[str, Any]) -> dict[str, bool]:
    semantic = metrics["subsets"]["semantic"]
    base_semantic = baseline["subsets"]["semantic"]
    overall = metrics["subsets"]["overall"]
    base_overall = baseline["subsets"]["overall"]
    return {
        "tenantViolationsZero": metrics["tenantViolations"] == 0,
        "inactiveEvidenceLeaksZero": metrics["inactiveEvidenceLeaks"] == 0,
        "expiredEvidenceLeaksZero": metrics["expiredEvidenceLeaks"] == 0,
        "falseEvidenceZero": metrics["falseEvidenceCount"] == 0,
        "minimumAnswerableAcceptanceRate": metrics["answerableAcceptanceRate"] >= 0.95,
        "noAnswerCorrectRejectionNotBelowBaseline": metrics["noAnswerCorrectRejection"] >= baseline["noAnswerCorrectRejection"],
        "answerableRecallRegressionWithinLimit": metrics["answerableRecallAt5"] + 0.01 >= baseline["answerableRecallAt5"],
        "semanticNdcgImproved": semantic["ndcgAt5"] > base_semantic["ndcgAt5"],
        "semanticMrrImproved": semantic["mrr"] > base_semantic["mrr"],
        "overallNdcgRegressionWithinLimit": overall["ndcgAt5"] + 0.01 >= base_overall["ndcgAt5"],
        "overallMrrRegressionWithinLimit": overall["mrr"] + 0.01 >= base_overall["mrr"],
    }


def policy_grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = set(THRESHOLD_GRID)
    no_answer_top = sorted(row["reranked"][0]["normalizedRelevanceScore"] for row in rows if row["isNoAnswerCase"] and row["reranked"])
    answer_top = sorted(row["reranked"][0]["normalizedRelevanceScore"] for row in rows if not row["isNoAnswerCase"] and row["reranked"])
    for left, right in adjacent_pairs(no_answer_top + answer_top):
        values.add(round((left + right) / 2, 6))
    policies = [{"policyType": "absolute-threshold", "absoluteThreshold": value, "minimumMargin": None, "highConfidenceThreshold": None, "maximumFinalK": 5, "allowBackfillBelowThreshold": False} for value in sorted(values)]
    for threshold in sorted(values):
        for margin in MARGIN_GRID:
            policies.append(
                {
                    "policyType": "absolute-threshold-plus-ambiguity-margin",
                    "absoluteThreshold": threshold,
                    "minimumMargin": margin,
                    "highConfidenceThreshold": threshold,
                    "maximumFinalK": 5,
                    "allowBackfillBelowThreshold": False,
                }
            )
    return policies


def apply_policy(row: dict[str, Any], final_k: int, policy: dict[str, Any] | None) -> list[dict[str, Any]]:
    if policy is None:
        return row["reranked"][:final_k]
    threshold = float(policy["absoluteThreshold"])
    values = row["reranked"]
    if not values:
        return []
    if policy["policyType"] == "absolute-threshold-plus-ambiguity-margin" and len(values) > 1:
        top1 = values[0]["normalizedRelevanceScore"]
        top2 = values[1]["normalizedRelevanceScore"]
        if top1 < float(policy["highConfidenceThreshold"]) and top1 - top2 < float(policy["minimumMargin"]):
            return []
    return [item for item in values if item["normalizedRelevanceScore"] >= threshold][:final_k]


def score_row(row: dict[str, Any], accepted: list[dict[str, Any]]) -> dict[str, float]:
    if row["isNoAnswerCase"]:
        return {"hitRateAt5": 0.0, "recallAt5": 0.0, "mrr": 0.0, "ndcgAt5": 0.0}
    # The safe rows do not expose raw relevant ids beyond boolean flags; compute graded metrics
    # from preserved per-candidate relevance identity without leaking text.
    relevant_ids = {item["chunkId"] for item in row["reranked"] if item["isRelevant"]}
    return score_query(
        retrieved_chunk_ids=[item["chunkId"] for item in accepted],
        relevant_chunk_ids=relevant_ids,
        forbidden_chunk_ids=set(),
        relevance_grades={item["chunkId"]: 1.0 for item in row["reranked"] if item["isRelevant"]},
    )


def aggregate_scores(scores: list[dict[str, float]]) -> dict[str, float]:
    if not scores:
        return {"hitRateAt5": 0.0, "recallAt5": 0.0, "mrr": 0.0, "ndcgAt5": 0.0}
    return macro_average(scores, ["hitRateAt5", "recallAt5", "mrr", "ndcgAt5"])


def safe_case(row: dict[str, Any], returned: list[dict[str, Any]], diagnosis: str) -> dict[str, Any]:
    top1 = returned[0]["normalizedRelevanceScore"] if returned else None
    top2 = returned[1]["normalizedRelevanceScore"] if len(returned) > 1 else None
    return {
        "caseId": row["caseId"],
        "category": row["category"],
        "isNoAnswerCase": row["isNoAnswerCase"],
        "expectedRelevantCount": row["expectedRelevantCount"],
        "candidateCount": row["candidateCount"],
        "candidatePoolContainsRelevantEvidence": row["candidatePoolContainsRelevantEvidence"],
        "top1NormalizedScore": top1,
        "top2NormalizedScore": top2,
        "top1Top2Margin": round(top1 - top2, 8) if top1 is not None and top2 is not None else None,
        "acceptedEvidenceCount": len(returned),
        "returnedEvidenceCount": len(returned),
        "relevantOriginalRanks": row["relevantOriginalRanks"],
        "relevantRerankedRanks": [index + 1 for index, item in enumerate(row["reranked"]) if item["isRelevant"]],
        "diagnosis": diagnosis,
    }


def write_policy_config(policy: dict[str, Any]) -> None:
    path = ROOT / "config" / "qualification" / "v22-reranker-evidence-rejection-policy.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            f"policyVersion: {POLICY_VERSION}",
            "modelId: BAAI/bge-reranker-v2-m3",
            "modelRevision: 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
            "scoreType: normalized-relevance",
            f"policyType: {policy['policyType']}",
            f"absoluteThreshold: {policy['absoluteThreshold']}",
            f"minimumMargin: {policy.get('minimumMargin')}",
            f"highConfidenceThreshold: {policy.get('highConfidenceThreshold')}",
            "maximumFinalK: 5",
            "allowBackfillBelowThreshold: false",
            "noEvidenceDisposition: manual-review",
            "noEvidenceLlmPolicy: short-circuit",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def render_report(audit: dict[str, Any], calibration: dict[str, Any], evaluation: dict[str, Any] | None) -> str:
    selected = calibration.get("selectedPolicy")
    return f"""# V2.2 Phase 8.5 Rejection Calibration Report

## False Evidence Audit

- False evidence total: `{audit['falseEvidenceTotal']}`
- False evidence case count: `{audit['falseEvidenceCaseCount']}`
- All false evidence from no-answer cases: `{audit['allFalseEvidenceFromNoAnswerCases']}`
- No-answer case total: `{audit['noAnswerCaseTotal']}`
- Current runtime always returns finalK: `{audit['currentRuntimeAlwaysReturnsFinalK']}`
- Low-score backfill to finalK: `{audit['lowScoreBackfillToFinalK']}`
- Tenant/inactive/expired/identity issue present: `{audit['containsTenantInactiveExpiredIdentityIssue']}`
- Accepted tenant violations: `{audit.get('acceptedTenantViolationCount')}`
- Accepted inactive evidence count: `{audit.get('acceptedInactiveEvidenceCount')}`
- Accepted expired evidence count: `{audit.get('acceptedExpiredEvidenceCount')}`

## Calibration

- Status: `{calibration['status']}`
- Candidate policies tested: `{calibration['candidateCount']}`
- Passing policies: `{calibration['passingCandidateCount']}`
- Selected policy: `{json.dumps(selected, ensure_ascii=False, sort_keys=True) if selected else None}`
- Blocked reasons: `{', '.join(calibration.get('blockedReasons') or [])}`

## Evaluation

{json.dumps(evaluation, ensure_ascii=False, indent=2, sort_keys=True) if evaluation else 'No evaluation was run because calibration did not produce a valid policy.'}
"""


def light_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    light = []
    for item in candidates:
        metrics = item["metrics"]
        light.append(
            {
                "policy": item["policy"],
                "pass": item["pass"],
                "falseEvidenceCount": metrics["falseEvidenceCount"],
                "noAnswerCorrectRejection": metrics["noAnswerCorrectRejection"],
                "answerableAcceptanceRate": metrics["answerableAcceptanceRate"],
                "semanticNdcgAt5": metrics["subsets"]["semantic"]["ndcgAt5"],
                "semanticMrr": metrics["subsets"]["semantic"]["mrr"],
                "overallNdcgAt5": metrics["subsets"]["overall"]["ndcgAt5"],
                "overallMrr": metrics["subsets"]["overall"]["mrr"],
            }
        )
    return light[:200]


def policy_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    policy = item["policy"]
    metrics = item["metrics"]
    complexity = 0 if policy["policyType"] == "absolute-threshold" else 1
    return (
        complexity,
        metrics["falseEvidenceCount"],
        -metrics["answerableRecallAt5"],
        -metrics["subsets"]["semantic"]["ndcgAt5"],
        -metrics["subsets"]["semantic"]["mrr"],
        metrics["latency"]["p95"],
    )


def apply_asset_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    embedding = manifest.get("embedding") or {}
    reranker = manifest.get("reranker") or {}
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ["RAG_BGE_M3_MODEL_PATH"] = str(embedding.get("modelPath") or "")
    os.environ.setdefault("RAG_BGE_M3_DEVICE", "cuda")
    os.environ.setdefault("RAG_BGE_M3_PROVIDER_IMPL", "legacy-cls")
    os.environ.setdefault("RAG_BGE_M3_USE_FP16", "true")
    os.environ["RAG_RERANKER_MODEL_PATH"] = str(reranker.get("modelPath") or "")
    os.environ["RAG_RERANKER_TYPE"] = "local-model"
    os.environ.setdefault("RAG_RERANKER_PROVIDER_IMPL", "flagembedding")
    os.environ.setdefault("RAG_RERANKER_DEVICE", "cuda")
    os.environ["RAG_REAL_RERANKER_REQUIRED"] = "true"


def assert_frozen_hashes(manifest: dict[str, Any]) -> None:
    frozen = read_json(OUT / "v22-reranker-benchmark-manifest.json")
    for key in ["benchmarkHash", "knowledgeHash", "calibrationHash", "evaluationHash"]:
        if frozen.get(key) != manifest.get(key):
            raise SystemExit(f"FROZEN_{key}_MISMATCH")


def adjacent_pairs(values: list[float]) -> list[tuple[float, float]]:
    ordered = sorted(set(float(value) for value in values if math.isfinite(float(value))))
    return list(zip(ordered, ordered[1:]))


def distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    return {"count": len(values), "min": min(values), "p50": percentile(values, 0.5), "p95": percentile(values, 0.95), "max": max(values)}


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = round((len(ordered) - 1) * fraction)
    return round(ordered[max(0, min(index, len(ordered) - 1))], 6)


def configuration_hash(selected: dict[str, Any]) -> str:
    return stable({"policyVersion": POLICY_VERSION, "selected": selected})


def normalize_category(value: str) -> str:
    return "no-answer" if value == "negative/no-answer" else value


def first_rank(values: list[str], target: str) -> int:
    try:
        return values.index(target) + 1
    except ValueError:
        return 0


def hash_ids(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def stable(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
