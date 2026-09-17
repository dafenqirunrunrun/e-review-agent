from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.agent_rag.eligibility import evaluate_evidence_eligibility  # noqa: E402
from app.agent_rag.phase2_retrieval import RetrievalCandidate  # noqa: E402
from app.agent_rag.reranker import GovernedReranker, RerankerConfig  # noqa: E402
from app.rag.document_contract import stable_hash  # noqa: E402
from v23_retrieval_common import EVALUATION_TIME_UTC, OUT, build_dataset_manifest, build_v23_cases, hash_json, prepare_runtime, read_json, sparse_top_ids, write_json, write_text  # noqa: E402
from run_v22_real_reranker_benchmark import benchmark_payload  # noqa: E402


DOCS = ROOT / "docs" / "retrieval-optimization"
CONFIG_OUT = ROOT / "config" / "qualification"
K_VALUES = (5, 10, 20, 30, 50, 75, 100)
FINAL_K = 5
RRF_CONSTANT = 60


@dataclass(frozen=True)
class FusionConfig:
    bm25RetrieveK: int
    denseRetrieveK: int
    rrfRankWindow: int
    postFusionCandidateK: int
    maximumFinalK: int = FINAL_K
    rrfRankConstant: int = RRF_CONSTANT
    bm25Weight: float = 1.0
    denseWeight: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "bm25RetrieveK": self.bm25RetrieveK,
            "denseRetrieveK": self.denseRetrieveK,
            "rrfRankWindow": self.rrfRankWindow,
            "postFusionCandidateK": self.postFusionCandidateK,
            "maximumFinalK": self.maximumFinalK,
            "rrfRankConstant": self.rrfRankConstant,
            "bm25Weight": self.bm25Weight,
            "denseWeight": self.denseWeight,
            "allowBackfill": False,
        }

    @property
    def configuration_hash(self) -> str:
        return hash_json(self.as_dict())


def load_dataset() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = build_v23_cases()
    return cases, build_dataset_manifest(cases)


def split_answerable(cases: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    return [case for case in cases if case["split"] == split and case["label"] == "answerable"]


def split_no_answer(cases: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    return [case for case in cases if case["split"] == split and case["label"] == "no_answer"]


def retrieve_depths(case: dict[str, Any], runtime: Any, *, bm25_k: int = 100, dense_k: int = 100) -> tuple[list[RetrievalCandidate], list[RetrievalCandidate]]:
    bm25_ids = sparse_top_ids(case["query"], case["tenantId"], bm25_k)
    dense_candidates, _trace = runtime.search(
        case["query"],
        tenant_id=case["tenantId"],
        mode="real-dense",
        sparse_top_k=dense_k,
        dense_top_k=dense_k,
        fusion_top_k=dense_k,
        rerank_top_k=None,
        evaluation_time_utc=EVALUATION_TIME_UTC,
    )
    dense_by_id = {item.chunkId: item for item in dense_candidates}
    row_by_id = {item.chunkId: item for item in dense_candidates}
    bm25_candidates: list[RetrievalCandidate] = []
    chunks = {chunk.chunkId: chunk for chunk in benchmark_payload()["chunks"]}
    for rank, chunk_id in enumerate(bm25_ids, start=1):
        base = row_by_id.get(chunk_id)
        if base:
            row = base.row
            tenant = base.tenantId
            document = base.documentId
        else:
            chunk = chunks.get(chunk_id)
            if not chunk:
                continue
            row = chunk.as_retriever_row()
            tenant = chunk.tenantId
            document = chunk.documentId
        bm25_candidates.append(
            RetrievalCandidate(
                retrieverType="sparse-only",
                tenantId=tenant,
                documentId=document,
                chunkId=chunk_id,
                sparseRank=rank,
                rawRank=rank,
                fusionRank=rank,
                fusionScore=1.0 / rank,
                row=row,
            )
        )
    dense_ranked = [
        RetrievalCandidate(**{**item.__dict__, "denseRank": rank, "rawRank": rank, "fusionRank": rank})
        for rank, item in enumerate(dense_candidates[:dense_k], start=1)
    ]
    return bm25_candidates[:bm25_k], dense_ranked


def raw_union_ids(bm25: list[RetrievalCandidate], dense: list[RetrievalCandidate], k: int = 100) -> list[str]:
    seen = set()
    out = []
    for item in bm25[:k] + dense[:k]:
        if item.chunkId not in seen:
            seen.add(item.chunkId)
            out.append(item.chunkId)
    return out


def budgeted_union_ids(bm25: list[RetrievalCandidate], dense: list[RetrievalCandidate], n: int) -> list[str]:
    by_id: dict[str, int] = {}
    for rank, item in enumerate(bm25, start=1):
        by_id[item.chunkId] = min(by_id.get(item.chunkId, 10_000), rank)
    for rank, item in enumerate(dense, start=1):
        by_id[item.chunkId] = min(by_id.get(item.chunkId, 10_000), rank)
    return [chunk_id for chunk_id, _rank in sorted(by_id.items(), key=lambda row: (row[1], row[0]))[:n]]


def rrf_fuse(bm25: list[RetrievalCandidate], dense: list[RetrievalCandidate], config: FusionConfig) -> list[RetrievalCandidate]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in bm25[: min(config.bm25RetrieveK, config.rrfRankWindow)]:
        by_id.setdefault(item.chunkId, {"candidate": item, "sparseRank": None, "denseRank": None})
        by_id[item.chunkId]["candidate"] = item
        by_id[item.chunkId]["sparseRank"] = item.sparseRank
    for item in dense[: min(config.denseRetrieveK, config.rrfRankWindow)]:
        by_id.setdefault(item.chunkId, {"candidate": item, "sparseRank": None, "denseRank": None})
        by_id[item.chunkId]["candidate"] = item
        by_id[item.chunkId]["denseRank"] = item.denseRank
    fused = []
    for chunk_id, value in by_id.items():
        sparse_rank = value["sparseRank"]
        dense_rank = value["denseRank"]
        score = 0.0
        if sparse_rank:
            score += config.bm25Weight / (config.rrfRankConstant + sparse_rank)
        if dense_rank:
            score += config.denseWeight / (config.rrfRankConstant + dense_rank)
        candidate = value["candidate"]
        fused.append(
            RetrievalCandidate(
                retrieverType="hybrid-real",
                tenantId=candidate.tenantId,
                documentId=candidate.documentId,
                chunkId=chunk_id,
                sparseRank=sparse_rank,
                denseRank=dense_rank,
                rawRank=min([rank for rank in [sparse_rank, dense_rank] if rank] or [9999]),
                fusionScore=round(score, 8),
                row=candidate.row,
            )
        )
    fused.sort(key=lambda item: (-item.fusionScore, item.rawRank, item.chunkId))
    return [RetrievalCandidate(**{**item.__dict__, "fusionRank": rank}) for rank, item in enumerate(fused[: config.postFusionCandidateK], start=1)]


def deterministic_rerank_ids(query: str, candidates: list[RetrievalCandidate], tenant_id: str) -> list[str]:
    result = GovernedReranker(RerankerConfig(requested_type="deterministic", candidate_k=len(candidates), final_k=FINAL_K)).rerank(
        query,
        candidates,
        top_k=FINAL_K,
        tenant_id=tenant_id,
        evaluation_time_utc=EVALUATION_TIME_UTC,
    )
    return [item.chunkId for item in result.candidates]


def case_relevant(case: dict[str, Any]) -> set[str]:
    return set(case["expectedRelevantChunkIds"]) | set(case["acceptableRelevantChunkIds"])


def score_list(ids: list[str], relevant: set[str], k_values: tuple[int, ...] = K_VALUES) -> dict[str, float]:
    deduped = []
    seen = set()
    for chunk_id in ids:
        if chunk_id not in seen:
            seen.add(chunk_id)
            deduped.append(chunk_id)
    total = max(1, len(relevant))
    out = {}
    for k in k_values:
        hits = len(set(deduped[:k]) & relevant)
        out[f"recallAt{k}"] = hits / total
        out[f"coverageAt{k}"] = 1.0 if hits else 0.0
    first = next((index + 1 for index, chunk_id in enumerate(deduped) if chunk_id in relevant), 0)
    out["mrr"] = 0.0 if not first else 1.0 / first
    out["ndcgAt5"] = 0.0 if not first or first > 5 else 1.0 / math.log2(first + 1)
    out["bestRelevantRank"] = float(first)
    return out


def score_raw_union(bm25: list[RetrievalCandidate], dense: list[RetrievalCandidate], relevant: set[str]) -> dict[str, float]:
    out = {}
    full_for_rank = raw_union_ids(bm25, dense, 100)
    first = next((index + 1 for index, chunk_id in enumerate(full_for_rank) if chunk_id in relevant), 0)
    for k in K_VALUES:
        ids = raw_union_ids(bm25, dense, k)
        hits = len(set(ids) & relevant)
        out[f"recallAt{k}"] = hits / max(1, len(relevant))
        out[f"coverageAt{k}"] = 1.0 if hits else 0.0
    out["mrr"] = 0.0 if not first else 1.0 / first
    out["ndcgAt5"] = 0.0 if not first or first > 5 else 1.0 / math.log2(first + 1)
    out["bestRelevantRank"] = float(first)
    return out


def aggregate(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    keys = [key for key in rows[0] if key != "bestRelevantRank"]
    out = {key: round(sum(float(row[key]) for row in rows) / len(rows), 6) for key in keys}
    ranks = [int(row["bestRelevantRank"]) for row in rows if row.get("bestRelevantRank")]
    out["missCount"] = len(rows) - len(ranks)
    out["caseCount"] = len(rows)
    return out


def latency(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if pct == 0.5:
        return round(float(median(ordered)), 3)
    return round(float(ordered[min(len(ordered) - 1, int(len(ordered) * pct))]), 3)


def evaluate_config(cases: list[dict[str, Any]], runtime: Any, config: FusionConfig) -> dict[str, Any]:
    rows = []
    rrf_scores = []
    rerank_scores = []
    raw_union_scores = []
    budgeted_scores = []
    bm25_scores = []
    dense_scores = []
    latencies = []
    violations = {"tenantViolations": 0, "expiredCandidatesAccepted": 0, "inactiveCandidatesAccepted": 0, "duplicateCandidates": 0, "lowScoreBackfillCount": 0}
    for case in cases:
        relevant = case_relevant(case)
        started = time.perf_counter()
        bm25, dense = retrieve_depths(case, runtime, bm25_k=max(100, config.bm25RetrieveK), dense_k=max(100, config.denseRetrieveK))
        fused = rrf_fuse(bm25, dense, config)
        latencies.append(round((time.perf_counter() - started) * 1000, 3))
        raw_union = raw_union_ids(bm25, dense, 100)
        budgeted = budgeted_union_ids(bm25[: config.bm25RetrieveK], dense[: config.denseRetrieveK], config.postFusionCandidateK)
        rerank_ids = deterministic_rerank_ids(case["query"], fused, case["tenantId"])
        bm25_scores.append(score_list([item.chunkId for item in bm25], relevant))
        dense_scores.append(score_list([item.chunkId for item in dense], relevant))
        rrf_scores.append(score_list([item.chunkId for item in fused], relevant))
        rerank_scores.append(score_list(rerank_ids, relevant, (5,)))
        raw_union_scores.append(score_raw_union(bm25, dense, relevant))
        budgeted_scores.append(score_list(budgeted, relevant))
        seen = set()
        for item in fused:
            if item.chunkId in seen:
                violations["duplicateCandidates"] += 1
            seen.add(item.chunkId)
            if item.tenantId not in {case["tenantId"], "__public__"}:
                violations["tenantViolations"] += 1
            decision = evaluate_evidence_eligibility(item, case["tenantId"], EVALUATION_TIME_UTC)
            if not decision.eligible and decision.reasonCode == "EXPIRED":
                violations["expiredCandidatesAccepted"] += 1
            if not decision.eligible and decision.reasonCode in {"INACTIVE", "DISABLED"}:
                violations["inactiveCandidatesAccepted"] += 1
        rows.append(
            {
                "caseId": case["caseId"],
                "queryIntent": case["queryIntent"],
                "relevantChunkIdsHash": hash_json(sorted(relevant)),
                "bm25BestRelevantRank": int(score_list([item.chunkId for item in bm25], relevant)["bestRelevantRank"]),
                "denseBestRelevantRank": int(score_list([item.chunkId for item in dense], relevant)["bestRelevantRank"]),
                "rawUnionBestRelevantRank": int(score_list(raw_union, relevant)["bestRelevantRank"]),
                "rrfBestRelevantRank": int(score_list([item.chunkId for item in fused], relevant)["bestRelevantRank"]),
            }
        )
    raw_metrics = aggregate(raw_union_scores)
    rrf_metrics = aggregate(rrf_scores)
    return {
        "configuration": config.as_dict(),
        "configurationHash": config.configuration_hash,
        "caseCount": len(cases),
        "bm25Metrics": aggregate(bm25_scores),
        "denseMetrics": aggregate(dense_scores),
        "rawUnionMetrics": raw_metrics,
        "unionBudgetedMetrics": aggregate(budgeted_scores),
        "rrfMetrics": rrf_metrics,
        "deterministicRerankerMetrics": aggregate(rerank_scores),
        "oracleCaptureRateAt20": round(rrf_metrics.get("coverageAt20", 0.0) / max(raw_metrics.get("coverageAt100", 0.0), 1e-9), 6),
        "oracleCaptureRateAt30": round(rrf_metrics.get("coverageAt30", 0.0) / max(raw_metrics.get("coverageAt100", 0.0), 1e-9), 6),
        "oracleCaptureRateAtSelectedK": round(rrf_metrics.get(f"coverageAt{config.postFusionCandidateK}", 0.0) / max(raw_metrics.get("coverageAt100", 0.0), 1e-9), 6),
        "latencyP50": latency(latencies, 0.5),
        "latencyP95": latency(latencies, 0.95),
        "latencyP99": latency(latencies, 0.99),
        "averageCandidateCount": config.postFusionCandidateK,
        "maximumCandidateCount": config.postFusionCandidateK,
        "memoryObservation": "not measured; candidate-only grid without model residency changes",
        **violations,
        "rowsLightHash": hash_json(rows),
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
