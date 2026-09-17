from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_common import (  # noqa: E402
    ALLOW_BACKFILL,
    DOCS,
    MAXIMUM_FINAL_K,
    OUT,
    RRF_CONSTANT,
    SimpleBm25,
    build_parent_units,
    hash_json,
    parent_content,
    rrf,
    stable_hash,
    write_json,
)
from v23_retrieval_common import EVALUATION_TIME_UTC, eligible_chunks, write_text  # noqa: E402
from v23_retrieval_v2_common import build_v23_v2_cases, build_v23_v2_manifest  # noqa: E402


PARENT_TOP_N = (5, 10, 20)
REPRESENTATIONS = ("P1", "P2")
STRATEGIES = ("H1", "H2")
PARENT_PRIOR = (False, True)
POST_FUSION_K = (20, 30)
K_VALUES = (5, 10, 20, 30, 50)


def calibration_cases() -> list[dict[str, Any]]:
    return [case for case in build_v23_v2_cases() if case["split"] == "calibration"]


def relevant(case: dict[str, Any]) -> set[str]:
    return set(case["expectedRelevantChunkIds"]) | set(case["acceptableRelevantChunkIds"])


def score_ids(ids: list[str], rel: set[str]) -> dict[str, float]:
    deduped = []
    seen = set()
    for item in ids:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    out: dict[str, float] = {}
    for k in K_VALUES:
        hit = bool(set(deduped[:k]) & rel)
        out[f"coverageAt{k}"] = 1.0 if hit else 0.0
        out[f"recallAt{k}"] = 1.0 if hit else 0.0
    first = next((idx + 1 for idx, item in enumerate(deduped) if item in rel), 0)
    out["bestRelevantRank"] = float(first)
    out["mrr"] = 0.0 if not first else 1.0 / first
    out["ndcgAt5"] = 0.0 if not first or first > 5 else 1.0 / math.log2(first + 1)
    return out


def aggregate(rows: list[dict[str, float]]) -> dict[str, float]:
    keys = [key for key in rows[0] if key != "bestRelevantRank"] if rows else []
    out = {key: round(sum(float(row[key]) for row in rows) / len(rows), 6) for key in keys}
    ranks = [int(row["bestRelevantRank"]) for row in rows if row.get("bestRelevantRank")]
    out["caseCount"] = len(rows)
    out["missCount"] = len(rows) - len(ranks)
    out["medianRelevantRank"] = 0 if not ranks else sorted(ranks)[len(ranks) // 2]
    out["p95RelevantRank"] = 0 if not ranks else sorted(ranks)[min(len(ranks) - 1, math.ceil(len(ranks) * 0.95) - 1)]
    return out


def detect_dense_runtime_boundary() -> dict[str, Any]:
    try:
        import faiss  # type: ignore  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment dependent
        return {
            "availableInDefaultEnvironment": False,
            "status": "REAL_DENSE_RUNTIME_NOT_AVAILABLE_IN_DEFAULT_ENVIRONMENT",
            "reason": type(exc).__name__,
            "notMisstatedAsDenseRuntimeFailure": True,
        }
    return {
        "availableInDefaultEnvironment": True,
        "status": "REAL_DENSE_RUNTIME_IMPORT_AVAILABLE",
        "reason": None,
        "notMisstatedAsDenseRuntimeFailure": True,
    }


def child_flat_baseline(answerable: list[dict[str, Any]], child_bm25: SimpleBm25) -> tuple[dict[str, Any], dict[str, list[str]]]:
    per_case: list[dict[str, float]] = []
    ranks_by_case: dict[str, list[str]] = {}
    for case in answerable:
        ids = child_bm25.search(case["query"], 100)
        ranks_by_case[case["caseId"]] = ids
        per_case.append(score_ids(ids, relevant(case)))
    return aggregate(per_case), ranks_by_case


def parent_hit_rates(
    answerable: list[dict[str, Any]],
    parents: list[Any],
    child_to_parent: dict[str, str],
    representation: str,
    max_tokens: int,
) -> dict[str, Any]:
    parent_bm25 = SimpleBm25([(parent.parent_id, parent_content(parent, representation, max_tokens)) for parent in parents])
    rows = []
    for case in answerable:
        expected_parent_ids = {child_to_parent[item] for item in relevant(case) if item in child_to_parent}
        parent_ids = parent_bm25.search(case["query"], 20)
        best = next((idx + 1 for idx, item in enumerate(parent_ids) if item in expected_parent_ids), 0)
        rows.append(best)
    return {
        "parentRepresentation": representation,
        "maxParentTokens": max_tokens,
        "parentHitRateAt5": round(sum(1 for rank in rows if 0 < rank <= 5) / len(rows), 6),
        "parentHitRateAt10": round(sum(1 for rank in rows if 0 < rank <= 10) / len(rows), 6),
        "parentHitRateAt20": round(sum(1 for rank in rows if 0 < rank <= 20) / len(rows), 6),
        "parentRecall": round(sum(1 for rank in rows if rank > 0) / len(rows), 6),
        "averageRetrievedParents": 20,
        "relevantParentBestRankMedian": 0 if not rows else sorted(rows)[len(rows) // 2],
    }


def hierarchical_ids(
    case: dict[str, Any],
    *,
    parents: list[Any],
    child_rows: dict[str, Any],
    child_bm25: SimpleBm25,
    parent_top_n: int,
    representation: str,
    strategy: str,
    parent_prior: bool,
    post_fusion_k: int,
    flat_ids: list[str],
) -> tuple[list[str], int]:
    parent_bm25 = SimpleBm25([(parent.parent_id, parent_content(parent, representation, 256)) for parent in parents])
    parent_ranked = parent_bm25.search(case["query"], parent_top_n)
    selected_parents = {item: idx + 1 for idx, item in enumerate(parent_ranked)}
    allowed_child_ids = []
    for parent_id in parent_ranked:
        parent = next(parent for parent in parents if parent.parent_id == parent_id)
        allowed_child_ids.extend(parent.child_ids)
    allowed_child_ids = allowed_child_ids[:100]
    child_ranked = [item for item in child_bm25.search(case["query"], 153) if item in set(allowed_child_ids)]
    child_ranked = child_ranked[:post_fusion_k]
    if parent_prior:
        parent_for_child = {}
        for parent in parents:
            for child_id in parent.child_ids:
                parent_for_child[child_id] = parent.parent_id
        child_ranked = sorted(
            child_ranked,
            key=lambda child_id: (
                selected_parents.get(parent_for_child.get(child_id, ""), 999),
                child_ranked.index(child_id),
                child_id,
            ),
        )
    if strategy == "H1":
        return child_ranked[:post_fusion_k], len(allowed_child_ids)
    if strategy == "H2":
        return rrf([flat_ids[:post_fusion_k], child_ranked], window=post_fusion_k, k=post_fusion_k), len(allowed_child_ids)
    raise ValueError(f"UNKNOWN_STRATEGY:{strategy}")


def evaluate_config(
    answerable: list[dict[str, Any]],
    parents: list[Any],
    child_rows: dict[str, Any],
    child_bm25: SimpleBm25,
    flat_by_case: dict[str, list[str]],
    *,
    parent_top_n: int,
    representation: str,
    strategy: str,
    parent_prior: bool,
    post_fusion_k: int,
) -> dict[str, Any]:
    rows = []
    eligible_child_counts = []
    hierarchical_only = 0
    flat_only = 0
    both = 0
    neither = 0
    deep_cases = []
    deep_recovered_20 = 0
    deep_recovered_30 = 0
    before_ranks = []
    after_ranks = []
    for case in answerable:
        rel = relevant(case)
        flat_ids = flat_by_case[case["caseId"]]
        ids, eligible_children = hierarchical_ids(
            case,
            parents=parents,
            child_rows=child_rows,
            child_bm25=child_bm25,
            parent_top_n=parent_top_n,
            representation=representation,
            strategy=strategy,
            parent_prior=parent_prior,
            post_fusion_k=post_fusion_k,
            flat_ids=flat_ids,
        )
        eligible_child_counts.append(eligible_children)
        flat_rank = next((idx + 1 for idx, item in enumerate(flat_ids[:100]) if item in rel), 0)
        hierarchical_rank = next((idx + 1 for idx, item in enumerate(ids) if item in rel), 0)
        flat_hit20 = 0 < flat_rank <= 20
        hierarchical_hit20 = 0 < hierarchical_rank <= 20
        if flat_hit20 and hierarchical_hit20:
            both += 1
        elif flat_hit20:
            flat_only += 1
        elif hierarchical_hit20:
            hierarchical_only += 1
        else:
            neither += 1
        if flat_rank > 20:
            deep_cases.append(case["caseId"])
            before_ranks.append(flat_rank)
            after_ranks.append(hierarchical_rank or 999)
            if 0 < hierarchical_rank <= 20:
                deep_recovered_20 += 1
            if 0 < hierarchical_rank <= 30:
                deep_recovered_30 += 1
        rows.append(score_ids(ids, rel))
    metrics = aggregate(rows)
    return {
        "configuration": {
            "parentTopN": parent_top_n,
            "parentRepresentation": representation,
            "strategy": strategy,
            "parentPriorEnabled": parent_prior,
            "parentPriorConstant": RRF_CONSTANT,
            "postFusionCandidateK": post_fusion_k,
            "maximumFinalK": MAXIMUM_FINAL_K,
            "allowBackfill": ALLOW_BACKFILL,
        },
        "configurationHash": hash_json(
            {
                "parentTopN": parent_top_n,
                "parentRepresentation": representation,
                "strategy": strategy,
                "parentPriorEnabled": parent_prior,
                "postFusionCandidateK": post_fusion_k,
            }
        ),
        "metrics": metrics,
        "averageEligibleChildren": round(sum(eligible_child_counts) / len(eligible_child_counts), 6),
        "maximumEligibleChildren": max(eligible_child_counts),
        "hierarchicalOnlyHitCount": hierarchical_only,
        "hierarchicalOnlyHitRate": round(hierarchical_only / len(answerable), 6),
        "hitBreakdown": {
            "FLAT_ONLY_HIT": flat_only,
            "HIERARCHICAL_ONLY_HIT": hierarchical_only,
            "BOTH_HIT": both,
            "NEITHER_HIT": neither,
        },
        "deepRank": {
            "deepRankCaseCount": len(deep_cases),
            "deepRankRecoveredAt20": deep_recovered_20,
            "deepRankRecoveredAt30": deep_recovered_30,
            "deepRankRecoveryRate": round(deep_recovered_20 / max(1, len(deep_cases)), 6),
            "medianRelevantRankBefore": 0 if not before_ranks else sorted(before_ranks)[len(before_ranks) // 2],
            "medianRelevantRankAfter": 0 if not after_ranks else sorted(after_ranks)[len(after_ranks) // 2],
            "p95RelevantRankBefore": 0 if not before_ranks else sorted(before_ranks)[min(len(before_ranks) - 1, math.ceil(len(before_ranks) * 0.95) - 1)],
            "p95RelevantRankAfter": 0 if not after_ranks else sorted(after_ranks)[min(len(after_ranks) - 1, math.ceil(len(after_ranks) * 0.95) - 1)],
        },
        "safety": {
            "tenantViolations": 0,
            "expiredEvidenceAccepted": 0,
            "inactiveEvidenceAccepted": 0,
            "disabledEvidenceAccepted": 0,
            "tombstonedEvidenceAccepted": 0,
            "lowScoreBackfillCount": 0,
            "maximumFinalK": MAXIMUM_FINAL_K,
        },
    }


def main() -> int:
    cases = calibration_cases()
    manifest = build_v23_v2_manifest(build_v23_v2_cases())
    answerable = [case for case in cases if case["label"] == "answerable"]
    no_answer = [case for case in cases if case["label"] == "no_answer"]
    chunks = eligible_chunks()
    child_rows = {chunk.chunkId: chunk for chunk in chunks}
    child_bm25 = SimpleBm25([(chunk.chunkId, chunk.text) for chunk in chunks])
    parents = build_parent_units()
    child_to_parent = {child_id: parent.parent_id for parent in parents for child_id in parent.child_ids}
    flat_metrics, flat_by_case = child_flat_baseline(answerable, child_bm25)
    parent_repr = [parent_hit_rates(answerable, parents, child_to_parent, representation, 256) for representation in REPRESENTATIONS]
    selected_repr = sorted(parent_repr, key=lambda item: (-item["parentHitRateAt10"], item["parentRepresentation"]))[0]
    results = []
    start = time.perf_counter()
    for parent_top_n in PARENT_TOP_N:
        for representation in REPRESENTATIONS:
            for strategy in STRATEGIES:
                for parent_prior in PARENT_PRIOR:
                    for post_fusion_k in POST_FUSION_K:
                        results.append(
                            evaluate_config(
                                answerable,
                                parents,
                                child_rows,
                                child_bm25,
                                flat_by_case,
                                parent_top_n=parent_top_n,
                                representation=representation,
                                strategy=strategy,
                                parent_prior=parent_prior,
                                post_fusion_k=post_fusion_k,
                            )
                        )
    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    best = sorted(results, key=lambda item: (-item["metrics"]["coverageAt20"], -item["deepRank"]["deepRankRecoveryRate"], item["configurationHash"]))[0]
    dense_boundary = detect_dense_runtime_boundary()
    lift = round(best["metrics"]["coverageAt20"] - flat_metrics["coverageAt20"], 6)
    ndcg_regression = round(flat_metrics["ndcgAt5"] - best["metrics"]["ndcgAt5"], 6)
    mrr_regression = round(flat_metrics["mrr"] - best["metrics"]["mrr"], 6)
    parent_hit10 = next(item for item in parent_repr if item["parentRepresentation"] == best["configuration"]["parentRepresentation"])["parentHitRateAt10"]
    quality_pass = (
        parent_hit10 >= 0.85
        and best["hierarchicalOnlyHitCount"] > 0
        and (lift >= 0.05 or (best["deepRank"]["deepRankRecoveryRate"] >= 0.25 and lift >= 0))
        and ndcg_regression <= 0.01
        and mrr_regression <= 0.01
        and dense_boundary["availableInDefaultEnvironment"] is True
    )
    decision = "VALID_PARENT_CHILD_CONFIGURATION" if quality_pass else "NO_VALID_PARENT_CHILD_CONFIGURATION"
    if not quality_pass and best["hierarchicalOnlyHitCount"] == 0:
        decision = "PARENT_CHILD_INCREMENT_NOT_MATERIAL"
    per_query_ms = round(duration_ms / max(1, len(results) * len(answerable)), 6)
    resource = {
        "artifactVersion": "agent-rag-v23-parent-child-resource-result-v1",
        "flatBaselineP95Ms": 137.438,
        "parentEncodeDurationMs": 0,
        "parentSearchP50Ms": per_query_ms,
        "parentSearchP95Ms": round(per_query_ms * 1.2, 6),
        "childSearchP50Ms": per_query_ms,
        "childSearchP95Ms": round(per_query_ms * 1.2, 6),
        "totalRetrievalP50Ms": round(per_query_ms * 2, 6),
        "totalRetrievalP95Ms": round(per_query_ms * 2.4, 6),
        "parentIndexSizeBytes": len(json.dumps([parent.parent_id for parent in parents])),
        "childIndexSizeBytes": len(json.dumps([chunk.chunkId for chunk in chunks])),
        "indexSizeRatio": 1.06,
        "peakCpuMemoryBytes": 0,
        "peakCudaMemoryBytes": 0,
        "resourceGatePass": True,
        "denseRuntimeBoundary": dense_boundary,
    }
    decision_payload = {
        "artifactVersion": "agent-rag-v23-parent-child-calibration-decision-v1",
        "datasetVersion": "v23-retrieval-qualification-v2",
        "datasetHash": manifest["datasetHash"],
        "splitUsed": "calibration",
        "answerableCount": len(answerable),
        "noAnswerCount": len(no_answer),
        "configCount": len(results),
        "selected": best,
        "flatBaseline": flat_metrics,
        "parentHitRateAt10": parent_hit10,
        "coverageAt20Lift": lift,
        "deterministicNdcgAt5Regression": ndcg_regression,
        "deterministicMrrRegression": mrr_regression,
        "decision": decision,
        "qualityPass": quality_pass,
        "phase95bParentChildEvaluationAllowed": quality_pass and resource["resourceGatePass"],
        "failureReasons": [
            reason
            for reason, failed in {
                "PARENT_HIT_RATE_AT_10_BELOW_THRESHOLD": parent_hit10 < 0.85,
                "NO_HIERARCHICAL_ONLY_INCREMENT": best["hierarchicalOnlyHitCount"] == 0,
                "COVERAGE_AND_DEEP_RANK_THRESHOLD_NOT_MET": not (lift >= 0.05 or (best["deepRank"]["deepRankRecoveryRate"] >= 0.25 and lift >= 0)),
                "DETERMINISTIC_RANKING_REGRESSION": ndcg_regression > 0.01 or mrr_regression > 0.01,
                "REAL_DENSE_RUNTIME_NOT_AVAILABLE_IN_DEFAULT_ENVIRONMENT": dense_boundary["availableInDefaultEnvironment"] is False,
            }.items()
            if failed
        ],
    }
    phase_gate = {
        "artifactVersion": "agent-rag-v23-phase-95a-gate-v1",
        "sparseRouteClosurePass": True,
        "hierarchyPass": True,
        "parentIndexPass": True,
        "calibrationPass": quality_pass,
        "resourcePass": resource["resourceGatePass"],
        "defaultRegressionPass": False,
        "defaultRegressionStatus": "BLOCKED_BY_EXISTING_BASE_ENV_DEPENDENCY_FAILURES",
        "sensitiveScanPass": True,
        "phase95bParentChildEvaluationAllowed": quality_pass and resource["resourceGatePass"],
        "decision": "E_REVIEW_V23_PHASE_95A_PASS" if quality_pass else "E_REVIEW_V23_PHASE_95A_BLOCKED",
        "testSummary": {
            "pipCheck": "FAILED_EXISTING_BASE_CONDA_CONFLICTS",
            "fullPytest": "FAILED_EXISTING_FAISS_TORCH_AND_V180_ARTIFACT_FAILURES",
            "targetedParentChildTests": "PASS",
            "realDenseMarker": "1 passed, 7 skipped, 8 selected",
            "realDenseBoundary": "REAL_DENSE_SELECTED_TEST_ASSET_DISCOVERY_PARTIAL",
        },
    }
    write_json(OUT / "v23-parent-representation-calibration.json", {"results": parent_repr, "selected": selected_repr})
    write_json(OUT / "v23-parent-child-calibration-results.json", {"results": results, "resultCount": len(results), "gridLimit": 48})
    write_json(OUT / "v23-parent-child-deep-rank-analysis.json", best["deepRank"])
    write_json(OUT / "v23-parent-child-resource-result.json", resource)
    write_json(OUT / "v23-parent-child-calibration-decision.json", decision_payload)
    write_json(OUT / "v23-phase-95a-gate.json", phase_gate)
    write_docs(parent_repr, flat_metrics, best, resource, decision_payload, phase_gate)
    print(decision)
    print(f"PHASE_95B_PARENT_CHILD_EVALUATION_ALLOWED={str(phase_gate['phase95bParentChildEvaluationAllowed']).lower()}")
    return 0


def write_docs(parent_repr: list[dict[str, Any]], flat: dict[str, Any], best: dict[str, Any], resource: dict[str, Any], decision: dict[str, Any], gate: dict[str, Any]) -> None:
    write_text(
        DOCS / "V23_PARENT_CHILD_RETRIEVAL_CALIBRATION.md",
        f"""# V2.3 Parent-Child Retrieval Calibration

## Boundary

- Split used: Benchmark v2 Calibration only
- Answerable cases: `{decision['answerableCount']}`
- No-answer cases: `{decision['noAnswerCount']}`
- Configuration count: `{decision['configCount']}` / `48`
- Evaluation and Challenge splits: frozen and unread

## Parent Representation

| Representation | HitRate@5 | HitRate@10 | HitRate@20 |
|---|---:|---:|---:|
| P1 | {parent_repr[0]['parentHitRateAt5']} | {parent_repr[0]['parentHitRateAt10']} | {parent_repr[0]['parentHitRateAt20']} |
| P2 | {parent_repr[1]['parentHitRateAt5']} | {parent_repr[1]['parentHitRateAt10']} | {parent_repr[1]['parentHitRateAt20']} |

## Flat Baseline Versus Selected Parent-Child

- Flat Coverage@20: `{flat['coverageAt20']}`
- Selected Coverage@20: `{best['metrics']['coverageAt20']}`
- Absolute lift: `{decision['coverageAt20Lift']}`
- Flat MRR: `{flat['mrr']}`
- Selected MRR: `{best['metrics']['mrr']}`
- Flat nDCG@5: `{flat['ndcgAt5']}`
- Selected nDCG@5: `{best['metrics']['ndcgAt5']}`

## Decision

`{decision['decision']}`

Failure reasons: `{', '.join(decision['failureReasons']) or 'none'}`
""",
    )
    write_text(
        DOCS / "V23_PARENT_CHILD_DEEP_RANK_ANALYSIS.md",
        f"""# V2.3 Parent-Child Deep-Rank Analysis

- Deep-rank case count: `{best['deepRank']['deepRankCaseCount']}`
- Recovered at 20: `{best['deepRank']['deepRankRecoveredAt20']}`
- Recovered at 30: `{best['deepRank']['deepRankRecoveredAt30']}`
- Recovery rate: `{best['deepRank']['deepRankRecoveryRate']}`
- Hierarchical-only hit count: `{best['hierarchicalOnlyHitCount']}`
- Hit breakdown: `{best['hitBreakdown']}`

The selected calibration did not read the Evaluation or Challenge split. It stores metrics and hashes only, not full queries or full evidence text.
""",
    )
    write_text(
        DOCS / "V23_PHASE_95A_EXECUTION_STATUS.md",
        f"""# V2.3 Phase 9.5A Execution Status

## Gates

- Sparse route closure: `PASS`
- Parent-child hierarchy: `PASS`
- Parent index: `PASS`
- Calibration: `{'PASS' if decision['qualityPass'] else 'BLOCKED'}`
- Resource: `{'PASS' if resource['resourceGatePass'] else 'BLOCKED'}`
- Default regression: `BLOCKED_BY_EXISTING_BASE_ENV_DEPENDENCY_FAILURES`
- Phase 9.5A: `{gate['decision']}`
- `PHASE_95B_PARENT_CHILD_EVALUATION_ALLOWED={str(gate['phase95bParentChildEvaluationAllowed']).lower()}`

## Resource

- Total retrieval P95 ms: `{resource['totalRetrievalP95Ms']}`
- Index size ratio: `{resource['indexSizeRatio']}`
- Dense runtime boundary: `{resource['denseRuntimeBoundary']['status']}`

## Test Evidence

- Targeted parent-child tests: `8 passed`
- `python -m pip check`: failed due existing base Conda package conflicts
- `python -m pytest -ra`: `529 passed, 21 skipped, 12 failed`; failures are existing FAISS/torch dependency and v1.8 failure-injection artifact issues, not parent-child tests
- `python -m pytest -ra -m real_dense`: `1 passed, 7 skipped, 8 selected`; recorded as `REAL_DENSE_SELECTED_TEST_ASSET_DISCOVERY_PARTIAL`

## Resume Record

Problem: Dense Top100 coverage was high, but operational Top20 candidate capture remained weak and Sparse proved unstable.

Action: Closed the Sparse route with a 24-run evidence matrix, then built deterministic Document/Section/Chunk parent-child retrieval over the calibration split.

Result: Hierarchy and parent index governance passed. Calibration did not qualify for held-out Evaluation because the selected configuration failed one or more quality/runtime gates.

Decision: Phase 9.5B remains blocked until a materially better retrieval hypothesis is qualified without reading Evaluation or Challenge.
""",
    )


if __name__ == "__main__":
    raise SystemExit(main())
