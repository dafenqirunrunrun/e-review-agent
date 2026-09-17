from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_step242g_after_sales_semantic_dev import load_cases, write_json


STEP242H_RESULT = ROOT / "artifacts" / "step242h_adaptive_evidence_budget" / "dev_ab_repaired_index_result.json"
BINDING_DATASET = (
    ROOT / "artifacts" / "step242h_adaptive_evidence_budget" / "bound_repaired_candidate" / "dev_bound_candidate_v2.jsonl"
)
CHUNKS = ROOT / "data" / "policy_rag_real" / "index_step242h_candidate" / "policy_chunks.jsonl"
OUTPUT = ROOT / "artifacts" / "step242i_business_evidence_sufficiency" / "dev_business_evidence_audit.json"
VARIANT = "fixed8_coverage_aware"
MAX_FINAL_EVIDENCE = 3


@dataclass(frozen=True)
class ClauseGroup:
    """One business assertion which needs one of the listed official clauses."""

    reason: str
    alternatives: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BusinessEvidenceRequirement:
    topic: str
    businessClaim: str
    clauseGroups: tuple[ClauseGroup, ...]


CONSUMER_LAW = "cn_consumer_rights_protection_law"
SEVEN_DAY_RULES = "cn_online_return_without_reason"


# This Dev-only contract intentionally names legal propositions, not chunk IDs.
# It permits semantically equivalent official clauses where a single exact-qrels
# target would be too narrow for the business decision being evaluated.
BUSINESS_REQUIREMENTS: dict[str, BusinessEvidenceRequirement] = {
    "quality_return": BusinessEvidenceRequirement(
        "quality_return",
        "质量不合格时，消费者可主张退货或修理、更换。",
        (ClauseGroup("质量不合格救济", ((CONSUMER_LAW, "二十四"), (SEVEN_DAY_RULES, "三十五"))),),
    ),
    "quality_transport_cost": BusinessEvidenceRequirement(
        "quality_transport_cost",
        "质量问题的退货争议需要适用质量不合格救济，而不能只引用无理由退货运费规则。",
        (ClauseGroup("质量不合格救济及必要费用", ((CONSUMER_LAW, "二十四"),)),),
    ),
    "post_seven_day_repair": BusinessEvidenceRequirement(
        "post_seven_day_repair",
        "超过七天后发现质量问题，经营者仍可能负有修理、更换等义务。",
        (ClauseGroup("质量不合格后的修理或更换", ((CONSUMER_LAW, "二十四"), (CONSUMER_LAW, "五十六"))),),
    ),
    "after_sales_terms": BusinessEvidenceRequirement(
        "after_sales_terms",
        "经营者使用格式条款时，应以显著方式提请消费者注意与其有重大利害关系的内容。",
        (ClauseGroup("格式条款显著提示", ((CONSUMER_LAW, "二十六"), ("cn_online_transaction_supervision", "二十一"))),),
    ),
    "online_after_sales_information": BusinessEvidenceRequirement(
        "online_after_sales_information",
        "网络销售者应提供经营地址、联系方式及售后服务等信息。",
        (ClauseGroup("网络经营信息披露", ((CONSUMER_LAW, "二十八"),)),),
    ),
    "unreasonable_delay": BusinessEvidenceRequirement(
        "unreasonable_delay",
        "经营者不得对消费者提出的退货、退款等要求故意拖延或无理拒绝。",
        (ClauseGroup("禁止故意拖延或无理拒绝", ((CONSUMER_LAW, "四十八"), (CONSUMER_LAW, "五十六"))),),
    ),
    "civil_remedy": BusinessEvidenceRequirement(
        "civil_remedy",
        "商品造成财产损害时，经营者应承担修理、退货、退款或赔偿等民事责任。",
        (ClauseGroup("财产损害民事责任", ((CONSUMER_LAW, "五十二"),)),),
    ),
    "unqualified_goods": BusinessEvidenceRequirement(
        "unqualified_goods",
        "依法认定不合格的商品，经营者应负责退货。",
        (ClauseGroup("不合格商品退货", ((CONSUMER_LAW, "五十四"), (SEVEN_DAY_RULES, "三十五"))),),
    ),
    "seven_day_duty": BusinessEvidenceRequirement(
        "seven_day_duty",
        "网络销售者应依法履行七日无理由退货义务。",
        (ClauseGroup("七日无理由退货义务", ((SEVEN_DAY_RULES, "三"), (CONSUMER_LAW, "二十五"))),),
    ),
    "statutory_exception": BusinessEvidenceRequirement(
        "statutory_exception",
        "消费者定作等法定例外不适用七日无理由退货。",
        (ClauseGroup("法定不适用范围", ((SEVEN_DAY_RULES, "六"), (CONSUMER_LAW, "二十五"))),),
    ),
    "confirmed_exception": BusinessEvidenceRequirement(
        "confirmed_exception",
        "部分商品仅在消费者购买时确认的条件下可以不适用七日无理由退货。",
        (ClauseGroup("需购买时确认的例外", ((SEVEN_DAY_RULES, "七"), (CONSUMER_LAW, "二十五"))),),
    ),
    "return_notice": BusinessEvidenceRequirement(
        "return_notice",
        "消费者可在签收次日起七日内发出无理由退货通知。",
        (ClauseGroup("退货通知期限", ((SEVEN_DAY_RULES, "十"),)),),
    ),
    "return_contact": BusinessEvidenceRequirement(
        "return_contact",
        "销售者收到退货通知后应提供真实、准确的退货地址和联系人信息。",
        (ClauseGroup("退货联系信息", ((SEVEN_DAY_RULES, "十一"), (SEVEN_DAY_RULES, "三十一"))),),
    ),
    "refund_time": BusinessEvidenceRequirement(
        "refund_time",
        "销售者收到退回商品后应在法定期限内返还已支付价款。",
        (ClauseGroup("退款时限", ((SEVEN_DAY_RULES, "十三"), (CONSUMER_LAW, "二十五"))),),
    ),
    "refund_method": BusinessEvidenceRequirement(
        "refund_method",
        "退款应比照原支付方式，未经同意不得擅自转换为店铺余额等方式。",
        (ClauseGroup("退款方式", ((SEVEN_DAY_RULES, "十四"),)),),
    ),
    "actual_paid_price": BusinessEvidenceRequirement(
        "actual_paid_price",
        "退货价款以消费者实际支出的价款为准。",
        (ClauseGroup("实际支付价款", ((SEVEN_DAY_RULES, "十七"),)),),
    ),
    "return_method_restriction": BusinessEvidenceRequirement(
        "return_method_restriction",
        "销售者可以约定退货方式，但不得限制消费者的退货方式。",
        (ClauseGroup("退货方式不得限制", ((SEVEN_DAY_RULES, "十九"),)),),
    ),
    "exception_confirmation_process": BusinessEvidenceRequirement(
        "exception_confirmation_process",
        "例外商品应明确标注；需要消费者确认的，应在销售必经流程中显著确认。",
        (ClauseGroup("例外商品确认程序", ((SEVEN_DAY_RULES, "二十"),)),),
    ),
    "expanded_exception": BusinessEvidenceRequirement(
        "expanded_exception",
        "无理由退货例外仅限法定范围或购买时确认的特定范围，不能笼统扩大。",
        (ClauseGroup("无理由退货及其例外范围", ((CONSUMER_LAW, "二十五"), (SEVEN_DAY_RULES, "三十"))),),
    ),
    "quality_cross_reference": BusinessEvidenceRequirement(
        "quality_cross_reference",
        "质量不合格争议适用质量不合格救济，不因无理由退货规则而排除。",
        (ClauseGroup("质量不合格救济", ((CONSUMER_LAW, "二十四"), (SEVEN_DAY_RULES, "三十五"))),),
    ),
}


# Each alternative contains words which must occur together in the retrieved
# child, never in a different child sharing the same clause number.
CONTENT_ANCHORS = {
    "quality_return": (("不符合质量要求", "退货"),),
    "quality_transport_cost": (("必要费用", "经营者应当承担"),),
    "post_seven_day_repair": (("七日后", "修理"), ("修理", "故意拖延", "无理拒绝")),
    "after_sales_terms": (("格式条款", "提请消费者注意"),),
    "online_after_sales_information": (("联系方式", "售后服务"),),
    "unreasonable_delay": (("故意拖延", "无理拒绝"),),
    "civil_remedy": (("财产损害", "民事责任"),),
    "unqualified_goods": (("认定为不合格", "负责退货"), ("不符合质量要求", "退货")),
    "seven_day_duty": (("依法履行七日无理由退货义务",), ("有权自收到商品之日起七日内退货",)),
    "statutory_exception": (("定作", "鲜活易腐"),),
    "confirmed_exception": (("购买时确认", "不适用无理由退货"), ("购买时确认", "可以不适用")),
    "return_notice": (("退货通知", "次日开始起算"),),
    "return_contact": (("退货地址", "退货联系人"),),
    "refund_time": (("收到退回商品之日起七日内", "价款"),),
    "refund_method": (("退款方式", "消费者明确表示同意"),),
    "actual_paid_price": (("实际支出的价款",),),
    "return_method_restriction": (("不应当限制消费者的退货方式",),),
    "exception_confirmation_process": (("显著的确认程序",),),
    "expanded_exception": (("擅自扩大不适用",), ("消费者定作", "购买时确认")),
    "quality_cross_reference": (("不符合质量要求", "退货"),),
}


def main() -> int:
    report = execute_dev_audit()
    write_json(OUTPUT, report)
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "PASS" else 1


def execute_dev_audit() -> dict[str, Any]:
    return execute_audit(
        STEP242H_RESULT,
        BINDING_DATASET,
        scope="Dev-only semantic audit of the candidate index. The runtime index, frozen exact-qrels, and Holdout remain untouched.",
        holdout_executed=False,
    )


def execute_audit(
    source_report_path: Path,
    dataset_path: Path,
    *,
    scope: str,
    holdout_executed: bool,
) -> dict[str, Any]:
    source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
    cases = load_cases(dataset_path)
    chunk_index = {
        item["chunkId"]: item
        for line in CHUNKS.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
        for item in [json.loads(line)]
    }
    final_evaluation = source_report["variants"][VARIANT]["finalBundleEvaluation"]
    case_results = {row["caseId"] for row in final_evaluation["caseResults"]}
    expected_case_ids = {case.caseId for case in cases}
    if case_results != expected_case_ids:
        raise RuntimeError("STEP242I_CASE_SET_MISMATCH")

    results_by_id = {row["caseId"]: row for row in final_evaluation["caseResults"]}
    audits = [audit_case(case, results_by_id[case.caseId], chunk_index) for case in cases]
    risk_audits = [item for item in audits if item["kind"] == "risk"]
    normal_audits = [item for item in audits if item["kind"] == "normal"]
    sufficient = [item for item in risk_audits if item["verdict"] == "sufficient"]
    partial = [item for item in risk_audits if item["verdict"] == "partial"]
    insufficient = [item for item in risk_audits if item["verdict"] == "insufficient"]
    citation_valid = all(item["citationValid"] for item in risk_audits)
    normal_abstained = all(item["verdict"] == "not_applicable" for item in normal_audits)
    bounded = all(item["selectedEvidenceCount"] <= MAX_FINAL_EVIDENCE and item.get("bundleValid", True) for item in audits)
    metrics = {
        "riskCaseCount": len(risk_audits),
        "businessSufficientCount": len(sufficient),
        "businessSufficientRate": ratio(len(sufficient), len(risk_audits)),
        "partialEvidenceCount": len(partial),
        "insufficientEvidenceCount": len(insufficient),
        "citationValidRate": ratio(sum(item["citationValid"] for item in risk_audits), len(risk_audits)),
        "normalAbstentionAccuracy": ratio(sum(item["verdict"] == "not_applicable" for item in normal_audits), len(normal_audits)),
        "maxSelectedEvidenceCount": max((item["selectedEvidenceCount"] for item in audits), default=0),
        "averageSelectedEvidenceCount": round(sum(item["selectedEvidenceCount"] for item in risk_audits) / len(risk_audits), 2),
        "strictPreferredEvidenceHitAt5": source_report["variants"][VARIANT]["evaluation"]["metrics"]["candidateEvidenceHitRateAt5"],
        "strictPreferredEvidenceHitAt3": source_report["variants"][VARIANT]["directPreferred"]["directPreferredHitRateAt3"],
    }
    checks = {
        "businessSufficientRate": metrics["businessSufficientRate"] >= 0.9,
        "citationValidRate": citation_valid,
        "normalAbstention": normal_abstained,
        "minimalEvidenceBundle": bounded,
    }
    return {
        "schemaVersion": "step242i-business-evidence-sufficiency-dev-v1",
        "gate": "PASS" if all(checks.values()) else "HOLD",
        "scope": scope,
        "sourceExperiment": {"path": relative_path(source_report_path), "variant": VARIANT},
        "evaluationContract": {
            "exactClauseMetric": "Diagnostic only; it reports whether the predeclared preferred clause was retrieved.",
            "businessSufficiencyMetric": "A final bundle is sufficient only when its valid official citations cover every legal proposition required by the current business complaint.",
            "finalEvidenceBundle": "Stop after coverage; retain at most three non-duplicate citations for a human reviewer.",
            "adjudicator": "codex_authored_clause_and_content_checks_v2",
            "limitation": "Deterministic checks of manually specified clauses and content anchors in retrieved chunks; not a live LLM judge or independent human gold.",
        },
        "gates": {"businessSufficientRate": 0.9, "citationValidRate": 1.0, "normalAbstentionAccuracy": 1.0, "maxEvidence": MAX_FINAL_EVIDENCE},
        "gateChecks": checks,
        "metrics": metrics,
        "cases": audits,
        "holdoutExecuted": holdout_executed,
    }


def audit_case(case: Any, result: dict[str, Any], chunk_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    selected = result.get("top5", [])
    evidence = [evidence_summary(hit, chunk_index) for hit in selected]
    citation_valid = all(item["citationValid"] for item in evidence) and (bool(evidence) or case.noAnswer)
    if case.noAnswer:
        return {
            "caseId": case.caseId,
            "kind": "normal",
            "reviewText": case.reviewText,
            "selectedEvidenceCount": len(evidence),
            "citationValid": citation_valid,
            "verdict": "not_applicable" if result.get("abstained") and not evidence else "insufficient",
            "reason": "普通评论不需要政策依据。" if result.get("abstained") and not evidence else "普通评论不应返回政策依据。",
            "selectedEvidence": evidence,
        }

    topic = str(case.metadata.get("topic", ""))
    requirement = requirement_for_case(topic, case.reviewText)
    if requirement is None:
        raise RuntimeError(f"STEP242I_MISSING_BUSINESS_REQUIREMENT:{topic}")
    unique = len({item["chunkId"] for item in evidence}) == len(evidence)
    bundle_valid = unique and len(evidence) <= MAX_FINAL_EVIDENCE
    keys = {
        (item["documentId"], item["clauseId"])
        for item in evidence
        if item["citationValid"] and content_supports_case(topic, case.reviewText, chunk_index[item["chunkId"]]["text"])
    }
    group_results = []
    for group in requirement.clauseGroups:
        matched = [key for key in group.alternatives if key in keys]
        group_results.append({"reason": group.reason, "matched": bool(matched), "matchedClauses": matched})
    matched_count = sum(item["matched"] for item in group_results)
    verdict = "sufficient" if citation_valid and bundle_valid and matched_count == len(group_results) else "partial" if matched_count else "insufficient"
    return {
        "caseId": case.caseId,
        "kind": "risk",
        "reviewText": case.reviewText,
        "riskTypes": case.riskTypes,
        "topic": topic,
        "businessClaim": requirement.businessClaim,
        "selectedEvidenceCount": len(evidence),
        "citationValid": citation_valid,
        "bundleValid": bundle_valid,
        "verdict": verdict,
        "reason": business_reason(verdict, group_results),
        "claimCoverage": group_results,
        "selectedEvidence": evidence,
    }


def evidence_summary(hit: dict[str, Any], chunk_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    chunk = chunk_index.get(hit.get("chunkId", ""), {})
    fields = ("sourceName", "sourceUrl", "sectionPath", "clauseId", "contentHash")
    citation_valid = bool(chunk.get("text")) and all(
        hit.get(key) and hit[key] == chunk.get(key) for key in fields
    ) and str(hit.get("sourceUrl", "")).startswith(("https://", "http://"))
    return {
        "chunkId": hit.get("chunkId", ""),
        "documentId": chunk.get("documentId", ""),
        "sourceName": hit.get("sourceName", ""),
        "sourceUrl": hit.get("sourceUrl", ""),
        "clauseId": hit.get("clauseId", ""),
        "sectionPath": hit.get("sectionPath", []),
        "contentHash": hit.get("contentHash", ""),
        "citationValid": citation_valid,
    }


def content_supports_case(topic: str, review_text: str, text: str) -> bool:
    if topic == "civil_remedy" and not any(word in review_text for word in ("财产损失", "财产损害")):
        topic = "quality_return"
    normalized = re.sub(r"\s+", "", text)
    return any(all(anchor in normalized for anchor in group) for group in CONTENT_ANCHORS[topic])


def requirement_for_case(topic: str, review_text: str) -> BusinessEvidenceRequirement | None:
    requirement = BUSINESS_REQUIREMENTS.get(topic)
    if topic != "civil_remedy" or any(word in review_text for word in ("财产损失", "财产损害")):
        return requirement
    return BusinessEvidenceRequirement(
        topic,
        "商品存在质量问题且经营者拒绝换货或退款时，需要质量不合格救济依据。",
        (ClauseGroup("质量不合格救济", ((CONSUMER_LAW, "二十四"), (SEVEN_DAY_RULES, "三十五"))),),
    )


def business_reason(verdict: str, groups: list[dict[str, Any]]) -> str:
    missing = [item["reason"] for item in groups if not item["matched"]]
    if verdict == "sufficient":
        return "已用最少的可追溯政策依据覆盖当前业务判断。"
    if verdict == "partial":
        return f"仅覆盖部分业务判断，仍缺少：{'、'.join(missing)}。"
    return f"当前候选未能支撑业务判断，缺少：{'、'.join(missing)}。"


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate": report["gate"],
        "metrics": report["metrics"],
        "gateChecks": report["gateChecks"],
        "insufficientCases": [item["caseId"] for item in report["cases"] if item["verdict"] == "insufficient"],
        "holdoutExecuted": report["holdoutExecuted"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
