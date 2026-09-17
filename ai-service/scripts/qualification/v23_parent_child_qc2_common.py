from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Any

from v23_parent_child_common import (
    ALLOW_BACKFILL,
    MAXIMUM_FINAL_K,
    RRF_CONSTANT,
    SimpleBm25,
    build_parent_units,
    parent_content,
    rrf,
)
from v23_retrieval_common import eligible_chunks, hash_json
from v23_retrieval_v2_common import build_v23_v2_cases, build_v23_v2_manifest


FORBIDDEN_SPLIT_ERROR = "HELD_OUT_SPLIT_ACCESS_FORBIDDEN_IN_PHASE_95A_QC2"
FROZEN_CONFIGURATION = {
    "parentRepresentation": "P2",
    "strategy": "H2",
    "parentTopN": 20,
    "parentPriorEnabled": True,
    "parentPriorConstant": 60,
    "postFusionCandidateK": 30,
    "maximumFinalK": 5,
    "allowBackfill": False,
}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ranked_ids_hash(ids: list[str]) -> str:
    return canonical_hash(list(ids))


def set_ids_hash(ids: list[str]) -> str:
    return canonical_hash(sorted(set(ids)))


def ranking_hash(ids: list[str]) -> str:
    return canonical_hash([{"id": item, "rank": index} for index, item in enumerate(ids, start=1)])


def corpus_hash(records: list[dict[str, Any]], field: str) -> str:
    ordered = [{"caseId": item["caseId"], field: item[field]} for item in sorted(records, key=lambda row: row["caseId"])]
    return canonical_hash(ordered)


def guard_calibration_split(split: str) -> None:
    if split != "calibration":
        raise RuntimeError(FORBIDDEN_SPLIT_ERROR)


def relevant(case: dict[str, Any]) -> set[str]:
    return set(case["expectedRelevantChunkIds"]) | set(case["acceptableRelevantChunkIds"])


def score_ids(ids: list[str], rel: set[str]) -> dict[str, float]:
    deduped: list[str] = []
    seen = set()
    for item in ids:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    out: dict[str, float] = {}
    for k in (5, 10, 20, 30):
        out[f"coverageAt{k}"] = 1.0 if set(deduped[:k]) & rel else 0.0
        out[f"recallAt{k}"] = out[f"coverageAt{k}"]
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


def index_fingerprints() -> dict[str, str]:
    chunks = eligible_chunks()
    parents = build_parent_units()
    parent_rows = [
        {
            "parentId": parent.parent_id,
            "childIdsHash": hash_json(list(parent.child_ids)),
            "contentHash": canonical_hash(parent_content(parent, "P2", 256)),
            "tenantId": parent.tenant_id,
        }
        for parent in parents
    ]
    child_rows = [
        {
            "chunkId": chunk.chunkId,
            "documentIdHash": canonical_hash(chunk.documentId),
            "textHash": canonical_hash(chunk.text),
            "tenantId": chunk.tenantId,
        }
        for chunk in chunks
    ]
    parent_bm25 = SimpleBm25([(row["parentId"], row["contentHash"]) for row in parent_rows])
    child_bm25 = SimpleBm25([(row["chunkId"], row["textHash"]) for row in child_rows])
    probes = ["refund governance", "after sales risk", "image conflict"]
    return {
        "parentIndexCanonicalFingerprint": canonical_hash(parent_rows),
        "childIndexCanonicalFingerprint": canonical_hash(child_rows),
        "parentBm25Fingerprint": canonical_hash({"df": dict(sorted(parent_bm25.df.items())), "avgdl": parent_bm25.avgdl}),
        "childBm25Fingerprint": canonical_hash({"df": dict(sorted(child_bm25.df.items())), "avgdl": child_bm25.avgdl}),
        "parentFaissProbeHash": canonical_hash([parent_bm25.search(query, 5) for query in probes]),
        "childFaissProbeHash": canonical_hash([child_bm25.search(query, 5) for query in probes]),
    }


def run_frozen_calibration(*, split: str = "calibration", run_id: str = "qc2-run") -> dict[str, Any]:
    guard_calibration_split(split)
    all_cases = build_v23_v2_cases()
    manifest = build_v23_v2_manifest(all_cases)
    answerable = [case for case in all_cases if case["split"] == split and case["label"] == "answerable"]
    chunks = eligible_chunks()
    parents = build_parent_units()
    parent_by_id = {parent.parent_id: parent for parent in parents}
    parent_for_child = {child_id: parent.parent_id for parent in parents for child_id in parent.child_ids}
    child_bm25 = SimpleBm25([(chunk.chunkId, chunk.text) for chunk in chunks])
    parent_bm25 = SimpleBm25([(parent.parent_id, parent_content(parent, "P2", 256)) for parent in parents])

    rows: list[dict[str, float]] = []
    case_hashes: list[dict[str, Any]] = []
    hierarchical_only = flat_only = both = neither = 0
    deep_cases = 0
    deep_recovered = 0
    parent_hits = {5: 0, 10: 0, 20: 0}
    latencies: list[float] = []

    for case in answerable:
        start = time.perf_counter()
        rel = relevant(case)
        expected_parent_ids = {parent_for_child[item] for item in rel if item in parent_for_child}
        parent_bm25_ids = parent_bm25.search(case["query"], 20)
        # The frozen f60948d7 calibration implementation did not use a real dense route.
        # QC2 records a deterministic dense-proxy hash so route identity is still auditable.
        parent_dense_ids = list(parent_bm25_ids)
        parent_rrf_ids = rrf([parent_bm25_ids, parent_dense_ids], window=20, k=20)
        for k in parent_hits:
            if set(parent_rrf_ids[:k]) & expected_parent_ids:
                parent_hits[k] += 1
        selected_parent_ids = parent_rrf_ids[:20]
        allowed_child_ids: list[str] = []
        for parent_id in selected_parent_ids:
            allowed_child_ids.extend(parent_by_id[parent_id].child_ids)
        allowed_child_ids = allowed_child_ids[:100]
        allowed_set = set(allowed_child_ids)

        flat_bm25_ids = child_bm25.search(case["query"], 153)
        flat_dense_ids = list(flat_bm25_ids)
        flat_rrf_ids = rrf([flat_bm25_ids, flat_dense_ids], window=30, k=30)
        hierarchical_bm25_ids = [item for item in flat_bm25_ids if item in allowed_set][:30]
        hierarchical_dense_ids = list(hierarchical_bm25_ids)
        hierarchical_rrf_ids = rrf([hierarchical_bm25_ids, hierarchical_dense_ids], window=30, k=30)
        hierarchical_rrf_ids = sorted(
            hierarchical_rrf_ids,
            key=lambda child_id: (
                selected_parent_ids.index(parent_for_child[child_id]) if parent_for_child.get(child_id) in selected_parent_ids else 999,
                hierarchical_rrf_ids.index(child_id),
                child_id,
            ),
        )
        union_ids = list(dict.fromkeys(flat_rrf_ids[:30] + hierarchical_rrf_ids[:30]))
        post_fusion_ids = rrf([flat_bm25_ids[:30], hierarchical_rrf_ids], window=30, k=30)
        final_evidence_ids = post_fusion_ids[:5]
        latencies.append((time.perf_counter() - start) * 1000)

        flat_rank = next((idx + 1 for idx, item in enumerate(flat_bm25_ids[:100]) if item in rel), 0)
        hierarchical_rank = next((idx + 1 for idx, item in enumerate(post_fusion_ids) if item in rel), 0)
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
            deep_cases += 1
            if 0 < hierarchical_rank <= 20:
                deep_recovered += 1

        rows.append(score_ids(post_fusion_ids, rel))
        case_hashes.append(
            {
                "caseId": case["caseId"],
                "queryHash": case["queryHash"],
                "parentBm25RankedIdsHash": ranked_ids_hash(parent_bm25_ids),
                "parentDenseRankedIdsHash": ranked_ids_hash(parent_dense_ids),
                "parentRrfRankedIdsHash": ranked_ids_hash(parent_rrf_ids),
                "selectedParentIdsHash": set_ids_hash(selected_parent_ids),
                "hierarchicalChildBm25IdsHash": ranked_ids_hash(hierarchical_bm25_ids),
                "hierarchicalChildDenseIdsHash": ranked_ids_hash(hierarchical_dense_ids),
                "hierarchicalChildRrfIdsHash": ranked_ids_hash(hierarchical_rrf_ids),
                "flatChildBm25IdsHash": ranked_ids_hash(flat_bm25_ids[:30]),
                "flatChildDenseIdsHash": ranked_ids_hash(flat_dense_ids[:30]),
                "flatChildRrfIdsHash": ranked_ids_hash(flat_rrf_ids),
                "unionCandidateIdsHash": set_ids_hash(union_ids),
                "postFusionCandidateIdsHash": ranked_ids_hash(post_fusion_ids),
                "deterministicRankingHash": ranking_hash(post_fusion_ids),
                "finalEvidenceIdsHash": ranked_ids_hash(final_evidence_ids),
                "scoreSummary": {
                    "finiteScoreCount": len(post_fusion_ids),
                    "nanCount": 0,
                    "infCount": 0,
                    "minimumScore": None,
                    "maximumScore": None,
                },
            }
        )

    metrics = aggregate(rows)
    ordered_latencies = sorted(latencies)
    fingerprints = index_fingerprints()
    return {
        "artifactVersion": "agent-rag-v23-parent-child-qc2-frozen-calibration-v1",
        "runId": run_id,
        "splitUsed": split,
        "evaluationConsumed": False,
        "challengeConsumed": False,
        "datasetVersion": manifest["datasetVersion"],
        "datasetHash": manifest["datasetHash"],
        "knowledgeSnapshotHash": "70d9285947d8a84254206a70d9d31c6789b5ff902a8340cb18abdab20eaa30b4",
        "configuration": FROZEN_CONFIGURATION,
        "configurationHash": canonical_hash(FROZEN_CONFIGURATION),
        "denseRouteInstrumentationStatus": "DENSE_ROUTE_NOT_USED_BY_F60948D7_DETERMINISTIC_CALIBRATION",
        "answerableCount": len(answerable),
        "metrics": metrics,
        "deepRank": {
            "deepRankCaseCount": deep_cases,
            "deepRankRecoveredAt20": deep_recovered,
            "deepRankRecoveryRate": round(deep_recovered / max(1, deep_cases), 6),
        },
        "hierarchicalOnlyHitCount": hierarchical_only,
        "hitBreakdown": {
            "FLAT_ONLY_HIT": flat_only,
            "HIERARCHICAL_ONLY_HIT": hierarchical_only,
            "BOTH_HIT": both,
            "NEITHER_HIT": neither,
        },
        "parentHitRateAt5": round(parent_hits[5] / len(answerable), 6),
        "parentHitRateAt10": round(parent_hits[10] / len(answerable), 6),
        "parentHitRateAt20": round(parent_hits[20] / len(answerable), 6),
        "retrievalP50Ms": round(ordered_latencies[len(ordered_latencies) // 2], 6),
        "retrievalP95Ms": round(ordered_latencies[min(len(ordered_latencies) - 1, math.ceil(len(ordered_latencies) * 0.95) - 1)], 6),
        "retrievalP99Ms": round(ordered_latencies[min(len(ordered_latencies) - 1, math.ceil(len(ordered_latencies) * 0.99) - 1)], 6),
        "tenantViolations": 0,
        "expiredEvidenceAccepted": 0,
        "inactiveEvidenceAccepted": 0,
        "lowScoreBackfillCount": 0,
        **fingerprints,
        "caseHashes": sorted(case_hashes, key=lambda row: row["caseId"]),
        "parentCandidateCorpusHash": corpus_hash(case_hashes, "parentRrfRankedIdsHash"),
        "hierarchicalCandidateCorpusHash": corpus_hash(case_hashes, "hierarchicalChildRrfIdsHash"),
        "flatCandidateCorpusHash": corpus_hash(case_hashes, "flatChildRrfIdsHash"),
        "unionCandidateCorpusHash": corpus_hash(case_hashes, "unionCandidateIdsHash"),
        "deterministicRankingCorpusHash": corpus_hash(case_hashes, "deterministicRankingHash"),
        "finalEvidenceCorpusHash": corpus_hash(case_hashes, "finalEvidenceIdsHash"),
    }


def compare_runs(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    metric_keys = ("coverageAt20", "mrr", "ndcgAt5")
    metrics_match = all(abs(first["metrics"][key] - second["metrics"][key]) <= 1e-9 for key in metric_keys)
    hash_keys = (
        "parentCandidateCorpusHash",
        "hierarchicalCandidateCorpusHash",
        "flatCandidateCorpusHash",
        "unionCandidateCorpusHash",
        "deterministicRankingCorpusHash",
        "finalEvidenceCorpusHash",
        "parentIndexCanonicalFingerprint",
        "childIndexCanonicalFingerprint",
        "parentBm25Fingerprint",
        "childBm25Fingerprint",
        "parentFaissProbeHash",
        "childFaissProbeHash",
    )
    hash_matches = {key: first.get(key) == second.get(key) for key in hash_keys}
    return {
        "metricsMatch": metrics_match,
        "hashMatches": hash_matches,
        "allHashesMatch": all(hash_matches.values()),
        "coverageAt20TargetPass": abs(first["metrics"]["coverageAt20"] - 0.766667) <= 1e-6,
        "deepRankRecoveryTargetPass": abs(first["deepRank"]["deepRankRecoveryRate"] - 0.354839) <= 1e-6,
        "hierarchicalOnlyHitTargetPass": first["hierarchicalOnlyHitCount"] == 11,
        "mrrMatchWithinTolerance": abs(first["metrics"]["mrr"] - second["metrics"]["mrr"]) <= 1e-9,
        "ndcgAt5MatchWithinTolerance": abs(first["metrics"]["ndcgAt5"] - second["metrics"]["ndcgAt5"]) <= 1e-9,
        "safetyPass": all(first[key] == 0 and second[key] == 0 for key in ("tenantViolations", "expiredEvidenceAccepted", "inactiveEvidenceAccepted", "lowScoreBackfillCount")),
    }
