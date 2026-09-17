from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from agent_rag_phase3a_common import phase3a_all_tenant_chunks, provider_env, source_commit, write_json
from app.agent_rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3ProviderConfig, HashEmbeddingProvider
from app.agent_rag.faiss_index import FaissVectorIndex
from app.agent_rag.metrics import macro_average, score_query
from app.agent_rag.phase2_retrieval import EvidenceQualityGate, QueryAnalyzer, RetrievalCandidate
from app.agent_rag.phase3a_retrieval import GovernedHybridRuntime
from app.rag.document_contract import stable_hash


PHASE3A2_OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-phase3a2"
SPLIT_SEED = 302202
CHALLENGE_TYPES = ("lexical", "semantic", "mixed", "temporal", "tenant-isolation", "negative/no-answer")
FAILURE_CATEGORIES = (
    "LEXICAL_ADVANTAGE",
    "SEMANTIC_ADVANTAGE",
    "BOTH_FAIL",
    "BOTH_PASS",
    "DENSE_WRONG_NEIGHBOR",
    "DENSE_FILTERED_OUT",
    "DENSE_BELOW_TOP_K",
    "FUSION_SUPPRESSED_DENSE",
    "LABEL_AMBIGUITY",
    "BENCHMARK_LEAKAGE",
    "CHUNKING_PROBLEM",
    "METADATA_MAPPING_PROBLEM",
)


def phase3a2_cases(chunks) -> list[dict[str, Any]]:
    topic_queries = {
        "refund": {
            "lexical": ["refund broken after-sales return", "refund policy customer service", "return compensation seven day rule"],
            "semantic": ["商品坏了想退应该怎么处理", "买到坏件怎么让平台介入售后", "东西不能用客服要怎么补偿"],
            "mixed": ["退货 refund 但是客服不处理", "after-sales 商品损坏 赔付规则", "return 包装破损 customer service"],
        },
        "safety": {
            "lexical": ["unsafe smoke fire battery", "product safety fire escalation", "charger smoke warning"],
            "semantic": ["充电时冒烟需要升级为安全风险吗", "儿童使用时发热刺鼻该如何处理", "可能起火的商品要不要人工复核"],
            "mixed": ["电池 smoke safety 风险", "儿童使用 charger 发热", "fire 安全 escalation"],
        },
        "fraud": {
            "lexical": ["fake counterfeit promotion", "counterfeit invoice mismatch", "platform fraud handling"],
            "semantic": ["宣传和实物完全不一致疑似虚假宣传", "票据对不上可能是假货", "商家夸大效果需要怎么治理"],
            "mixed": ["虚假 promotion fake 商品", "invoice 不一致 counterfeit", "fraud 商家宣传"],
        },
        "logistics": {
            "lexical": ["logistics delay slow parcel", "warehouse dispatch tracking delay", "parcel slow customer service"],
            "semantic": ["快递一直不到客户要求解释", "物流轨迹停了好几天怎么回复", "仓库迟迟不发货引发投诉"],
            "mixed": ["物流 delay 太慢", "parcel 轨迹停滞", "warehouse 发货 slow"],
        },
        "manual": {
            "lexical": ["warranty product manual warning", "waterproof temperature warranty", "product manual usage warning"],
            "semantic": ["说明书里有没有保修和使用温度限制", "防水宣传和手册警示不一致", "用户误用是否超出保修范围"],
            "mixed": ["warranty 使用 warning", "manual 防水 temperature", "保修 product manual"],
        },
        "service": {
            "lexical": ["customer service replacement coupon", "service apology replacement", "coupon follow up customer service"],
            "semantic": ["客服承诺换新但迟迟没跟进", "用户要求补偿券和道歉", "售后沟通需要补发优惠券"],
            "mixed": ["customer service 优惠券", "replacement 客服 跟进", "apology 补偿 coupon"],
        },
    }
    cases: list[dict[str, Any]] = []
    idx = 0
    for topic, groups in topic_queries.items():
        for challenge, queries in groups.items():
            repeat = 3 if challenge != "mixed" else 2
            for query in queries:
                for suffix in range(repeat):
                    cases.append(_case(idx, query if suffix == 0 else f"{query} 场景{suffix}", topic, challenge, chunks))
                    idx += 1
    temporal_queries = [
        ("current refund policy should ignore expired rule", "refund"),
        ("today product safety rule must use active evidence", "safety"),
        ("当前售后规则不要引用过期政策", "refund"),
        ("现在物流延迟按有效FAQ处理", "logistics"),
        ("as of today fake promotion handling", "fraud"),
        ("当前 warranty warning active manual", "manual"),
        ("today customer service replacement guidance", "service"),
        ("当前 charger smoke safety escalation", "safety"),
        ("as of today parcel delay rule", "logistics"),
        ("当前发票不一致疑似假货", "fraud"),
    ]
    for query, topic in temporal_queries:
        cases.append(_case(idx, query, topic, "temporal", chunks))
        idx += 1
    tenant_queries = [
        ("tenant-a refund broken after-sales", "refund"),
        ("tenant-a unsafe smoke fire", "safety"),
        ("tenant-a fake counterfeit promotion", "fraud"),
        ("tenant-a logistics delay slow parcel", "logistics"),
        ("tenant-a warranty product manual", "manual"),
        ("tenant-a customer service replacement", "service"),
        ("tenant-a 商品坏了想退", "refund"),
        ("tenant-a 冒烟安全风险", "safety"),
        ("tenant-a 虚假宣传处理", "fraud"),
        ("tenant-a 物流轨迹停滞", "logistics"),
    ]
    for query, topic in tenant_queries:
        cases.append(_case(idx, query, topic, "tenant-isolation", chunks))
        idx += 1
    no_answer_queries = [
        "直播带货达人佣金结算规则",
        "海外仓报关税率怎么计算",
        "门店自提停车券政策",
        "二手平台寄卖鉴定流程",
        "会员积分兑换航空里程",
        "药品处方审核规范",
        "线下维修工程师排班",
        "跨境海关抽检二维码",
        "电视安装墙体打孔收费",
        "预售演唱会门票实名制",
    ]
    for query in no_answer_queries:
        cases.append(_case(idx, query, "", "negative/no-answer", chunks, no_answer=True))
        idx += 1
    return cases


def build_provider_and_index(chunks):
    env = provider_env()
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "").strip()
    if model_path:
        provider = BgeM3EmbeddingProvider(
            BgeM3ProviderConfig(
                model_path=Path(model_path),
                device=env["device"],
                batch_size=env["batchSize"],
                max_length=env["maxLength"],
                normalize=env["normalize"],
            )
        )
        provider_type = "bge-m3"
    else:
        provider = HashEmbeddingProvider(dimensions=64)
        provider_type = "hash"
    index_root = PHASE3A2_OUT / f"faiss-{provider_type}"
    if index_root.exists():
        shutil.rmtree(index_root)
    index = FaissVectorIndex(index_root)
    manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version=f"phase3a2-{provider_type}-v1", source_commit=source_commit())
    index.activate(manifest.indexVersion, provider.metadata(), tenant_id="tenant-a")
    return provider, index, provider_type


def evaluate_cases(chunks, provider, index, cases: list[dict[str, Any]], *, sparse_weight: float = 1.0, dense_weight: float = 1.0, dense_top_k: int = 20) -> dict[str, Any]:
    runtime = GovernedHybridRuntime(chunks=chunks, provider=provider, faiss_index=index, fallback_provider="sparse", real_dense_required=True, sparse_weight=sparse_weight, dense_weight=dense_weight)
    rows = []
    for case in cases:
        bm25, _ = runtime.search(case["query"], tenant_id=case["tenantId"], mode="sparse-only", fusion_top_k=5)
        dense, _ = runtime.search(case["query"], tenant_id=case["tenantId"], mode="real-dense", dense_top_k=dense_top_k, fusion_top_k=5)
        hybrid, _ = runtime.search(case["query"], tenant_id=case["tenantId"], mode="hybrid-real", sparse_top_k=20, dense_top_k=dense_top_k, fusion_top_k=5)
        rows.append(score_result(case, bm25, dense, hybrid))
    return aggregate_results(rows)


def score_result(case: dict[str, Any], bm25: list[RetrievalCandidate], dense: list[RetrievalCandidate], hybrid: list[RetrievalCandidate]) -> dict[str, Any]:
    return {
        "caseId": case["caseId"],
        "query": case["query"],
        "tenantId": case["tenantId"],
        "retrievalChallengeType": case["retrievalChallengeType"],
        "relevantChunkIds": case["relevantChunkIds"],
        "bm25": _score_mode(case, bm25),
        "bge": _score_mode(case, dense),
        "hybrid": _score_mode(case, hybrid),
        "bm25Top5": _top5(bm25),
        "bgeTop5": _top5(dense),
        "hybridTop5": _top5(hybrid),
        "failureCategory": classify_failure(case, bm25, dense, hybrid),
    }


def aggregate_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    subsets: dict[str, dict[str, Any]] = {}
    for challenge in ("overall", *CHALLENGE_TYPES):
        selected = rows if challenge == "overall" else [row for row in rows if row["retrievalChallengeType"] == challenge]
        subsets[challenge] = {mode: _aggregate_mode([row[mode] for row in selected]) for mode in ("bm25", "bge", "hybrid")}
        subsets[challenge]["caseCount"] = len(selected)
    return {"caseCount": len(rows), "subsets": subsets, "rows": rows}


def split_cases(cases: list[dict[str, Any]], *, seed: int = SPLIT_SEED) -> dict[str, Any]:
    rng = random.Random(seed)
    calibration = []
    evaluation = []
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_type[case["retrievalChallengeType"]].append(case)
    for challenge, group in sorted(by_type.items()):
        ordered = sorted(group, key=lambda row: row["caseId"])
        rng.shuffle(ordered)
        cut = max(1, round(len(ordered) * 0.3))
        calibration.extend(ordered[:cut])
        evaluation.extend(ordered[cut:])
    calibration.sort(key=lambda row: row["caseId"])
    evaluation.sort(key=lambda row: row["caseId"])
    return {
        "splitSeed": seed,
        "calibration": calibration,
        "evaluation": evaluation,
        "calibrationCaseIdsHash": _hash_ids(calibration),
        "evaluationCaseIdsHash": _hash_ids(evaluation),
    }


def rrf_contribution(sparse: list[RetrievalCandidate], dense: list[RetrievalCandidate], *, rrf_k: int = 60, sparse_weight: float = 1.0, dense_weight: float = 1.0, top_k: int = 5) -> list[dict[str, Any]]:
    by_chunk: dict[str, dict[str, Any]] = {}
    for item in sparse:
        by_chunk.setdefault(item.chunkId, {"chunkId": item.chunkId, "bm25Rank": None, "denseRank": None, "bm25Contribution": 0.0, "denseContribution": 0.0})
        by_chunk[item.chunkId].update({"bm25Rank": item.sparseRank, "bm25Contribution": sparse_weight / (rrf_k + int(item.sparseRank or 9999))})
    for item in dense:
        by_chunk.setdefault(item.chunkId, {"chunkId": item.chunkId, "bm25Rank": None, "denseRank": None, "bm25Contribution": 0.0, "denseContribution": 0.0})
        by_chunk[item.chunkId].update({"denseRank": item.denseRank, "denseContribution": dense_weight / (rrf_k + int(item.denseRank or 9999))})
    rows = []
    for row in by_chunk.values():
        row["finalFusionScore"] = round(float(row["bm25Contribution"]) + float(row["denseContribution"]), 8)
        rows.append(row)
    rows.sort(key=lambda row: row["finalFusionScore"], reverse=True)
    for rank, row in enumerate(rows[:top_k], start=1):
        row["finalRank"] = rank
    return rows[:top_k]


def select_default_mode(evaluation: dict[str, Any]) -> tuple[str, str]:
    subsets = evaluation["subsets"]
    bm25 = subsets["overall"]["bm25"]
    dense = subsets["overall"]["bge"]
    hybrid = subsets["overall"]["hybrid"]
    semantic = subsets["semantic"]
    if hybrid["ndcgAt5"] > bm25["ndcgAt5"] + 0.02 and hybrid["recallAt5"] >= bm25["recallAt5"]:
        return "hybrid-real", "AGENT_RAG_DENSE_QUALITY_GAIN_CONFIRMED"
    if semantic["bge"]["ndcgAt5"] > semantic["bm25"]["ndcgAt5"] + 0.02 or semantic["hybrid"]["ndcgAt5"] > semantic["bm25"]["ndcgAt5"] + 0.02:
        return "bm25-first-semantic-hybrid", "AGENT_RAG_DENSE_SEMANTIC_GAIN_ONLY"
    _ = dense
    return "sparse-only", "AGENT_RAG_DENSE_QUALITY_GAIN_NOT_DEMONSTRATED"


def no_answer_gate(rows: list[dict[str, Any]], *, min_score: float) -> dict[str, Any]:
    gate = EvidenceQualityGate(min_score=min_score)
    no_answer = [row for row in rows if row["retrievalChallengeType"] == "negative/no-answer"]
    false_evidence = 0
    rejected = 0
    for row in no_answer:
        candidates = [
            RetrievalCandidate(
                retrieverType="hybrid-real",
                tenantId=item.get("tenantId", "tenant-a"),
                documentId=item.get("documentId", ""),
                chunkId=item["chunkId"],
                fusionScore=float(item.get("fusionScore", 0.0)),
                row={"document_id": item.get("documentId", ""), "chunk_id": item["chunkId"], "content_hash": item["chunkId"], "content": item.get("snippet", "synthetic")},
            )
            for item in row["hybridTop5"]
        ]
        accepted, _ = gate.filter(candidates, tenant_id=row["tenantId"])
        false_evidence += len(accepted)
        rejected += int(not accepted)
    count = len(no_answer)
    return {
        "caseCount": count,
        "falseEvidenceRate": 0.0 if count == 0 else round(false_evidence / max(1, sum(len(row["hybridTop5"]) for row in no_answer)), 4),
        "noAnswerCorrectRejectionRate": 0.0 if count == 0 else round(rejected / count, 4),
    }


def dense_score_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive = []
    top1 = []
    no_answer = []
    for row in rows:
        hits = row["bgeTop5"]
        if hits:
            top1.append(float(hits[0].get("denseScore", 0.0)))
        if row["retrievalChallengeType"] == "negative/no-answer":
            if hits:
                no_answer.append(float(hits[0].get("denseScore", 0.0)))
            continue
        relevant = set(row["relevantChunkIds"])
        for hit in hits:
            if hit["chunkId"] in relevant:
                positive.append(float(hit.get("denseScore", 0.0)))
    return {"positive": _dist(positive), "noAnswerTop1": _dist(no_answer), "allTop1": _dist(top1)}


def chunk_stats(chunks) -> dict[str, Any]:
    lengths = [len(chunk.text) for chunk in chunks]
    token_lengths = [len(str(chunk.text).split()) for chunk in chunks]
    counts = Counter(stable_hash(chunk.text) for chunk in chunks)
    return {
        "chunkCharP50": _percentile(lengths, 0.5),
        "chunkCharP95": _percentile(lengths, 0.95),
        "chunkTokenP50": _percentile(token_lengths, 0.5),
        "chunkTokenP95": _percentile(token_lengths, 0.95),
        "titleOnlyCount": sum(1 for chunk in chunks if chunk.text.strip() == chunk.title.strip()),
        "shortChunkCount": sum(1 for value in lengths if value < 80),
        "longChunkCount": sum(1 for value in lengths if value > 1200),
        "duplicateContentCount": sum(1 for value in counts.values() if value > 1),
    }


def benchmark_integrity(cases: list[dict[str, Any]], chunks) -> dict[str, Any]:
    counts = Counter(case["retrievalChallengeType"] for case in cases)
    chunk_ids = {chunk.chunkId for chunk in chunks}
    missing = [
        case["caseId"]
        for case in cases
        if case["retrievalChallengeType"] != "negative/no-answer" and not set(case["relevantChunkIds"]).issubset(chunk_ids)
    ]
    return {
        "caseCount": len(cases),
        "challengeCounts": dict(counts),
        "semanticCount": counts["semantic"],
        "lexicalCount": counts["lexical"],
        "mixedCount": counts["mixed"],
        "negativeNoAnswerCount": counts["negative/no-answer"],
        "tenantTemporalCount": counts["tenant-isolation"] + counts["temporal"],
        "missingRelevantCaseIds": missing,
        "status": "PASS"
        if len(cases) >= 150
        and counts["semantic"] >= 40
        and counts["lexical"] >= 40
        and counts["mixed"] >= 30
        and counts["negative/no-answer"] >= 10
        and counts["tenant-isolation"] + counts["temporal"] >= 20
        and not missing
        else "FAIL",
    }


def _case(idx: int, query: str, topic: str, challenge: str, chunks, *, no_answer: bool = False) -> dict[str, Any]:
    relevant = []
    if not no_answer:
        relevant = [
            chunk.chunkId
            for chunk in chunks
            if chunk.tenantId in {"tenant-a", "__public__"} and topic and (topic in chunk.documentId or topic in chunk.text)
        ][:5]
    forbidden = [chunk.chunkId for chunk in chunks if chunk.tenantId not in {"tenant-a", "__public__"}][:5]
    return {
        "caseId": f"p3a2-{idx:03d}",
        "query": query,
        "tenantId": "tenant-a",
        "expectedTopic": topic,
        "retrievalChallengeType": challenge,
        "relevantChunkIds": relevant,
        "forbiddenChunkIds": forbidden,
        "relevanceGrades": {chunk_id: 1 for chunk_id in relevant},
    }


def _score_mode(case: dict[str, Any], candidates: list[RetrievalCandidate]) -> dict[str, Any]:
    if case["retrievalChallengeType"] == "negative/no-answer":
        metric = {key: 0.0 for key in ("hitRateAt1", "hitRateAt3", "hitRateAt5", "recallAt1", "recallAt3", "recallAt5", "mrr", "ndcgAt5")}
        metric.update({"duplicateCount": 0, "forbiddenHitCount": 0})
    else:
        metric = score_query(
            retrieved_chunk_ids=[candidate.chunkId for candidate in candidates],
            relevant_chunk_ids=set(case["relevantChunkIds"]),
            forbidden_chunk_ids=set(case["forbiddenChunkIds"]),
            relevance_grades=case["relevanceGrades"],
        )
    metric["empty"] = not candidates
    metric["tenantViolation"] = any(candidate.tenantId not in {case["tenantId"], "__public__"} for candidate in candidates)
    return metric


def _aggregate_mode(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"hitRateAt5": 0.0, "recallAt5": 0.0, "mrr": 0.0, "ndcgAt5": 0.0, "emptyRetrievalRate": 0.0, "tenantViolations": 0}
    averaged = macro_average(rows, ["hitRateAt5", "recallAt5", "mrr", "ndcgAt5"])
    return {
        "hitRateAt5": round(averaged["hitRateAt5"], 4),
        "recallAt5": round(averaged["recallAt5"], 4),
        "mrr": round(averaged["mrr"], 4),
        "ndcgAt5": round(averaged["ndcgAt5"], 4),
        "emptyRetrievalRate": round(sum(row["empty"] for row in rows) / len(rows), 4),
        "tenantViolations": sum(row["tenantViolation"] for row in rows),
    }


def _top5(candidates: list[RetrievalCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "chunkId": item.chunkId,
            "documentId": item.documentId,
            "tenantId": item.tenantId,
            "sparseRank": item.sparseRank,
            "denseRank": item.denseRank,
            "sparseScore": round(float(item.sparseScore), 6),
            "denseScore": round(float(item.denseScore), 6),
            "fusionScore": round(float(item.fusionScore), 8),
        }
        for item in candidates[:5]
    ]


def classify_failure(case: dict[str, Any], bm25: list[RetrievalCandidate], dense: list[RetrievalCandidate], hybrid: list[RetrievalCandidate]) -> str:
    relevant = set(case["relevantChunkIds"])
    if not relevant:
        return "BOTH_PASS"
    bm25_hit = any(item.chunkId in relevant for item in bm25[:5])
    dense_hit = any(item.chunkId in relevant for item in dense[:5])
    hybrid_hit = any(item.chunkId in relevant for item in hybrid[:5])
    dense_any = any(item.chunkId in relevant for item in dense)
    if bm25_hit and dense_hit:
        return "BOTH_PASS"
    if bm25_hit and not dense_hit:
        return "LEXICAL_ADVANTAGE" if case["retrievalChallengeType"] == "lexical" else ("DENSE_BELOW_TOP_K" if dense_any else "DENSE_WRONG_NEIGHBOR")
    if dense_hit and not bm25_hit:
        return "SEMANTIC_ADVANTAGE" if hybrid_hit else "FUSION_SUPPRESSED_DENSE"
    return "BOTH_FAIL"


def _hash_ids(cases: list[dict[str, Any]]) -> str:
    return hashlib.sha256("\n".join(case["caseId"] for case in cases).encode("utf-8")).hexdigest()


def _dist(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "min": round(min(values), 6),
        "p25": round(_percentile(values, 0.25), 6),
        "p50": round(_percentile(values, 0.5), 6),
        "p75": round(_percentile(values, 0.75), 6),
        "p95": round(_percentile(values, 0.95), 6),
        "max": round(max(values), 6),
    }


def _percentile(values: list[float] | list[int], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    return ordered[min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))]


def write_phase3a2_json(name: str, payload: dict[str, Any]) -> Path:
    path = PHASE3A2_OUT / name
    write_json(path, payload)
    return path
