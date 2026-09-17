from __future__ import annotations

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

from app.contracts.review_semantics import risk_type_severity
from app.policy_rag.index_store import load_policy_chunks
from app.rag_quality.audit import audit_legacy_challenge_qrels
from app.rag_quality.contract import metric_contract
from app.rag_quality.models import QualityQrel, RagQualityCase


LEGACY_DATASET = ROOT / "data" / "benchmarks" / "step233c_cn_challenge_v2.jsonl"
LEGACY_MANIFEST = ROOT / "data" / "benchmarks" / "step233c_cn_challenge_v2.manifest.json"
CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
FROZEN_WORKFLOW = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
OUTPUT_DIR = ROOT / "data" / "benchmarks" / "rag_quality_v2"
ARTIFACT_DIR = ROOT / "artifacts" / "step242a"
DATASET_VERSION = "rag-quality-v2-candidate-1"
FROZEN_WORKFLOW_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"


DEV_QUOTAS = {
    "multi_risk_precedence": 20,
    "implicit_colloquial": 15,
    "risk_distractor": 15,
    "normal_hard_negative": 10,
    "normal_easy": 5,
    "long_noisy": 8,
    "boundary_ambiguous": 7,
}

SMOKE_QUOTAS = {
    "multi_risk_precedence": 4,
    "implicit_colloquial": 4,
    "risk_distractor": 4,
    "normal_hard_negative": 4,
    "normal_easy": 2,
    "long_noisy": 3,
    "boundary_ambiguous": 3,
}


HOLDOUT_DRAFTS: list[dict[str, Any]] = [
    {"profile": "fake_fabricated", "style": "implicit_paraphrase", "risks": ["fake_review", "rating_manipulation"], "text": text}
    for text in [
        "有人专门收空包裹单号，没见过商品也能照统一话术发布满分体验。",
        "店里说不用购买，只要换几个账号写使用感受，就按条结算报酬。",
        "评论区那些买家秀其实是员工拿同一批图片轮流上传的。",
        "群管理员发来商品文案，让从未下单的人伪装成老顾客评价。",
        "商家批量提供账号和模板，要求制造看起来真实的成交反馈。",
    ]
] + [
    {"profile": "rating_incentive", "style": "implicit_paraphrase", "risks": ["rating_manipulation", "fake_review"], "text": text}
    for text in [
        "包裹卡片写着只有评价打满分并上传截图，才返还二十元。",
        "客服表示评价内容可以自拟，但星级低于最高档就不给赠品。",
        "订单完成后收到私信，要求先把分数改高再处理补偿。",
        "商家把优惠券和指定好评绑定，不按要求评价就无法领取。",
        "参加试用的条件是公开给出最高评分，并把页面截图发给运营。",
    ]
] + [
    {"profile": "suppression_delete", "style": "near_neighbor_clause", "risks": ["review_suppression"], "text": text}
    for text in [
        "商家答应退款，但前提是先撤下已经发布的质量差评。",
        "平台只展示好评，消费者提交的负面体验一直被隐藏。",
        "客服反复要求删除评论，否则拒绝继续处理退换货。",
        "卖家以停止保修为条件，逼迫用户把低分评价改成好评。",
        "用户的批评内容没有违规，却被商家操作成其他人不可见。",
    ]
] + [
    {"profile": "privacy_disclosure", "style": "long_noisy", "risks": ["privacy_risk"], "text": text}
    for text in [
        "争执后商家在评论回复里公开了我的手机号和完整收货地址。",
        "客服把订单截图发到群里，其中姓名、电话和门牌号都没有遮挡。",
        "店铺为了反驳差评，直接贴出了消费者的身份证号码片段。",
        "评价页面出现了我的私人聊天记录，还带着可识别的联系方式。",
        "商家号召别人联系投诉者，并公布了对方的家庭住址信息。",
    ]
] + [
    {"profile": "safety_product", "style": "vague_risk_description", "risks": ["safety_or_fraud_risk", "after_sales_risk"], "text": text}
    for text in [
        "充电器使用几分钟就冒烟，商家仍称绝对安全并拒绝登记问题。",
        "收到的所谓正品没有防伪信息，通电后外壳还出现明显漏电。",
        "儿童用品有尖锐断口，页面却把相关安全警告全部省略了。",
        "食品已经过期，店铺改贴日期后继续销售并拒绝退款。",
        "燃气设备发生泄漏，卖家要求不要声张并让用户自行维修。",
    ]
] + [
    {"profile": "after_sales_records", "style": "table_or_record_lookup", "risks": ["after_sales_risk"], "text": text}
    for text in [
        "售后记录显示已经签收退货，但商家仍说仓库从未收到。",
        "维修单连续关闭三次，没有给出检测结果也没有返还商品。",
        "订单明细承诺七天退换，客服却拒绝登记符合条件的申请。",
        "物流证明破损发生在运输中，平台仍要求消费者自行承担全部损失。",
        "退款进度表长期停在审核中，商家无法提供任何处理凭证。",
    ]
] + [
    {"profile": "harassment_general", "style": "implicit_paraphrase", "risks": ["harassment_or_abuse"], "text": text}
    for text in [
        "发布真实体验后，店铺连续用侮辱性称呼私信攻击我。",
        "客服因为低分评价反复来电辱骂，并煽动他人一起骚扰。",
        "商家在公开回复中进行人身攻击，却没有回应商品问题。",
        "我拒绝修改评论后，对方每天发送带有威胁意味的信息。",
        "运营人员组织多个账号围攻评价者，内容主要是贬损和羞辱。",
    ]
] + [
    {"profile": "", "style": "no_answer_hard_negative", "risks": [], "text": text}
    for text in [
        "杯子的颜色比网页照片稍浅，但使用正常，我只是记录个人偏好。",
        "配送比预计晚了一天，商品本身完好，客服也已经解释原因。",
        "鞋码对我来说偏大，已经按照正常流程申请换货。",
        "这款茶味道比较淡，家人喜欢，我个人更偏好浓一点的。",
        "包装设计很简洁，安装说明如果再详细些会更方便。",
    ]
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    legacy_cases = load_jsonl(LEGACY_DATASET)
    legacy_manifest = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8-sig"))
    chunks = load_policy_chunks(CHUNKS)
    frozen_sha = sha256_file(FROZEN_WORKFLOW)
    if frozen_sha != FROZEN_WORKFLOW_SHA:
        raise SystemExit(f"STEP242A_FROZEN_WORKFLOW_SHA_MISMATCH actual={frozen_sha}")

    audit = audit_legacy_challenge_qrels(legacy_cases, chunks, legacy_manifest)
    dev = build_dev_cases(legacy_cases)
    holdout = build_holdout_candidates(legacy_cases)
    cases = [*dev, *holdout]
    validation = validate_cases(cases, legacy_cases, chunks)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    contract_path = OUTPUT_DIR / "metric_contract_v1.json"
    dataset_path = OUTPUT_DIR / "dataset_candidate.jsonl"
    dev_path = OUTPUT_DIR / "dev_candidate.jsonl"
    holdout_path = OUTPUT_DIR / "holdout_annotation_candidate.jsonl"
    smoke_path = OUTPUT_DIR / "smoke_candidate.jsonl"
    qrels_path = OUTPUT_DIR / "qrels_candidate.tsv"
    queue_path = OUTPUT_DIR / "human_annotation_queue.jsonl"
    audit_path = ARTIFACT_DIR / "legacy_challenge_qrels_audit.json"
    manifest_path = OUTPUT_DIR / "manifest.json"

    write_json(contract_path, metric_contract())
    write_jsonl(dataset_path, [item.model_dump(mode="json") for item in cases])
    write_jsonl(dev_path, [item.model_dump(mode="json") for item in dev])
    write_jsonl(holdout_path, [item.model_dump(mode="json") for item in holdout])
    write_jsonl(smoke_path, [item.model_dump(mode="json") for item in dev if item.smoke])
    write_qrels(qrels_path, cases)
    write_jsonl(queue_path, [annotation_row(item) for item in cases])
    write_json(audit_path, audit)

    manifest = {
        "schemaVersion": "rag-quality-dataset-manifest-v2",
        "datasetVersion": DATASET_VERSION,
        "status": "ANNOTATION_PENDING",
        "promotionEligible": False,
        "language": "zh",
        "frozenWorkflowGold": {
            "path": str(FROZEN_WORKFLOW.relative_to(ROOT)).replace("\\", "/"),
            "sha256": frozen_sha,
            "unchanged": True,
        },
        "corpus": {
            "path": str(CHUNKS.relative_to(ROOT)).replace("\\", "/"),
            "chunkCount": len(chunks),
            "contentRootHash": content_root_hash(chunks),
        },
        "files": {
            name: {"path": path.name, "sha256": sha256_file(path)}
            for name, path in {
                "metricContract": contract_path,
                "dataset": dataset_path,
                "dev": dev_path,
                "holdout": holdout_path,
                "smoke": smoke_path,
                "qrelsCandidate": qrels_path,
                "humanAnnotationQueue": queue_path,
            }.items()
        },
        "validation": validation,
        "annotation": {
            "status": "PENDING",
            "humanVerifiedCaseCount": 0,
            "pendingCaseCount": len(cases),
            "requiredBeforePromotion": True,
            "holdoutExecutionAllowed": False,
            "rules": [
                "Synthetic or Codex-authored drafts are never gold without human approval.",
                "High-risk and no-answer cases require a second independent review pass.",
                "Holdout must not be executed before annotation freeze.",
                "Any qrel repair creates a new dataset version.",
            ],
        },
        "promotionBlockers": [
            "HUMAN_ADJUDICATION_PENDING",
            "HOLDOUT_NOT_FROZEN",
            "DEV_QRELS_INHERIT_PARTIAL_DIAGNOSTIC_POOL",
            "QUALITY_THRESHOLDS_PENDING_TRUSTWORTHY_BASELINE",
        ],
        "legacyAudit": {
            "path": str(audit_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(audit_path),
            "status": audit["status"],
        },
    }
    write_json(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), **validation, "promotionEligible": False}, ensure_ascii=False, indent=2))
    return 0


def build_dev_cases(legacy_cases: list[dict[str, Any]]) -> list[RagQualityCase]:
    selected: list[dict[str, Any]] = []
    for slice_name, quota in DEV_QUOTAS.items():
        rows = [item for item in legacy_cases if item.get("slice") == slice_name]
        if len(rows) < quota:
            raise ValueError(f"STEP242A_DEV_SLICE_SHORTAGE slice={slice_name}")
        selected.extend(rows[:quota])
    smoke_ids: set[str] = set()
    for slice_name, quota in SMOKE_QUOTAS.items():
        rows = [item for item in selected if item.get("slice") == slice_name]
        smoke_ids.update(str(item["caseId"]) for item in rows[:quota])

    output: list[RagQualityCase] = []
    for index, legacy in enumerate(selected, start=1):
        risks = [str(item) for item in legacy.get("riskTypes", []) if item != "normal_review"]
        no_answer = not bool(legacy.get("policyJudgments"))
        output.append(
            RagQualityCase(
                datasetVersion=DATASET_VERSION,
                caseId=f"rqv2-dev-{index:03d}",
                split="dev",
                smoke=str(legacy["caseId"]) in smoke_ids,
                reviewText=str(legacy["reviewText"]),
                queryStyle=str(legacy["slice"]),
                riskTypes=risks,
                riskLevel=risk_level(risks),
                noAnswer=no_answer,
                sourceLanguage=source_language(legacy.get("policyJudgments", [])),
                documentFormat="html" if not no_answer else "not_applicable",
                qrels=convert_judgments(legacy.get("policyJudgments", [])),
                qrelCompleteness="pooled_partial",
                annotationStatus="pending_human_review",
                annotationSource="step23.3c_diagnostic_inheritance",
                candidateExposure=True,
                requiresAdjudication=True,
                metadata={
                    "originalCaseId": legacy["caseId"],
                    "policyProfile": legacy.get("policyProfile", ""),
                    "legacyAnnotationConfidence": legacy.get("annotationConfidence", "unknown"),
                },
            )
        )
    return output


def build_holdout_candidates(legacy_cases: list[dict[str, Any]]) -> list[RagQualityCase]:
    representatives = {
        profile: next(
            item for item in legacy_cases
            if item.get("policyProfile") == profile and item.get("policyJudgments")
        )
        for profile in {str(item["profile"]) for item in HOLDOUT_DRAFTS if item["profile"]}
    }
    output: list[RagQualityCase] = []
    for index, draft in enumerate(HOLDOUT_DRAFTS, start=1):
        profile = str(draft["profile"])
        judgments = representatives[profile].get("policyJudgments", []) if profile else []
        risks = list(draft["risks"])
        output.append(
            RagQualityCase(
                datasetVersion=DATASET_VERSION,
                caseId=f"rqv2-holdout-{index:03d}",
                split="holdout",
                reviewText=str(draft["text"]),
                queryStyle=str(draft["style"]),
                riskTypes=risks,
                riskLevel=risk_level(risks),
                noAnswer=not risks,
                sourceLanguage=source_language(judgments),
                documentFormat="html" if risks else "not_applicable",
                qrels=convert_judgments(judgments),
                qrelCompleteness="draft_pool",
                annotationStatus="pending_human_review",
                annotationSource="codex_draft_pending_human_review",
                candidateExposure=False,
                requiresAdjudication=True,
                metadata={"policyProfile": profile, "holdoutExecuted": False},
            )
        )
    return output


def convert_judgments(rows: list[dict[str, Any]]) -> list[QualityQrel]:
    return [
        QualityQrel(
            chunkId=str(row["chunkId"]),
            relevance=int(row["semanticRelevance"]),
            supports=[str(item) for item in row.get("supports", [])],
            sourceName=str(row.get("sourceName", "")),
            sourceType=str(row.get("sourceType", "")),
            sourceLevel=str(row.get("sourceLevel", "")),
            clauseId=str(row.get("clauseId", "")),
            rationale=str(row.get("judgmentRationale", "")),
        )
        for row in rows
    ]


def validate_cases(
    cases: list[RagQualityCase],
    legacy_cases: list[dict[str, Any]],
    chunks: list[Any],
) -> dict[str, Any]:
    dev = [item for item in cases if item.split == "dev"]
    holdout = [item for item in cases if item.split == "holdout"]
    smoke = [item for item in dev if item.smoke]
    legacy_texts = {str(item.get("reviewText", "")) for item in legacy_cases}
    holdout_reuse = sorted(item.caseId for item in holdout if item.reviewText in legacy_texts)
    case_ids = [item.caseId for item in cases]
    texts = [item.reviewText for item in cases]
    known_chunks = {item.chunkId for item in chunks}
    missing_refs = sorted(
        {qrel.chunkId for case in cases for qrel in case.qrels if qrel.chunkId not in known_chunks}
    )
    checks = {
        "caseCount": len(cases) == 120,
        "devCount": len(dev) == 80,
        "holdoutCount": len(holdout) == 40,
        "smokeCount": len(smoke) == 24,
        "allQueriesChinese": all(re.search(r"[\u4e00-\u9fff]", item.reviewText) for item in cases),
        "caseIdsUnique": len(case_ids) == len(set(case_ids)),
        "reviewTextsUnique": len(texts) == len(set(texts)),
        "holdoutDoesNotReuseLegacyText": not holdout_reuse,
        "allAnnotationsPending": all(item.annotationStatus == "pending_human_review" for item in cases),
        "holdoutNotCandidateExposed": all(not item.candidateExposure for item in holdout),
        "allQrelChunksExist": not missing_refs,
    }
    if not all(checks.values()):
        raise ValueError(f"STEP242A_DATASET_VALIDATION_FAILED checks={checks} missing={missing_refs} reuse={holdout_reuse}")
    return {
        "caseCount": len(cases),
        "devCount": len(dev),
        "holdoutCount": len(holdout),
        "smokeCount": len(smoke),
        "riskCaseCount": sum(bool(item.riskTypes) for item in cases),
        "noAnswerCaseCount": sum(item.noAnswer for item in cases),
        "queryStyleCounts": dict(sorted(Counter(item.queryStyle for item in cases).items())),
        "riskTypeCounts": dict(sorted(Counter(risk for item in cases for risk in item.riskTypes).items())),
        "checks": checks,
    }


def annotation_row(case: RagQualityCase) -> dict[str, Any]:
    payload = case.model_dump(mode="json")
    return {
        "caseId": case.caseId,
        "split": case.split,
        "reviewText": case.reviewText,
        "proposedRiskTypes": case.riskTypes,
        "proposedNoAnswer": case.noAnswer,
        "proposedQrels": payload["qrels"],
        "humanReview": {
            "status": "PENDING",
            "approvedRiskTypes": None,
            "approvedNoAnswer": None,
            "approvedQrels": None,
            "reviewer": "",
            "reviewedAt": "",
            "remark": "",
        },
        "secondReview": {
            "required": case.riskLevel == "high" or case.noAnswer,
            "status": "PENDING" if case.riskLevel == "high" or case.noAnswer else "NOT_REQUIRED",
            "reviewer": "",
            "reviewedAt": "",
            "remark": "",
        },
    }


def source_language(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "not_applicable"
    languages = {
        "zh" if str(row.get("sourceName", "")).startswith(("中华", "网络交易")) else "en"
        for row in rows
    }
    return next(iter(languages)) if len(languages) == 1 else "mixed"


def risk_level(risks: list[str]) -> str:
    if not risks:
        return "normal"
    levels = {risk_type_severity(item) for item in risks}
    if "高" in levels:
        return "high"
    if "中" in levels:
        return "medium"
    return "low"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_qrels(path: Path, cases: list[RagQualityCase]) -> None:
    lines = [
        f"{case.caseId}\t0\t{qrel.chunkId}\t{qrel.relevance}\n"
        for case in cases
        for qrel in case.qrels
    ]
    path.write_text("".join(lines), encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def content_root_hash(chunks: list[Any]) -> str:
    return hashlib.sha256("|".join(item.contentHash for item in chunks).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
