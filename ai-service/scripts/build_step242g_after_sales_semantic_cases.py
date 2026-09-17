from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.chunker import PolicyStructureChunker
from app.policy_rag.parser import PolicyDocumentParser
from app.policy_rag.sources import REAL_POLICY_SOURCES


DATASET_VERSION = "rag-quality-after-sales-semantic-v2"
RAW_DIR = ROOT / "data" / "policy_rag_real" / "raw"
OUTPUT_DIR = ROOT / "data" / "benchmarks" / "rag_quality_after_sales_semantic_v2"
SOURCE_IDS = {
    "cn_consumer_rights_protection_law",
    "cn_online_return_without_reason",
}


# One dev/holdout paraphrase pair per legal topic. The target remains a canonical
# clause reference, so the source-of-truth survives an intentional chunk rebuild.
TOPICS: list[dict[str, Any]] = [
    {
        "id": "quality_return", "clause": ("cn_consumer_rights_protection_law", "二十四", ["不符合质量要求", "退货"]),
        "dev": "收到的商品质量不合格，商家拒绝给我退货。",
        "holdout": "货有明显质量问题，客服说不能退也不能换。",
    },
    {
        "id": "quality_transport_cost", "clause": ("cn_consumer_rights_protection_law", "二十四", ["运输", "必要费用"]),
        "dev": "商品破损退货，商家要我自己承担寄回去的必要运费。",
        "holdout": "质量问题换货时，卖家拒绝支付因此产生的运输费用。",
    },
    {
        "id": "post_seven_day_repair", "clause": ("cn_consumer_rights_protection_law", "二十四", ["七日后", "更换", "修理"]),
        "dev": "签收超过七天才发现故障，商家说退不了也不负责维修。",
        "holdout": "商品过了一周出现质量问题，客服拒绝履行更换或修理。",
    },
    {
        "id": "after_sales_terms", "clause": ("cn_consumer_rights_protection_law", "二十六", ["格式条款", "售后服务"]),
        "dev": "商家的购买条款把售后责任藏得很深，下单前根本看不清。",
        "holdout": "店铺用固定条款限制售后，却没有显著提醒消费者注意。",
    },
    {
        "id": "online_after_sales_information", "clause": ("cn_consumer_rights_protection_law", "二十八", ["网络", "售后服务"]),
        "dev": "网店页面没有提供售后服务和经营联系信息。",
        "holdout": "线上购买前，卖家没有清楚展示售后责任和联系方式。",
    },
    {
        "id": "unreasonable_delay", "clause": ("cn_consumer_rights_protection_law", "四十八", ["故意拖延", "退货"]),
        "dev": "我提出退款退货后，商家一直故意拖着不处理。",
        "holdout": "客服反复拖延我要求的修理和退款，没有给出处理结果。",
    },
    {
        "id": "civil_remedy", "clause": ("cn_consumer_rights_protection_law", "五十二", ["修理", "退还货款"]),
        "dev": "商品造成财产损失后，商家既不修理也不退还货款。",
        "holdout": "卖家提供的商品有问题，我要求换货或退款却被拒绝。",
    },
    {
        "id": "unqualified_goods", "clause": ("cn_consumer_rights_protection_law", "五十四", ["不合格", "退货"]),
        "dev": "商品已经被认定不合格，商家还是不同意退货。",
        "holdout": "检测不合格的商品想退回去，店铺说一律不退。",
    },
    {
        "id": "seven_day_duty", "clause": ("cn_online_return_without_reason", "三", ["七日无理由退货", "义务"]),
        "dev": "普通商品签收第三天申请七天无理由退货，商家直接拒绝。",
        "holdout": "还在七天内的普通网购商品，卖家不肯履行无理由退货。",
    },
    {
        "id": "statutory_exception", "clause": ("cn_online_return_without_reason", "六", ["定作", "不适用"]),
        "dev": "我买的是按要求定制的商品，商家说不支持七天无理由退货。",
        "holdout": "鲜活易腐商品申请无理由退货，店铺说明不适用七天规则。",
    },
    {
        "id": "confirmed_exception", "clause": ("cn_online_return_without_reason", "七", ["确认", "不适用"]),
        "dev": "购买时确认过激活试用后价值会贬损，商家拒绝无理由退货。",
        "holdout": "商品销售时已明示有瑕疵且我确认过，卖家称不适用七天退货。",
    },
    {
        "id": "return_notice", "clause": ("cn_online_return_without_reason", "十", ["七日内", "退货通知"]),
        "dev": "我在签收后第七天发出退货通知，商家说已经过期。",
        "holdout": "消费者签收商品第六天通知退货，客服仍以超期为由拒绝。",
    },
    {
        "id": "return_contact", "clause": ("cn_online_return_without_reason", "十一", ["退货地址", "联系人"]),
        "dev": "申请退货后，商家一直不提供真实退货地址和联系人。",
        "holdout": "卖家收到退货通知，却不给退货电话和有效地址。",
    },
    {
        "id": "refund_time", "clause": ("cn_online_return_without_reason", "十三", ["七日", "返还"]),
        "dev": "商家收到退回商品十天了，还没有把已支付价款退给我。",
        "holdout": "退货签收后一周过去，店铺仍未返还消费者已经支付的钱。",
    },
    {
        "id": "refund_method", "clause": ("cn_online_return_without_reason", "十四", ["退款方式", "自行指定"]),
        "dev": "商家没征得同意，就把退款强制转成店铺余额。",
        "holdout": "原本是银行卡付款，卖家却自行指定用优惠券代替退款。",
    },
    {
        "id": "actual_paid_price", "clause": ("cn_online_return_without_reason", "十七", ["实际支出的价款"]),
        "dev": "满减订单退货后，商家不愿按我实际支付的金额退款。",
        "holdout": "套装里退一件商品，店铺把应退金额算得低于消费者实际支出。",
    },
    {
        "id": "return_method_restriction", "clause": ("cn_online_return_without_reason", "十九", ["不应当限制", "退货方式"]),
        "dev": "商家规定只能用他指定的快递退货，不接受别的合理方式。",
        "holdout": "卖家以各种理由限制消费者选择退货方式。",
    },
    {
        "id": "exception_confirmation_process", "clause": ("cn_online_return_without_reason", "二十", ["显著的确认程序", "不得拒绝"]),
        "dev": "商品被标成不能退，但购买流程没有任何显著确认。",
        "holdout": "店铺声称商品不适用退货，却没有在下单流程让消费者确认。",
    },
    {
        "id": "expanded_exception", "clause": ("cn_online_return_without_reason", "三十", ["擅自扩大", "不适用"]),
        "dev": "普通商品还在七天内，店铺却用概不退换扩大不适用范围。",
        "holdout": "卖家把本可无理由退货的商品全部列为例外。",
    },
    {
        "id": "quality_cross_reference", "clause": ("cn_online_return_without_reason", "三十五", ["不符合质量要求", "第二十四条"]),
        "dev": "商品质量不达标，商家说这和退货规则没有关系。",
        "holdout": "卖家提供的商品不符合质量要求，却拒绝消费者的退货请求。",
    },
]

NORMAL_CASES = [
    ("normal_001", "dev", "包装完整，物流很快，商品用起来没有问题。"),
    ("normal_002", "dev", "这款衣服有没有蓝色，尺码应该怎么选？"),
    ("normal_003", "dev", "客服回复很耐心，整体购物体验不错。"),
    ("normal_004", "dev", "收到商品和图片一致，没有需要售后的地方。"),
    ("normal_005", "holdout", "发货及时，产品正常使用，满意。"),
    ("normal_006", "holdout", "请问什么时候补货，能不能开发票？"),
    ("normal_007", "holdout", "店家服务不错，已经推荐给朋友。"),
    ("normal_008", "holdout", "商品颜色符合预期，暂时没有遇到问题。"),
]


def main() -> int:
    clause_text = canonical_clause_text()
    rows = build_rows(clause_text)
    validation = validate_rows(rows, clause_text)
    write_outputs(rows, validation)
    print(json.dumps({"datasetVersion": DATASET_VERSION, **validation}, ensure_ascii=False, indent=2))
    return 0


def canonical_clause_text() -> dict[tuple[str, str], str]:
    parser = PolicyDocumentParser()
    combined: dict[tuple[str, str], list[str]] = {}
    for spec in REAL_POLICY_SOURCES:
        if spec.sourceId not in SOURCE_IDS:
            continue
        document = parser.parse_file(
            RAW_DIR / spec.fileName,
            source_id=spec.sourceId,
            source_url=spec.sourceUrl,
            source_name=spec.sourceName,
            source_type=spec.sourceType,
            language=spec.language,
            jurisdiction=spec.jurisdiction,
            license_class=spec.licenseClass,
        )
        for chunk in PolicyStructureChunker().chunk(document):
            if chunk.clauseId:
                combined.setdefault((chunk.documentId, chunk.clauseId), []).append(chunk.text)
    return {key: "\n".join(value) for key, value in combined.items()}


def build_rows(clause_text: dict[tuple[str, str], str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for topic in TOPICS:
        source_id, clause_id, anchors = topic["clause"]
        for split in ("dev", "holdout"):
            rows.append(
                {
                    "schemaVersion": "rag-quality-semantic-case-v1",
                    "datasetVersion": DATASET_VERSION,
                    "caseId": f"asv2-{topic['id']}-{split}",
                    "split": split,
                    "language": "zh",
                    "reviewText": topic[split],
                    "queryStyle": "business_paraphrase",
                    "riskTypes": ["after_sales_risk"],
                    "riskLevel": "medium",
                    "noAnswer": False,
                    "expectedEvidence": [
                        {
                            "documentId": source_id,
                            "clauseId": clause_id,
                            "relevance": 3,
                            "requiredAnchors": anchors,
                            "businessRationale": "Direct policy evidence sufficient to assess the described after-sales dispute.",
                        }
                    ],
                    "annotationStatus": "llm_adjudicated",
                    "annotationSource": "codex_semantic_adjudication_after_sales_v2",
                    "candidateExposure": split == "dev",
                    "requiresAdjudication": False,
                    "metadata": {
                        "topic": topic["id"],
                        "semanticLabelIsChunkIndependent": True,
                        "limitation": "Single Codex semantic adjudication for a personal demo; not human gold.",
                    },
                }
            )
    for identifier, split, text in NORMAL_CASES:
        rows.append(
            {
                "schemaVersion": "rag-quality-semantic-case-v1",
                "datasetVersion": DATASET_VERSION,
                "caseId": f"asv2-{identifier}",
                "split": split,
                "language": "zh",
                "reviewText": text,
                "queryStyle": "normal_review",
                "riskTypes": [],
                "riskLevel": "normal",
                "noAnswer": True,
                "expectedEvidence": [],
                "annotationStatus": "llm_adjudicated",
                "annotationSource": "codex_semantic_adjudication_after_sales_v2",
                "candidateExposure": split == "dev",
                "requiresAdjudication": False,
                "metadata": {
                    "semanticLabelIsChunkIndependent": True,
                    "limitation": "Workflow abstention control; it does not assert retrieval-level no-answer quality.",
                },
            }
        )
    return rows


def validate_rows(rows: list[dict[str, Any]], clause_text: dict[tuple[str, str], str]) -> dict[str, Any]:
    identifiers = [str(row["caseId"]) for row in rows]
    texts = [str(row["reviewText"]) for row in rows]
    dev = [row for row in rows if row["split"] == "dev"]
    holdout = [row for row in rows if row["split"] == "holdout"]
    topic_pairs = Counter(row["metadata"].get("topic") for row in rows if row["metadata"].get("topic"))
    anchor_failures = []
    for row in rows:
        for reference in row["expectedEvidence"]:
            key = (reference["documentId"], reference["clauseId"])
            text = normalize_for_anchor_match(clause_text.get(key, ""))
            missing = [
                anchor
                for anchor in reference["requiredAnchors"]
                if normalize_for_anchor_match(anchor) not in text
            ]
            if missing:
                anchor_failures.append({"caseId": row["caseId"], "reference": key, "missingAnchors": missing})
    checks = {
        "caseCountIs48": len(rows) == 48,
        "devCountIs24": len(dev) == 24,
        "holdoutCountIs24": len(holdout) == 24,
        "allChinese": all(any("\u4e00" <= char <= "\u9fff" for char in str(row["reviewText"])) for row in rows),
        "idsUnique": len(identifiers) == len(set(identifiers)),
        "textsUnique": len(texts) == len(set(texts)),
        "everyTopicHasDevAndHoldoutParaphrase": all(count == 2 for count in topic_pairs.values()) and len(topic_pairs) == len(TOPICS),
        "holdoutNotCandidateExposed": all(not row["candidateExposure"] for row in holdout),
        "allSemanticReferencesResolve": not anchor_failures,
        "normalCasesHaveNoEvidence": all(not row["expectedEvidence"] and not row["riskTypes"] for row in rows if row["noAnswer"]),
        "riskCasesHaveDirectEvidence": all(row["expectedEvidence"] and row["riskTypes"] == ["after_sales_risk"] for row in rows if not row["noAnswer"]),
    }
    if not all(checks.values()):
        raise ValueError(f"STEP242G_SEMANTIC_DATASET_INVALID checks={checks} anchorFailures={anchor_failures}")
    return {
        "caseCount": len(rows),
        "devCount": len(dev),
        "holdoutCount": len(holdout),
        "riskCaseCount": sum(not row["noAnswer"] for row in rows),
        "normalControlCount": sum(row["noAnswer"] for row in rows),
        "legalTopicCount": len(TOPICS),
        "topicCoverage": dict(sorted(topic_pairs.items())),
        "checks": checks,
    }


def write_outputs(rows: list[dict[str, Any]], validation: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset = OUTPUT_DIR / "semantic_cases_llm_adjudicated_v2.jsonl"
    dev = OUTPUT_DIR / "semantic_dev_llm_adjudicated_v2.jsonl"
    holdout = OUTPUT_DIR / "semantic_holdout_llm_adjudicated_v2.jsonl"
    write_jsonl(dataset, rows)
    write_jsonl(dev, [row for row in rows if row["split"] == "dev"])
    write_jsonl(holdout, [row for row in rows if row["split"] == "holdout"])
    manifest = {
        "schemaVersion": "rag-quality-after-sales-semantic-manifest-v2",
        "status": "FROZEN_SEMANTIC_LABELS_AWAITING_CHUNK_BINDING",
        "datasetVersion": DATASET_VERSION,
        "purpose": "Chunk-independent, Chinese after-sales semantic ground truth for validating a future structure-aware index rebuild.",
        "limitation": "Single Codex semantic adjudication for a personal demo; not human gold. The holdout is execution-unseen, not author-blind.",
        "files": {
            path.name: {"path": path.name, "sha256": sha256_file(path)}
            for path in (dataset, dev, holdout)
        },
        "annotation": {
            "status": "llm_adjudicated",
            "semanticLabels": "canonical_document_clause_anchor",
            "chunkIdsBound": False,
            "holdoutExecuted": False,
            "thresholdsFrozen": False,
        },
        "validation": validation,
    }
    write_json(OUTPUT_DIR / "semantic_manifest_llm_adjudicated_v2.json", manifest)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def normalize_for_anchor_match(value: str) -> str:
    """Make PDF line wraps invisible without applying semantic rewriting."""
    return "".join(char for char in value if char.isalnum() or "\u4e00" <= char <= "\u9fff")


if __name__ == "__main__":
    raise SystemExit(main())
