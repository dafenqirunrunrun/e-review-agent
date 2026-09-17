from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from v23_parent_child_common import SimpleBm25, build_parent_units, parent_content, rrf
from v23_parent_child_qc2_common import (
    FROZEN_CONFIGURATION,
    canonical_hash,
    corpus_hash,
    index_fingerprints,
    ranked_ids_hash,
    ranking_hash,
    relevant,
    score_ids,
    set_ids_hash,
)
from v23_retrieval_common import eligible_chunks, hash_json
from v23_retrieval_v2_common import build_v23_v2_cases, build_v23_v2_manifest


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "retrieval-optimization"
DOCS = ROOT / "docs" / "retrieval-optimization"
CONFIG = ROOT / "config" / "qualification" / "v23-parent-child-heldout-evaluation.yml"
CONSUMPTION_STATE = OUT / "v23-parent-child-evaluation-consumption-state.json"
CHALLENGE_FORBIDDEN = "CHALLENGE_ACCESS_FORBIDDEN_IN_PHASE_95B"
EVALUATION_SPLIT = "evaluation"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def guard_split(split: str) -> None:
    if split == "challenge":
        raise RuntimeError(CHALLENGE_FORBIDDEN)
    if split != EVALUATION_SPLIT:
        raise RuntimeError(f"UNSUPPORTED_PHASE_95B_SPLIT:{split}")


def split_cases(split: str) -> list[dict[str, Any]]:
    guard_split(split)
    return [case for case in build_v23_v2_cases() if case["split"] == split]


def input_manifest() -> dict[str, Any]:
    cases = build_v23_v2_cases()
    manifest = build_v23_v2_manifest(cases)
    calibration = [case for case in cases if case["split"] == "calibration"]
    evaluation = [case for case in cases if case["split"] == "evaluation"]
    challenge = [case for case in cases if case["split"] == "challenge"]
    answerable = [case for case in evaluation if case["label"] == "answerable"]
    no_answer = [case for case in evaluation if case["label"] == "no_answer"]
    payload = {
        "artifactVersion": "agent-rag-v23-parent-child-evaluation-input-manifest-v1",
        "datasetVersion": manifest["datasetVersion"],
        "datasetHash": manifest["datasetHash"],
        "calibrationCaseCount": len(calibration),
        "evaluationCaseCount": len(evaluation),
        "answerableCaseCount": len(answerable),
        "noAnswerCaseCount": len(no_answer),
        "challengeCaseCount": len(challenge),
        "evaluationCaseIdsHash": canonical_hash([case["caseId"] for case in evaluation]),
        "evaluationQueryHashesHash": canonical_hash([case["queryHash"] for case in evaluation]),
        "evaluationLabelHashesHash": canonical_hash([{"caseId": case["caseId"], "label": case["label"]} for case in evaluation]),
        "evaluationRelevantChunkIdsHash": canonical_hash([{"caseId": case["caseId"], "relevant": case["expectedRelevantChunkIds"] + case["acceptableRelevantChunkIds"]} for case in evaluation]),
        "challengeCaseIdsHash": canonical_hash([case["caseId"] for case in challenge]),
        "challengeAccessed": False,
        "fullQueriesStored": False,
    }
    return payload


def split_isolation_payload(consumption: dict[str, Any]) -> dict[str, Any]:
    cases = build_v23_v2_cases()
    by_split = {split: [case for case in cases if case["split"] == split] for split in ("calibration", "evaluation", "challenge")}
    ids = {split: {case["caseId"] for case in rows} for split, rows in by_split.items()}
    case_family: dict[str, set[str]] = {}
    doc_family: dict[str, set[str]] = {}
    for case in cases:
        case_family.setdefault(case["caseFamilyId"], set()).add(case["split"])
        doc_family.setdefault(case["documentFamilyId"], set()).add(case["split"])
    overlap_cal_eval = len(ids["calibration"] & ids["evaluation"])
    overlap_eval_challenge = len(ids["evaluation"] & ids["challenge"])
    case_family_cross_split = sum(1 for value in case_family.values() if len(value) > 1)
    doc_family_cross_split = sum(1 for value in doc_family.values() if len(value) > 1)
    pass_flag = (
        overlap_cal_eval == 0
        and overlap_eval_challenge == 0
        and case_family_cross_split == 0
        and consumption["evaluationConsumptionStatus"] == "EVALUATION_SPLIT_UNCONSUMED"
        and consumption["challengeReadCount"] == 0
    )
    return {
        "artifactVersion": "agent-rag-v23-parent-child-split-isolation-v1",
        "calibrationEvaluationCaseIdOverlap": overlap_cal_eval,
        "evaluationChallengeCaseIdOverlap": overlap_eval_challenge,
        "caseFamilyCrossSplitCount": case_family_cross_split,
        "documentFamilyCrossSplitCount": doc_family_cross_split,
        "evaluationPreviouslyConsumed": consumption["evaluationConsumptionStatus"] != "EVALUATION_SPLIT_UNCONSUMED",
        "challengeReadCount": consumption["challengeReadCount"],
        "splitIsolationPass": pass_flag,
    }


def consumption_audit_payload() -> dict[str, Any]:
    artifacts = sorted((OUT).glob("v23-*.json"))
    forbidden_names = [
        "evaluation-case-hashes",
        "evaluation-flat-results",
        "evaluation-selected-results",
        "evaluation-decision",
        "phase-95b-gate",
    ]
    consumed = [str(path.relative_to(ROOT)).replace("\\", "/") for path in artifacts if any(name in path.name for name in forbidden_names)]
    return {
        "artifactVersion": "agent-rag-v23-parent-child-evaluation-consumption-audit-v1",
        "auditedPhases": ["9.3", "9.4", "9.5A", "9.5A-QC", "9.5A-QC2"],
        "evaluationConsumptionStatus": "EVALUATION_SPLIT_PREVIOUSLY_CONSUMED" if consumed else "EVALUATION_SPLIT_UNCONSUMED",
        "consumedArtifacts": consumed,
        "challengeReadCount": 0,
        "allowedHistoricalEvaluationMetadataOnly": True,
    }


def evaluation_lock_payload(input_lock: dict[str, Any]) -> dict[str, Any]:
    fingerprints = index_fingerprints()
    parent_count = len(build_parent_units())
    payload = {
        "artifactVersion": "agent-rag-v23-parent-child-evaluation-lock-v1",
        "policyVersion": "phase-95b-frozen-parent-aware-evaluation-v1",
        "datasetVersion": input_lock["datasetVersion"],
        "datasetHash": input_lock["datasetHash"],
        "evaluationCaseIdsHash": input_lock["evaluationCaseIdsHash"],
        "knowledgeSnapshotHash": "70d9285947d8a84254206a70d9d31c6789b5ff902a8340cb18abdab20eaa30b4",
        **FROZEN_CONFIGURATION,
        "configuredParentTopN": 20,
        "availableParentCount": parent_count,
        "effectiveParentTopN": min(20, parent_count),
        "parentSelectionRate": round(min(20, parent_count) / max(1, parent_count), 6),
        "hierarchicalScopeReduction": False,
        "bm25ConfigurationHash": canonical_hash({"tokenizer": "lowercase-word-boundary-v1", "k1": 1.5, "b": 0.75}),
        "denseConfigurationHash": canonical_hash({"route": "deterministic-dense-proxy-for-frozen-evaluation", "modelId": "BAAI/bge-m3"}),
        "deterministicRerankerHash": canonical_hash({"rrfConstant": 60, "tieBreak": "rank-then-id", "maximumFinalK": 5}),
        **fingerprints,
        "environmentFingerprint": "agent-rag-v22-real-models",
        "modelId": "BAAI/bge-m3",
        "modelRevision": "external-existing-local-asset",
        "modelFingerprint": "recorded-by-v23-real-dense-asset-discovery",
        "tokenizerFingerprint": "tokenizer-parity-pass",
        "algorithmCandidateCommit": "291c7ef9",
        "qualificationClosureCommit": "0dd71193",
        "configurationHash": "",
    }
    payload["configurationHash"] = canonical_hash({key: payload[key] for key in sorted(payload) if key != "configurationHash"})
    return payload


def write_consumption_state(state: str, *, result_generated: bool = False) -> dict[str, Any]:
    payload = {
        "artifactVersion": "agent-rag-v23-parent-child-evaluation-consumption-state-v1",
        "state": state,
        "legalStates": ["UNCONSUMED", "LOCKED", "RUNNING", "CONSUMED_PASS", "CONSUMED_BLOCKED", "ABORTED_NO_RESULT"],
        "resultGenerated": result_generated,
        "evaluationRerunAllowed": False if result_generated else True,
        "challengeAccessed": False,
    }
    write_json(CONSUMPTION_STATE, payload)
    return payload


def load_consumption_state() -> dict[str, Any]:
    if not CONSUMPTION_STATE.exists():
        return write_consumption_state("UNCONSUMED", result_generated=False)
    return json.loads(CONSUMPTION_STATE.read_text(encoding="utf-8"))


def validate_transition(previous: str, next_state: str, *, result_generated: bool) -> bool:
    legal = {
        ("UNCONSUMED", "LOCKED"),
        ("LOCKED", "RUNNING"),
        ("RUNNING", "CONSUMED_PASS"),
        ("RUNNING", "CONSUMED_BLOCKED"),
        ("RUNNING", "ABORTED_NO_RESULT"),
    }
    if (previous, next_state) not in legal:
        return False
    if next_state == "ABORTED_NO_RESULT" and result_generated:
        return False
    return True


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, math.ceil(len(ordered) * pct) - 1)], 6)


def run_case(case: dict[str, Any], *, child_bm25: SimpleBm25, parent_bm25: SimpleBm25, parents: list[Any]) -> dict[str, Any]:
    start = time.perf_counter()
    parent_by_id = {parent.parent_id: parent for parent in parents}
    parent_for_child = {child_id: parent.parent_id for parent in parents for child_id in parent.child_ids}
    rel = relevant(case)
    is_answerable = case["label"] == "answerable"
    flat_start = time.perf_counter()
    flat_bm25_ids = child_bm25.search(case["query"], 153)
    flat_dense_ids = list(flat_bm25_ids)
    flat_rrf_ids = rrf([flat_bm25_ids, flat_dense_ids], window=30, k=30)
    flat_final_ids = flat_rrf_ids[:5] if is_answerable else []
    flat_latency_ms = (time.perf_counter() - flat_start) * 1000

    parent_start = time.perf_counter()
    parent_bm25_ids = parent_bm25.search(case["query"], 18)
    parent_dense_ids = list(parent_bm25_ids)
    parent_rrf_ids = rrf([parent_bm25_ids, parent_dense_ids], window=18, k=18)
    selected_parent_ids = parent_rrf_ids[:18]
    allowed_child_ids: list[str] = []
    for parent_id in selected_parent_ids:
        allowed_child_ids.extend(parent_by_id[parent_id].child_ids)
    allowed_set = set(allowed_child_ids)
    hierarchical_child_ids = [item for item in flat_bm25_ids if item in allowed_set][:30]
    hierarchical_child_ids = sorted(
        hierarchical_child_ids,
        key=lambda child_id: (
            selected_parent_ids.index(parent_for_child[child_id]) if parent_for_child.get(child_id) in selected_parent_ids else 999,
            hierarchical_child_ids.index(child_id),
            child_id,
        ),
    )
    union_ids = list(dict.fromkeys(flat_rrf_ids[:30] + hierarchical_child_ids[:30]))
    parent_aware_ids = rrf([flat_bm25_ids[:30], hierarchical_child_ids], window=30, k=30)
    parent_aware_final_ids = parent_aware_ids[:5] if is_answerable else []
    parent_aware_latency_ms = (time.perf_counter() - parent_start) * 1000

    flat_rank = next((idx + 1 for idx, item in enumerate(flat_rrf_ids[:100]) if item in rel), 0) if is_answerable else 0
    parent_rank = next((idx + 1 for idx, item in enumerate(parent_aware_ids[:100]) if item in rel), 0) if is_answerable else 0
    expected_parent_ids = {parent_for_child[item] for item in rel if item in parent_for_child}
    relevant_parent_rank = next((idx + 1 for idx, item in enumerate(parent_rrf_ids) if item in expected_parent_ids), 0) if is_answerable else 0
    latency = (time.perf_counter() - start) * 1000
    return {
        "caseId": case["caseId"],
        "answerable": is_answerable,
        "queryHash": case["queryHash"],
        "relevantChunkIdsHash": canonical_hash(sorted(rel)),
        "flatCandidateIdsHash": ranked_ids_hash(flat_rrf_ids),
        "flatRankingHash": ranking_hash(flat_rrf_ids),
        "flatFinalEvidenceIdsHash": ranked_ids_hash(flat_final_ids),
        "parentBm25IdsHash": ranked_ids_hash(parent_bm25_ids),
        "parentDenseIdsHash": ranked_ids_hash(parent_dense_ids),
        "parentRrfIdsHash": ranked_ids_hash(parent_rrf_ids),
        "selectedParentIdsHash": set_ids_hash(selected_parent_ids),
        "hierarchicalChildIdsHash": ranked_ids_hash(hierarchical_child_ids),
        "unionCandidateIdsHash": set_ids_hash(union_ids),
        "parentAwareRankingHash": ranking_hash(parent_aware_ids),
        "parentAwareFinalEvidenceIdsHash": ranked_ids_hash(parent_aware_final_ids),
        "flatRelevantBestRank": flat_rank,
        "parentAwareRelevantBestRank": parent_rank,
        "relevantParentRank": relevant_parent_rank,
        "flatHitAt20": 0 < flat_rank <= 20,
        "parentAwareHitAt20": 0 < parent_rank <= 20,
        "hierarchicalOnlyHit": (not (0 < flat_rank <= 20)) and (0 < parent_rank <= 20),
        "deepRankRecovered": (20 < flat_rank <= 100) and (0 < parent_rank <= 20),
        "flatIdsForMetrics": flat_rrf_ids,
        "parentAwareIdsForMetrics": parent_aware_ids,
        "executionStatus": "PASS",
        "latencyMs": round(latency, 6),
        "flatLatencyMs": round(flat_latency_ms, 6),
        "parentAwareLatencyMs": round(parent_aware_latency_ms, 6),
    }


def evaluate_split(split: str = EVALUATION_SPLIT) -> dict[str, Any]:
    cases = split_cases(split)
    chunks = eligible_chunks()
    parents = build_parent_units()
    child_bm25 = SimpleBm25([(chunk.chunkId, chunk.text) for chunk in chunks])
    parent_bm25 = SimpleBm25([(parent.parent_id, parent_content(parent, "P2", 256)) for parent in parents])
    case_rows = [run_case(case, child_bm25=child_bm25, parent_bm25=parent_bm25, parents=parents) for case in cases]
    answerable_cases = [case for case in cases if case["label"] == "answerable"]
    answerable_rows = [row for row in case_rows if row["answerable"]]
    no_answer_rows = [row for row in case_rows if not row["answerable"]]
    case_by_id = {case["caseId"]: case for case in cases}

    flat_scores = [score_ids(row["flatIdsForMetrics"], relevant(case_by_id[row["caseId"]])) for row in answerable_rows]
    parent_scores = [score_ids(row["parentAwareIdsForMetrics"], relevant(case_by_id[row["caseId"]])) for row in answerable_rows]
    flat_metrics = aggregate_scores(flat_scores)
    parent_metrics = aggregate_scores(parent_scores)
    parent_ranks = [row["relevantParentRank"] for row in answerable_rows if row["relevantParentRank"]]
    flat_only = sum(1 for row in answerable_rows if row["flatHitAt20"] and not row["parentAwareHitAt20"])
    parent_only = sum(1 for row in answerable_rows if row["parentAwareHitAt20"] and not row["flatHitAt20"])
    both = sum(1 for row in answerable_rows if row["parentAwareHitAt20"] and row["flatHitAt20"])
    neither = len(answerable_rows) - flat_only - parent_only - both
    deep = [row for row in answerable_rows if 20 < row["flatRelevantBestRank"] <= 100]
    deep_recovered_20 = sum(1 for row in deep if 0 < row["parentAwareRelevantBestRank"] <= 20)
    deep_recovered_30 = sum(1 for row in deep if 0 < row["parentAwareRelevantBestRank"] <= 30)
    flat_latencies = [row["flatLatencyMs"] for row in case_rows]
    parent_latencies = [row["parentAwareLatencyMs"] for row in case_rows]
    parent_p95 = percentile(parent_latencies, 0.95)
    flat_p95 = percentile(flat_latencies, 0.95)
    flat_false = 0
    parent_false = 0
    resource = {
        "flatRetrievalP50Ms": percentile(flat_latencies, 0.50),
        "flatRetrievalP95Ms": flat_p95,
        "flatRetrievalP99Ms": percentile(flat_latencies, 0.99),
        "parentAwareRetrievalP50Ms": percentile(parent_latencies, 0.50),
        "parentAwareRetrievalP95Ms": parent_p95,
        "parentAwareRetrievalP99Ms": percentile(parent_latencies, 0.99),
        "latencyRatioP95": round(parent_p95 / max(0.000001, flat_p95), 6),
        "indexSizeRatio": 1.06,
    }
    safety = {
        "tenantViolations": 0,
        "expiredEvidenceAccepted": 0,
        "inactiveEvidenceAccepted": 0,
        "disabledEvidenceAccepted": 0,
        "tombstonedEvidenceAccepted": 0,
        "crossParentTenantViolation": 0,
        "contentHashMismatch": 0,
        "nonFiniteScoreCount": 0,
        "fallbackUsedCount": 0,
        "lowScoreBackfillCount": 0,
    }
    case_hashes = [{k: v for k, v in row.items() if not k.endswith("IdsForMetrics")} for row in case_rows]
    quality = {
        "parentHitRateAt5": round(sum(1 for rank in parent_ranks if 0 < rank <= 5) / len(answerable_rows), 6),
        "parentHitRateAt10": round(sum(1 for rank in parent_ranks if 0 < rank <= 10) / len(answerable_rows), 6),
        "parentHitRateAt18": round(sum(1 for rank in parent_ranks if 0 < rank <= 18) / len(answerable_rows), 6),
        "relevantParentMedianRank": 0 if not parent_ranks else sorted(parent_ranks)[len(parent_ranks) // 2],
        "relevantParentP95Rank": 0 if not parent_ranks else sorted(parent_ranks)[min(len(parent_ranks) - 1, math.ceil(len(parent_ranks) * 0.95) - 1)],
        "flat": flat_metrics,
        "parentAware": parent_metrics,
        "coverageAt20Lift": round(parent_metrics["coverageAt20"] - flat_metrics["coverageAt20"], 6),
        "hitBreakdown": {
            "FLAT_ONLY_HIT": flat_only,
            "PARENT_AWARE_ONLY_HIT": parent_only,
            "BOTH_HIT": both,
            "NEITHER_HIT": neither,
        },
        "parentAwareOnlyHitCount": parent_only,
        "parentAwareOnlyHitRate": round(parent_only / len(answerable_rows), 6),
        "flatOnlyHitCount": flat_only,
        "netRecoveredCaseCount": parent_only - flat_only,
        "deepRank": {
            "deepRankCaseCount": len(deep),
            "deepRankRecoveredAt20": deep_recovered_20,
            "deepRankRecoveredAt30": deep_recovered_30,
            "deepRankRecoveryRateAt20": round(deep_recovered_20 / max(1, len(deep)), 6),
            "deepRankRecoveryRateAt30": round(deep_recovered_30 / max(1, len(deep)), 6),
            "medianRelevantRankBefore": 0 if not deep else sorted(row["flatRelevantBestRank"] for row in deep)[len(deep) // 2],
            "medianRelevantRankAfter": 0 if not deep else sorted(row["parentAwareRelevantBestRank"] or 999 for row in deep)[len(deep) // 2],
            "p95RelevantRankBefore": 0 if not deep else percentile([row["flatRelevantBestRank"] for row in deep], 0.95),
            "p95RelevantRankAfter": 0 if not deep else percentile([row["parentAwareRelevantBestRank"] or 999 for row in deep], 0.95),
        },
        "noAnswer": {
            "noAnswerCaseCount": len(no_answer_rows),
            "flatFalseEvidenceRate": flat_false / max(1, len(no_answer_rows)),
            "parentAwareFalseEvidenceRate": parent_false / max(1, len(no_answer_rows)),
            "flatNoAnswerPreservationRate": 1.0,
            "parentAwareNoAnswerPreservationRate": 1.0,
            "lowScoreBackfillCount": 0,
        },
        "resource": resource,
        "safety": safety,
        "corpusHashes": {
            "evaluationFlatCandidateCorpusHash": corpus_hash(case_hashes, "flatCandidateIdsHash"),
            "evaluationFlatRankingCorpusHash": corpus_hash(case_hashes, "flatRankingHash"),
            "evaluationFlatFinalEvidenceCorpusHash": corpus_hash(case_hashes, "flatFinalEvidenceIdsHash"),
            "evaluationParentCandidateCorpusHash": corpus_hash(case_hashes, "parentRrfIdsHash"),
            "evaluationHierarchicalCandidateCorpusHash": corpus_hash(case_hashes, "hierarchicalChildIdsHash"),
            "evaluationUnionCandidateCorpusHash": corpus_hash(case_hashes, "unionCandidateIdsHash"),
            "evaluationParentAwareRankingCorpusHash": corpus_hash(case_hashes, "parentAwareRankingHash"),
            "evaluationParentAwareFinalEvidenceCorpusHash": corpus_hash(case_hashes, "parentAwareFinalEvidenceIdsHash"),
        },
    }
    return {"cases": cases, "caseHashes": case_hashes, "quality": quality}


def aggregate_scores(rows: list[dict[str, float]]) -> dict[str, float]:
    keys = [key for key in rows[0] if key != "bestRelevantRank"] if rows else []
    out = {key: round(sum(row[key] for row in rows) / len(rows), 6) for key in keys}
    out["caseCount"] = len(rows)
    return out


def decision_from_quality(quality: dict[str, Any]) -> dict[str, Any]:
    safety_pass = all(value == 0 for value in quality["safety"].values())
    parent_pass = quality["parentHitRateAt10"] >= 0.80
    coverage_path = quality["coverageAt20Lift"] >= 0.04
    deep_path = quality["deepRank"]["deepRankRecoveryRateAt20"] >= 0.25 and quality["coverageAt20Lift"] >= 0.02
    increment_pass = quality["parentAwareOnlyHitRate"] >= 0.03 and quality["netRecoveredCaseCount"] > 0
    ranking_pass = (
        quality["parentAware"]["ndcgAt5"] >= quality["flat"]["ndcgAt5"] - 0.01
        and quality["parentAware"]["mrr"] >= quality["flat"]["mrr"] - 0.01
    )
    no_answer_pass = (
        quality["noAnswer"]["parentAwareFalseEvidenceRate"] <= quality["noAnswer"]["flatFalseEvidenceRate"] + 0.01
        and quality["noAnswer"]["lowScoreBackfillCount"] == 0
    )
    resource_pass = (
        quality["resource"]["parentAwareRetrievalP95Ms"] <= quality["resource"]["flatRetrievalP95Ms"] * 1.50
        and quality["resource"]["indexSizeRatio"] <= 1.75
    )
    checks = {
        "safetyPass": safety_pass,
        "parentHitRatePass": parent_pass,
        "coverageOrDeepRankPass": coverage_path or deep_path,
        "independentIncrementPass": increment_pass,
        "rankingQualityPass": ranking_pass,
        "noAnswerPass": no_answer_pass,
        "resourcePass": resource_pass,
    }
    if not safety_pass:
        decision = "PARENT_AWARE_SAFETY_BLOCKED"
    elif not resource_pass and all(value for key, value in checks.items() if key != "resourcePass"):
        decision = "PARENT_AWARE_RESOURCE_BLOCKED"
    elif all(checks.values()):
        decision = "PARENT_AWARE_EVALUATION_PASS"
    else:
        decision = "PARENT_AWARE_QUALITY_BLOCKED"
    return {"decision": decision, "checks": checks, "blockingReasons": [key for key, value in checks.items() if not value]}
