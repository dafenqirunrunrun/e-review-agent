from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.index_store import load_policy_chunks
from scripts.build_step233c_cn_challenge import (
    BOUNDARY,
    HARD_NEGATIVE,
    IMPLICIT,
    LONG_NOISY,
    MULTI_RISK,
    NORMAL,
    normalize_text,
)
from scripts.run_step233a_qwen_embedding_ab import content_root_hash


DATASET_VERSION = "step23.3c-cn-challenge-v2"
DEFAULT_OUTPUT = ROOT / "data" / "benchmarks" / "step233c_cn_challenge_v2.jsonl"
DEFAULT_REFLECTION_OUTPUT = ROOT / "data" / "benchmarks" / "step233c_reflection_scenarios_v2.jsonl"
DEFAULT_MANIFEST = ROOT / "data" / "benchmarks" / "step233c_cn_challenge_v2.manifest.json"
DEFAULT_CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
V1_DATASET = ROOT / "data" / "benchmarks" / "step233c_cn_ranking_challenge_v1.jsonl"


def _judgment(
    chunk_id: str,
    relevance: int,
    supports: tuple[str, ...],
    rationale: str,
    *,
    primary: bool = False,
) -> dict[str, Any]:
    return {
        "chunkId": chunk_id,
        "semanticRelevance": relevance,
        "supports": list(supports),
        "primaryPolicy": primary,
        "judgmentRationale": rationale,
    }


# Relevance is semantic relevance, not legal applicability. Source authority is
# stored separately so a platform rule is not silently treated as local law.
POLICY_PROFILES_V2: dict[str, list[dict[str, Any]]] = {
    "fake_fabricated": [
        _judgment("9c3dc9939e5eb8879caf3c5c", 3, ("fake_review",), "直接禁止虚构交易、编造用户评价。", primary=True),
        _judgment("b9a74381a55c2e2a5d531eee", 3, ("fake_review",), "直接覆盖不存在的评论者或并未使用商品的虚假评价。", primary=True),
        _judgment("ff0598d26200a4e201663451", 3, ("fake_review",), "直接覆盖未使用商品、员工或关联人员编造体验。", primary=True),
        _judgment("74340d2418d9fcfa599e41da", 3, ("fake_review", "rating_manipulation"), "直接覆盖非真实体验、多账号发布及付费评价。", primary=True),
        _judgment("84208b9327ce0af315cef11b", 2, ("fake_review",), "覆盖多账号重复发布，作为组织化虚假参与的补充依据。"),
    ],
    "rating_incentive": [
        _judgment("d75980ec05a8bcb347f5bf52", 3, ("rating_manipulation",), "直接禁止以特定评价倾向为条件提供补偿或奖励。", primary=True),
        _judgment("193384aae5a85267bb71d5a2", 3, ("rating_manipulation",), "直接覆盖付款、折扣、赠品换取评价修改或删除。", primary=True),
        _judgment("74340d2418d9fcfa599e41da", 3, ("rating_manipulation", "fake_review"), "直接覆盖有偿评价和以奖励换取评价。", primary=True),
        _judgment("5e45c7b9d11e097df49f7e14", 2, ("rating_manipulation", "fake_review"), "覆盖商家组织员工集中索取特定评价。"),
        _judgment("9c3dc9939e5eb8879caf3c5c", 1, ("fake_review",), "对虚假或误导性评价宣传提供一般性法律背景。"),
    ],
    "suppression_delete": [
        _judgment("2bee6c98575e591210bf2067", 3, ("review_suppression",), "明确规定平台不得删除消费者评价。", primary=True),
        _judgment("1b44f5da1082d2e258a9b675", 2, ("review_suppression", "harassment_or_abuse"), "覆盖通过威胁移除评价及按负面倾向压制展示。"),
        _judgment("352cc7c3321ebbb3ee8c8c7d", 2, ("review_suppression",), "说明基于评分或负面倾向压制评价的判断边界。"),
        _judgment("72db6bec63c837846684727a", 1, ("review_suppression",), "提供平台对虚假或偏置内容治理的一般背景。"),
    ],
    "suppression_threat": [
        _judgment("1b44f5da1082d2e258a9b675", 3, ("review_suppression", "harassment_or_abuse"), "直接覆盖用法律或人身威胁阻止、移除消费者评价。", primary=True),
        _judgment("2bee6c98575e591210bf2067", 2, ("review_suppression",), "明确消费者评价不得被平台删除。"),
        _judgment("a120af91026adec4e2a4e419", 1, ("harassment_or_abuse",), "提供骚扰行为的一般平台规范。"),
    ],
    "privacy_disclosure": [
        _judgment("f7c63a5ca6444c3d8bf2766b", 3, ("privacy_risk",), "直接涉及未经同意公开个人身份、医疗或联系信息。", primary=True),
        _judgment("e66578cf821a0e47b9e962ca", 2, ("privacy_risk",), "规定经营者收集和使用个人信息应遵守保护规则。"),
        _judgment("f9d2febf1911851cc59297b2", 1, ("privacy_risk",), "提供个人信息、隐私和商业秘密保密的一般法律背景。"),
    ],
    "after_sales_records": [
        _judgment("31b38d83c374476950d9bf66", 3, ("after_sales_risk",), "直接要求保存退换货和售后等交易信息。", primary=True),
        _judgment("a5d7486b9d28abc732aa76d1", 2, ("after_sales_risk",), "涉及质量担保、先行赔偿和消费者权益保障。"),
        _judgment("93326e9355a42652819655e3", 2, ("after_sales_risk",), "要求展示售后服务和实际经营主体信息。"),
    ],
    "after_sales_disclosure": [
        _judgment("93326e9355a42652819655e3", 3, ("after_sales_risk",), "直接要求展示售后服务及实际经营主体信息。", primary=True),
        _judgment("31b38d83c374476950d9bf66", 2, ("after_sales_risk",), "补充售后及退换货记录保存要求。"),
        _judgment("a5d7486b9d28abc732aa76d1", 1, ("after_sales_risk",), "提供消费者权益保障背景。"),
    ],
    "after_sales_compensation": [
        _judgment("a5d7486b9d28abc732aa76d1", 3, ("after_sales_risk",), "直接涉及质量担保、先行赔偿和追偿机制。", primary=True),
        _judgment("31b38d83c374476950d9bf66", 2, ("after_sales_risk",), "补充退换货和售后交易记录要求。"),
        _judgment("93326e9355a42652819655e3", 1, ("after_sales_risk",), "补充售后信息展示要求。"),
    ],
    "safety_product": [
        _judgment("eeecfa148cfe1159d4a3498f", 3, ("safety_or_fraud_risk",), "直接要求商品和服务保障人身、财产安全。", primary=True),
        _judgment("80f9b79fe54394c78c211e9c", 3, ("safety_or_fraud_risk",), "直接禁止提供不符合人身、财产安全要求的商品或服务。", primary=True),
        _judgment("25b39504f13e488f3e5ae074", 2, ("safety_or_fraud_risk",), "规定平台明知商品存在安全问题时的责任。"),
        _judgment("32171f295985f6c3669279e8", 2, ("safety_or_fraud_risk",), "补充平台对生命健康商品的审核和安全保障责任。"),
    ],
    "safety_platform": [
        _judgment("25b39504f13e488f3e5ae074", 3, ("safety_or_fraud_risk",), "直接规定平台明知安全风险而未采取措施时的责任。", primary=True),
        _judgment("32171f295985f6c3669279e8", 3, ("safety_or_fraud_risk",), "直接覆盖平台审核义务及生命健康商品安全保障。", primary=True),
        _judgment("eeecfa148cfe1159d4a3498f", 2, ("safety_or_fraud_risk",), "补充商品本身的人身和财产安全要求。"),
    ],
    "fraud_deception": [
        _judgment("733aa32c4fab815fefe98471", 3, ("safety_or_fraud_risk", "fake_review"), "直接涉及虚假或引人误解的商业宣传及安全责任。", primary=True),
        _judgment("9c3dc9939e5eb8879caf3c5c", 2, ("fake_review",), "覆盖虚假或误导性商业宣传。"),
        _judgment("eeecfa148cfe1159d4a3498f", 2, ("safety_or_fraud_risk",), "补充商品安全和禁止交易要求。"),
    ],
    "fraud_payment": [
        _judgment("2b830e6558f54bde857aeed4", 3, ("safety_or_fraud_risk",), "直接规定电子支付服务不符合安全要求造成损失时的责任。", primary=True),
        _judgment("960edf5b431f2e1a75fe12c0", 2, ("safety_or_fraud_risk",), "规定平台保障电子商务交易安全。"),
        _judgment("4ad43740494d51521fbccedb", 1, ("safety_or_fraud_risk",), "提供维护电子商务交易安全的一般背景。"),
    ],
    "harassment_general": [
        _judgment("a120af91026adec4e2a4e419", 3, ("harassment_or_abuse",), "直接禁止针对个人或商家的骚扰及煽动骚扰。", primary=True),
        _judgment("707d8b182fcab0cc98e0d706", 2, ("harassment_or_abuse", "safety_or_fraud_risk"), "覆盖具体伤害威胁和人肉曝光。"),
        _judgment("1b44f5da1082d2e258a9b675", 2, ("harassment_or_abuse", "review_suppression"), "覆盖针对消费者评价的威胁和恐吓。"),
    ],
    "harassment_threat": [
        _judgment("707d8b182fcab0cc98e0d706", 3, ("harassment_or_abuse", "safety_or_fraud_risk"), "直接覆盖使人担忧身心安全的具体伤害威胁。", primary=True),
        _judgment("1b44f5da1082d2e258a9b675", 3, ("harassment_or_abuse", "review_suppression"), "直接覆盖回应消费者评价时使用人身威胁或恐吓。", primary=True),
        _judgment("a120af91026adec4e2a4e419", 2, ("harassment_or_abuse",), "补充一般骚扰行为规范。"),
    ],
}


TRUE_NORMAL_HARD_NEGATIVE = [
    ("包装卡明确写着无需五星，也没有返现活动，可以按真实体验评价。", 5),
    ("客服主动说明不会要求删除差评，任何评分都不影响正常售后。", 4),
    ("订单截图中的电话和地址都已遮挡，公开回复没有泄露个人信息。", 4),
    ("查过防伪码确认不是假货，商品使用正常，只是外盒有点旧。", 4),
    ("看到别人说退款慢，不过我这单当天就原路退回，记录也完整。", 5),
    ("店铺提醒不要刷单，也不要复制他人的评价，应该描述真实体验。", 5),
    ("页面没有屏蔽评价，低分和高分都能正常查看和排序。", 4),
    ("客服没有辱骂或威胁，只是礼貌询问能否补充故障照片。", 4),
    ("插头没有发热、冒烟或异味，连续使用几小时依然正常。", 5),
    ("这次没有赠品换好评，优惠是在下单前公开领取的。", 4),
    ("我没有被要求改成五星，商家只请我在解决后更新真实进展。", 4),
    ("评价暂时没显示是网络延迟，刷新后高低分内容都恢复了。", 3),
    ("个人资料由我主动隐藏，商家回复中只引用了商品编号。", 4),
    ("虽然提到退货，但流程已经顺利完成，我只是记录处理速度。", 4),
    ("评论里说的危险是形容颜色太亮，商品本身没有安全问题。", 4),
]


BOUNDARY_ALTERNATIVES = {
    1: ["rating_manipulation", "normal_review"],
    2: ["fake_review"],
    3: ["review_suppression", "after_sales_risk"],
    4: ["privacy_risk", "normal_review"],
    5: ["safety_or_fraud_risk", "normal_review"],
    6: ["harassment_or_abuse", "normal_review"],
    7: ["after_sales_risk", "normal_review"],
    8: ["fake_review", "normal_review"],
    9: ["rating_manipulation", "normal_review"],
    10: ["review_suppression", "normal_review"],
}


V2_SLICES = {
    "multi_risk_precedence": MULTI_RISK[:30],
    "implicit_colloquial": IMPLICIT[:25],
    "risk_distractor": HARD_NEGATIVE,
    "normal_hard_negative": TRUE_NORMAL_HARD_NEGATIVE,
    "normal_easy": NORMAL[:10],
    "long_noisy": LONG_NOISY,
    "boundary_ambiguous": BOUNDARY,
}


def build_cases(chunks_path: Path = DEFAULT_CHUNKS) -> list[dict[str, Any]]:
    chunks = load_policy_chunks(chunks_path)
    chunk_by_id = {chunk.chunkId: chunk for chunk in chunks}
    cases: list[dict[str, Any]] = []
    sequence = 0
    for slice_name, specs in V2_SLICES.items():
        for slice_index, raw in enumerate(specs, start=1):
            sequence += 1
            if slice_name == "normal_hard_negative":
                text, rating = raw
                primary, secondary, profile = "normal_review", (), ""
            else:
                text, primary, secondary, profile, rating = raw
            profile = refined_profile(text, primary, profile)
            risk_types = [primary, *secondary]
            judgments = build_judgments(primary, secondary, profile, chunk_by_id) if primary != "normal_review" else []
            primary_ids = sorted(row["chunkId"] for row in judgments if row["primaryPolicy"])
            boundary = slice_name == "boundary_ambiguous"
            acceptable = BOUNDARY_ALTERNATIVES[slice_index] if boundary else [primary]
            cases.append(
                {
                    "caseId": f"cn2-{sequence:03d}",
                    "datasetVersion": DATASET_VERSION,
                    "language": "zh",
                    "slice": slice_name,
                    "sliceIndex": slice_index,
                    "reviewText": text,
                    "rating": rating,
                    "ratingSource": "USER_PROVIDED" if rating is not None else "UNKNOWN",
                    "primaryRiskType": primary,
                    "secondaryRiskTypes": list(secondary),
                    "riskTypes": risk_types,
                    "acceptablePrimaryRiskTypes": acceptable,
                    "annotationConfidence": "low" if boundary and len(acceptable) > 1 else "medium" if boundary else "high",
                    "requiresAdjudication": boundary and len(acceptable) > 1,
                    "policyProfile": profile or None,
                    "primaryPolicyChunkIds": primary_ids,
                    "policyJudgments": judgments,
                    "qrelCompleteness": "pooled_partial" if judgments else "not_applicable",
                    "expectedRoute": "low_touch" if primary == "normal_review" else "governance_required",
                    "routeEvaluationModes": ["text_only", "rating_aware"],
                    "reflectionExpectationPolicy": {
                        "supported": "Top-3 complete citations cover every accepted risk type.",
                        "insufficient": "No evidence, retrieval failure, or incomplete citation metadata.",
                        "mismatch": "Evidence exists but does not cover all accepted risk types.",
                    } if judgments else None,
                    "annotationBasis": "依据业务主风险规则和政策条款内容修订；主体文本已被旧候选看过，本版本不作为盲测集。",
                }
            )
    return cases


def refined_profile(text: str, primary: str, original: str) -> str:
    if primary == "after_sales_risk":
        if any(term in text for term in ("售后入口", "经营主体", "直播")):
            return "after_sales_disclosure"
        if any(term in text for term in ("赔偿", "退款", "钱也没有回来")):
            return "after_sales_compensation"
        return "after_sales_records"
    if primary == "safety_or_fraud_risk":
        if "转账" in text or "支付" in text:
            return "fraud_payment"
        if any(term in text for term in ("假药", "假货", "防伪", "宣传")):
            return "fraud_deception"
        if any(term in text for term in ("平台不核验", "明知", "审核义务")):
            return "safety_platform"
        return "safety_product"
    if primary == "privacy_risk":
        return "privacy_disclosure"
    return original


def build_judgments(
    primary: str,
    secondary: tuple[str, ...],
    profile: str,
    chunk_by_id: dict[str, Any],
) -> list[dict[str, Any]]:
    if profile not in POLICY_PROFILES_V2:
        raise ValueError(f"UNKNOWN_V2_PROFILE:{profile}")
    merged: dict[str, dict[str, Any]] = {}
    for row in POLICY_PROFILES_V2[profile]:
        merged[row["chunkId"]] = enrich_judgment(row, chunk_by_id)
    for risk in secondary:
        secondary_profile = default_profile(risk)
        for row in POLICY_PROFILES_V2[secondary_profile]:
            candidate = dict(row)
            candidate["semanticRelevance"] = min(2, int(row["semanticRelevance"]))
            candidate["primaryPolicy"] = False
            candidate["judgmentRationale"] = "次风险支持依据：" + row["judgmentRationale"]
            current = merged.get(candidate["chunkId"])
            if current is None:
                merged[candidate["chunkId"]] = enrich_judgment(candidate, chunk_by_id)
            else:
                current["supports"] = sorted(set(current["supports"]) | set(candidate["supports"]))
    return sorted(merged.values(), key=lambda item: (-item["semanticRelevance"], not item["primaryPolicy"], item["chunkId"]))


def enrich_judgment(row: dict[str, Any], chunk_by_id: dict[str, Any]) -> dict[str, Any]:
    chunk = chunk_by_id.get(row["chunkId"])
    if chunk is None:
        raise ValueError(f"V2_QREL_CHUNK_MISSING:{row['chunkId']}")
    source_level = "A" if chunk.sourceType in {"law", "regulation"} else "B"
    return {
        **row,
        "supports": sorted(set(row["supports"])),
        "sourceName": chunk.sourceName,
        "sourceType": chunk.sourceType,
        "sourceLevel": source_level,
        "clauseId": chunk.clauseId,
        "applicability": "indexed_policy_reference",
    }


def default_profile(risk: str) -> str:
    return {
        "fake_review": "fake_fabricated",
        "rating_manipulation": "rating_incentive",
        "review_suppression": "suppression_delete",
        "privacy_risk": "privacy_disclosure",
        "after_sales_risk": "after_sales_records",
        "safety_or_fraud_risk": "safety_product",
        "harassment_or_abuse": "harassment_general",
    }[risk]


def build_reflection_scenarios(chunks_path: Path = DEFAULT_CHUNKS) -> list[dict[str, Any]]:
    chunk_ids = {chunk.chunkId for chunk in load_policy_chunks(chunks_path)}
    supported = {
        "fake_review": "9c3dc9939e5eb8879caf3c5c",
        "rating_manipulation": "d75980ec05a8bcb347f5bf52",
        "review_suppression": "2bee6c98575e591210bf2067",
        "privacy_risk": "f7c63a5ca6444c3d8bf2766b",
        "after_sales_risk": "31b38d83c374476950d9bf66",
        "safety_or_fraud_risk": "eeecfa148cfe1159d4a3498f",
        "harassment_or_abuse": "a120af91026adec4e2a4e419",
    }
    mismatch = {
        "fake_review": supported["privacy_risk"],
        "rating_manipulation": supported["after_sales_risk"],
        "review_suppression": supported["safety_or_fraud_risk"],
        "privacy_risk": supported["rating_manipulation"],
        "after_sales_risk": supported["harassment_or_abuse"],
        "safety_or_fraud_risk": supported["fake_review"],
        "harassment_or_abuse": supported["after_sales_risk"],
    }
    if not set(supported.values()).union(mismatch.values()).issubset(chunk_ids):
        raise ValueError("REFLECTION_SCENARIO_CHUNK_MISSING")
    rows = []
    sequence = 0
    for risk, chunk_id in supported.items():
        risk_level = "medium" if risk == "after_sales_risk" else "high"
        for mode, evidence_ids, expected, mutation in (
            ("supported", [chunk_id], "supported", None),
            ("empty", [], "insufficient", None),
            ("mismatch", [mismatch[risk]], "mismatch", None),
            ("citation_incomplete", [chunk_id], "insufficient", "remove_sourceUrl"),
        ):
            sequence += 1
            rows.append(
                {
                    "scenarioId": f"reflection-v2-{sequence:03d}",
                    "riskTypes": [risk],
                    "riskLevel": risk_level,
                    "confidence": 0.9,
                    "evidenceMode": mode,
                    "evidenceChunkIds": evidence_ids,
                    "evidenceMutation": mutation,
                    "expectedEvidenceStatus": expected,
                    "expectedRequiresHumanReview": expected != "supported",
                }
            )
    return rows


def validate(cases: list[dict[str, Any]], reflection: list[dict[str, Any]], chunks_path: Path = DEFAULT_CHUNKS) -> dict[str, Any]:
    if len(cases) != 120:
        raise ValueError(f"V2_CASE_COUNT_MISMATCH:{len(cases)}")
    if len(reflection) != 28:
        raise ValueError(f"V2_REFLECTION_COUNT_MISMATCH:{len(reflection)}")
    texts = [normalize_text(case["reviewText"]) for case in cases]
    if len(texts) != len(set(texts)):
        raise ValueError("V2_DUPLICATE_TEXT")
    if any(not re.search(r"[\u4e00-\u9fff]", case["reviewText"]) or re.search(r"[A-Za-z]", case["reviewText"]) for case in cases):
        raise ValueError("V2_NON_CHINESE_TEXT")
    true_negatives = [case for case in cases if case["slice"] == "normal_hard_negative"]
    if len(true_negatives) != 15 or any(case["primaryRiskType"] != "normal_review" for case in true_negatives):
        raise ValueError("V2_TRUE_NEGATIVE_CONTRACT_INVALID")
    rankable = [case for case in cases if case["policyJudgments"]]
    if len(rankable) != 95:
        raise ValueError(f"V2_RANKING_COUNT_MISMATCH:{len(rankable)}")
    for case in rankable:
        judgments = case["policyJudgments"]
        if not case["primaryPolicyChunkIds"]:
            raise ValueError(f"V2_PRIMARY_POLICY_MISSING:{case['caseId']}")
        if any(not row["judgmentRationale"] or row["semanticRelevance"] not in {1, 2, 3} for row in judgments):
            raise ValueError(f"V2_JUDGMENT_INVALID:{case['caseId']}")
        if any(row["primaryPolicy"] and case["primaryRiskType"] not in row["supports"] for row in judgments):
            raise ValueError(f"V2_PRIMARY_SUPPORT_INVALID:{case['caseId']}")
    expected_statuses = Counter(row["expectedEvidenceStatus"] for row in reflection)
    if expected_statuses != Counter({"insufficient": 14, "supported": 7, "mismatch": 7}):
        raise ValueError(f"V2_REFLECTION_STATUS_MISMATCH:{dict(expected_statuses)}")
    chunks = load_policy_chunks(chunks_path)
    referenced = {row["chunkId"] for case in rankable for row in case["policyJudgments"]}
    v1_texts = load_texts(V1_DATASET)
    return {
        "caseCount": len(cases),
        "rankingCaseCount": len(rankable),
        "normalCaseCount": len(cases) - len(rankable),
        "trueNormalHardNegativeCount": len(true_negatives),
        "sliceCounts": dict(Counter(case["slice"] for case in cases)),
        "primaryRiskCounts": dict(Counter(case["primaryRiskType"] for case in cases)),
        "annotationConfidenceCounts": dict(Counter(case["annotationConfidence"] for case in cases)),
        "reflectionScenarioCount": len(reflection),
        "reflectionStatusCounts": dict(expected_statuses),
        "uniquePolicyChunkCount": len(referenced),
        "judgedCorpusCoverage": round(len(referenced) / len(chunks), 4),
        "v1ExactTextReuseCount": len(set(texts).intersection(v1_texts)),
        "allChinese": True,
        "contentRootHash": content_root_hash(chunks),
    }


def build_manifest(dataset_path: Path, reflection_path: Path, validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "step23.3c-cn-challenge-manifest-v2",
        "datasetVersion": DATASET_VERSION,
        "status": "FROZEN_DIAGNOSTIC",
        "promotionEligible": False,
        "promotionIneligibleReasons": [
            "The set reuses candidate-exposed v1 texts.",
            "Policy judgments require independent human adjudication.",
            "Qrels are pooled partial judgments; unjudged chunks are not irrelevant.",
        ],
        "dataset": {"path": dataset_path.name, "sha256": sha256_file(dataset_path)},
        "reflectionScenarios": {"path": reflection_path.name, "sha256": sha256_file(reflection_path)},
        "language": "zh",
        "policyScope": {
            "jurisdiction": "unspecified",
            "sourceRole": "indexed public policy reference; not a legal applicability determination",
            "precedence": [
                "direct primary-risk clause",
                "direct secondary-risk clause",
                "general supporting context",
            ],
        },
        "qualityRepairs": [
            "Preserved v1 unchanged and versioned the repaired contract.",
            "Separated semantic relevance from source authority and applicability.",
            "Added per-judgment rationale and explicit alternative primary policies.",
            "Removed the incomplete FTC 465.7 lead-in chunk from qrels.",
            "Added 15 genuine normal hard negatives.",
            "Renamed risk-bearing lexical distractors to risk_distractor.",
            "Added ambiguity confidence and acceptable primary labels.",
            "Separated text-only and rating-aware route evaluation modes.",
            "Added deterministic Reflection three-state and citation-failure scenarios.",
        ],
        "evaluationRules": {
            "componentRanking": "May use annotated riskTypes, but must be reported as conditional retrieval.",
            "endToEnd": "Must use predicted riskTypes and report Router misses separately.",
            "unjudgedChunks": "Must be reported as unjudged, never silently converted to relevance zero.",
            "decision": "Decision accuracy is diagnostic; high-risk human-review invariance must not inflate quality claims.",
            "route": "Report text_only and rating_aware results separately.",
        },
        "validation": validation,
        "humanAdjudication": {
            "status": "PENDING",
            "requiredBeforePromotionUse": True,
            "requiredChecks": [
                "primary risk precedence",
                "alternative acceptable labels",
                "policy relevance and applicability",
                "pooled unjudged policy chunks",
            ],
        },
    }


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8", newline="\n")


def load_texts(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        normalize_text(json.loads(line).get("reviewText", ""))
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the quality-repaired Chinese Step 23.3C v2 diagnostic set.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reflection-output", type=Path, default=DEFAULT_REFLECTION_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    args = parser.parse_args()

    chunks_path = args.chunks.resolve()
    cases = build_cases(chunks_path)
    reflection = build_reflection_scenarios(chunks_path)
    validation = validate(cases, reflection, chunks_path)
    output = args.output.resolve()
    reflection_output = args.reflection_output.resolve()
    write_jsonl(cases, output)
    write_jsonl(reflection, reflection_output)
    manifest = build_manifest(output, reflection_output, validation)
    args.manifest.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.manifest.resolve().write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"datasetSha256": manifest["dataset"]["sha256"], "reflectionSha256": manifest["reflectionScenarios"]["sha256"], **validation}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
