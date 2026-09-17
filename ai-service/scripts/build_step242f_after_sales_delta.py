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

from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.models import PolicyChunk
from app.rag_quality.models import QualityQrel, RagQualityCase


DATASET_VERSION = "rag-quality-after-sales-delta-v1"
CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
OUTPUT_DIR = ROOT / "data" / "benchmarks" / "rag_quality_after_sales_delta_v1"


# This is intentionally a corpus-bound delta set. It evaluates the two newly
# ingested after-sales regulations, not the old 71-chunk review-policy corpus.
CASE_SPECS: list[dict[str, Any]] = [
    {
        "id": "001", "split": "dev", "style": "quality_return",
        "text": "收到的商品有明显质量问题，商家拒绝退货退款。",
        "direct": [("cn_consumer_rights_protection_law", "二十四")],
        "support": [("cn_online_return_without_reason", "三十五")],
    },
    {
        "id": "002", "split": "dev", "style": "quality_return_cost",
        "text": "商品坏了要退货，商家说运费必须由我承担。",
        "direct": [("cn_consumer_rights_protection_law", "二十四")],
        "support": [("cn_online_return_without_reason", "三十五")],
    },
    {
        "id": "003", "split": "dev", "style": "quality_requirement",
        "text": "商品不符合质量要求，客服却说不能退，只能自己忍着。",
        "direct": [("cn_online_return_without_reason", "三十五")],
        "support": [("cn_consumer_rights_protection_law", "二十四")],
    },
    {
        "id": "004", "split": "dev", "style": "seven_day_return",
        "text": "刚签收三天的普通商品想七天无理由退货，商家直接拒绝。",
        "direct": [("cn_online_return_without_reason", "三")],
        "support": [("cn_online_return_without_reason", "十")],
    },
    {
        "id": "005", "split": "dev", "style": "return_exception",
        "text": "我定制的商品想按七天无理由退货，商家说不支持。",
        "direct": [("cn_online_return_without_reason", "六")],
        "support": [],
    },
    {
        "id": "006", "split": "dev", "style": "confirmed_exception",
        "text": "购买时确认过已激活试用后价值会大幅贬损，商家拒绝七天无理由退货。",
        "direct": [("cn_online_return_without_reason", "七")],
        "support": [("cn_online_return_without_reason", "二十")],
    },
    {
        "id": "007", "split": "dev", "style": "return_notice_window",
        "text": "我在签收后第七天通知退货，商家说已经超过期限。",
        "direct": [("cn_online_return_without_reason", "十")],
        "support": [("cn_online_return_without_reason", "三")],
    },
    {
        "id": "008", "split": "dev", "style": "return_address",
        "text": "申请退货后商家一直不给真实退货地址和联系人。",
        "direct": [("cn_online_return_without_reason", "十一")],
        "support": [],
    },
    {
        "id": "009", "split": "dev", "style": "refund_method",
        "text": "商家未经同意，把应退的钱强制退成店铺余额。",
        "direct": [("cn_online_return_without_reason", "十四")],
        "support": [],
    },
    {
        "id": "010", "split": "dev", "style": "refund_amount",
        "text": "退货后商家不按实际支付金额退款，说满减订单只能少退。",
        "direct": [("cn_online_return_without_reason", "十七")],
        "support": [("cn_online_return_without_reason", "十四")],
    },
    {
        "id": "011", "split": "dev", "style": "return_method_restriction",
        "text": "商家指定只能用他自己的快递退货，不接受别的合理退货方式。",
        "direct": [("cn_online_return_without_reason", "十九")],
        "support": [],
    },
    {
        "id": "012", "split": "dev", "style": "delayed_after_sales",
        "text": "商品有问题后，我多次要求修理或退款，商家一直故意拖着不处理。",
        "direct": [("cn_consumer_rights_protection_law", "四十八")],
        "support": [("cn_consumer_rights_protection_law", "二十四")],
    },
    {
        "id": "013", "split": "dev", "style": "unqualified_goods",
        "text": "商品已经被认定不合格，我要求退货，商家还是不同意。",
        "direct": [("cn_consumer_rights_protection_law", "五十四")],
        "support": [("cn_consumer_rights_protection_law", "二十四")],
    },
    {
        "id": "014", "split": "dev", "style": "normal_negative",
        "text": "包装不错，物流也很快，下次还会购买。",
        "direct": [], "support": [],
    },
    {
        "id": "015", "split": "dev", "style": "normal_product_question",
        "text": "请问这款商品有没有蓝色，尺寸怎么选择？",
        "direct": [], "support": [],
    },
    {
        "id": "016", "split": "dev", "style": "quality_repair",
        "text": "七天后发现质量故障，商家说既不能退也不肯提供更换或修理。",
        "direct": [("cn_consumer_rights_protection_law", "二十四")],
        "support": [("cn_online_return_without_reason", "三十五")],
    },
    {
        "id": "017", "split": "holdout", "style": "promotion_refund_amount",
        "text": "参加满减活动买的商品退货，商家只愿意退一部分实际付款。",
        "direct": [("cn_online_return_without_reason", "十七")],
        "support": [],
    },
    {
        "id": "018", "split": "holdout", "style": "blanket_no_return",
        "text": "普通非定制商品还在七天内，店铺写着一律概不退换。",
        "direct": [("cn_online_return_without_reason", "三")],
        "support": [("cn_online_return_without_reason", "三十")],
    },
    {
        "id": "019", "split": "holdout", "style": "exception_confirmation",
        "text": "商品被商家列为不支持退货，但购买流程里没有任何显著确认。",
        "direct": [("cn_online_return_without_reason", "二十")],
        "support": [("cn_online_return_without_reason", "七")],
    },
    {
        "id": "020", "split": "holdout", "style": "refund_to_coupon",
        "text": "退货后商家没问我就发了一张优惠券，说这就算退款。",
        "direct": [("cn_online_return_without_reason", "十四")],
        "support": [],
    },
    {
        "id": "021", "split": "holdout", "style": "quality_transport_cost",
        "text": "收到破损商品申请退货，商家要求我承担寄回去的必要运费。",
        "direct": [("cn_consumer_rights_protection_law", "二十四")],
        "support": [("cn_online_return_without_reason", "三十五")],
    },
    {
        "id": "022", "split": "holdout", "style": "contractual_after_sales_refusal",
        "text": "商品与宣传不符，我提出退货退款，商家无理拒绝并一直拖延。",
        "direct": [("cn_consumer_rights_protection_law", "四十八")],
        "support": [("cn_consumer_rights_protection_law", "五十二")],
    },
    {
        "id": "023", "split": "holdout", "style": "normal_praise",
        "text": "店家发货及时，产品使用正常，整体体验不错。",
        "direct": [], "support": [],
    },
    {
        "id": "024", "split": "holdout", "style": "quality_refund_reference",
        "text": "商品质量不达标，商家却说售后规则和退货没有关系。",
        "direct": [("cn_online_return_without_reason", "三十五")],
        "support": [("cn_consumer_rights_protection_law", "二十四")],
    },
]


def main() -> int:
    chunks = load_policy_chunks(CHUNKS)
    cases = build_cases(chunks)
    validation = validate_cases(cases, chunks)
    write_outputs(cases, chunks, validation)
    print(json.dumps({"datasetVersion": DATASET_VERSION, **validation}, ensure_ascii=False, indent=2))
    return 0


def build_cases(chunks: list[PolicyChunk]) -> list[RagQualityCase]:
    by_clause: dict[tuple[str, str], list[PolicyChunk]] = {}
    for chunk in chunks:
        by_clause.setdefault((chunk.documentId, chunk.clauseId), []).append(chunk)

    cases: list[RagQualityCase] = []
    for spec in CASE_SPECS:
        direct_ids = _resolve_clause_ids(by_clause, spec["direct"], spec["id"], "direct")
        support_ids = _resolve_clause_ids(by_clause, spec["support"], spec["id"], "support")
        if direct_ids.intersection(support_ids):
            raise ValueError(f"STEP242F_QREL_ROLE_OVERLAP:{spec['id']}")
        no_answer = not direct_ids and not support_ids
        qrels = [
            _qrel_for_chunk(
                chunk,
                relevance=3 if chunk.chunkId in direct_ids else 2 if chunk.chunkId in support_ids else 0,
            )
            for chunk in chunks
        ]
        cases.append(
            RagQualityCase(
                datasetVersion=DATASET_VERSION,
                caseId=f"asdv1-{spec['id']}",
                split=spec["split"],
                smoke=spec["split"] == "dev" and int(spec["id"]) <= 4,
                reviewText=spec["text"],
                queryStyle=spec["style"],
                riskTypes=[] if no_answer else ["after_sales_risk"],
                riskLevel="normal" if no_answer else "medium",
                noAnswer=no_answer,
                sourceLanguage="not_applicable" if no_answer else "zh",
                documentFormat="not_applicable" if no_answer else "pdf",
                qrels=qrels,
                qrelCompleteness="complete",
                annotationStatus="llm_adjudicated",
                annotationSource="codex_semantic_adjudication_after_sales_delta_v1",
                candidateExposure=spec["split"] == "dev",
                requiresAdjudication=False,
                metadata={
                    "scope": "after_sales_delta",
                    "annotationLimitation": "Single Codex semantic adjudication for a personal demo; not human gold.",
                    "directPreferredChunkIds": sorted(direct_ids),
                    "supportingChunkIds": sorted(support_ids),
                    "holdoutTextExposure": "not_used_for_threshold_selection" if spec["split"] == "holdout" else "dev",
                },
            )
        )
    return cases


def validate_cases(cases: list[RagQualityCase], chunks: list[PolicyChunk]) -> dict[str, Any]:
    corpus_ids = {chunk.chunkId for chunk in chunks}
    case_ids = [case.caseId for case in cases]
    texts = [case.reviewText for case in cases]
    dev = [case for case in cases if case.split == "dev"]
    holdout = [case for case in cases if case.split == "holdout"]
    checks = {
        "currentCorpusHas123Chunks": len(chunks) == 123,
        "caseCountIs24": len(cases) == 24,
        "devCountIs16": len(dev) == 16,
        "holdoutCountIs8": len(holdout) == 8,
        "allQueriesChinese": all(any("\u4e00" <= char <= "\u9fff" for char in case.reviewText) for case in cases),
        "caseIdsUnique": len(case_ids) == len(set(case_ids)),
        "reviewTextsUnique": len(texts) == len(set(texts)),
        "completeQrels": all(len(case.qrels) == len(chunks) and {item.chunkId for item in case.qrels} == corpus_ids for case in cases),
        "allReleaseAnnotatedWithLimitation": all(
            case.annotationStatus == "llm_adjudicated" and not case.requiresAdjudication for case in cases
        ),
        "holdoutNotCandidateExposed": all(not case.candidateExposure for case in holdout),
        "normalCasesHaveNoPositiveQrels": all(
            not any(qrel.relevance >= 2 for qrel in case.qrels) for case in cases if case.noAnswer
        ),
        "riskCasesHaveDirectEvidence": all(
            any(qrel.relevance == 3 for qrel in case.qrels) for case in cases if not case.noAnswer
        ),
        "riskSupportMatchesContract": all(
            set(case.riskTypes).issubset({risk for qrel in case.qrels if qrel.relevance >= 2 for risk in qrel.supports})
            for case in cases
            if not case.noAnswer
        ),
    }
    if not all(checks.values()):
        raise ValueError(f"STEP242F_DATASET_VALIDATION_FAILED:{checks}")
    return {
        "caseCount": len(cases),
        "devCount": len(dev),
        "holdoutCount": len(holdout),
        "riskCaseCount": sum(not case.noAnswer for case in cases),
        "noAnswerCaseCount": sum(case.noAnswer for case in cases),
        "queryStyleCounts": dict(sorted(Counter(case.queryStyle for case in cases).items())),
        "checks": checks,
    }


def write_outputs(cases: list[RagQualityCase], chunks: list[PolicyChunk], validation: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset_path = OUTPUT_DIR / "dataset_llm_adjudicated_v1.jsonl"
    dev_path = OUTPUT_DIR / "dev_llm_adjudicated_v1.jsonl"
    holdout_path = OUTPUT_DIR / "holdout_llm_adjudicated_v1.jsonl"
    qrels_path = OUTPUT_DIR / "qrels_llm_adjudicated_v1.tsv"
    _write_jsonl(dataset_path, [case.model_dump(mode="json") for case in cases])
    _write_jsonl(dev_path, [case.model_dump(mode="json") for case in cases if case.split == "dev"])
    _write_jsonl(holdout_path, [case.model_dump(mode="json") for case in cases if case.split == "holdout"])
    qrels_path.write_text(
        "".join(
            f"{case.caseId}\t0\t{qrel.chunkId}\t{qrel.relevance}\n"
            for case in cases
            for qrel in case.qrels
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schemaVersion": "rag-quality-after-sales-delta-manifest-v1",
        "status": "FROZEN_LLM_ADJUDICATED_AWAITING_DEV_BASELINE",
        "datasetVersion": DATASET_VERSION,
        "purpose": "Corpus-bound delta evaluation for the two after-sales PDF sources added after the 71-chunk frozen corpus.",
        "limitation": "Single Codex semantic adjudication for a personal demo; not human gold and not a global workflow promotion result.",
        "corpus": {
            "chunkCount": len(chunks),
            "contentRootHash": _content_root_hash(chunks),
            "documents": sorted({chunk.documentId for chunk in chunks}),
            "newDocuments": ["cn_consumer_rights_protection_law", "cn_online_return_without_reason"],
        },
        "files": {
            name: {"path": name, "sha256": _sha256_file(OUTPUT_DIR / name)}
            for name in (dataset_path.name, dev_path.name, holdout_path.name, qrels_path.name)
        },
        "annotation": {
            "status": "llm_adjudicated",
            "source": "codex_semantic_adjudication_after_sales_delta_v1",
            "humanVerifiedCaseCount": 0,
            "llmAdjudicatedCaseCount": len(cases),
            "qrelCompleteness": "complete",
            "candidateExposure": {"dev": True, "holdout": False},
            "holdoutExecuted": False,
            "thresholdsFrozen": False,
        },
        "validation": validation,
    }
    _write_json(OUTPUT_DIR / "manifest_llm_adjudicated_v1.json", manifest)


def _resolve_clause_ids(
    by_clause: dict[tuple[str, str], list[PolicyChunk]],
    references: list[tuple[str, str]],
    case_id: str,
    role: str,
) -> set[str]:
    result: set[str] = set()
    for reference in references:
        matched = by_clause.get(reference, [])
        if not matched:
            raise ValueError(f"STEP242F_QREL_CLAUSE_NOT_FOUND case={case_id} role={role} reference={reference}")
        result.update(chunk.chunkId for chunk in matched)
    return result


def _qrel_for_chunk(chunk: PolicyChunk, *, relevance: int) -> QualityQrel:
    supports = ["after_sales_risk"] if relevance >= 2 else []
    rationale = (
        "Direct preferred policy evidence for the described after-sales dispute."
        if relevance == 3
        else "Supporting policy evidence for the described after-sales dispute."
        if relevance == 2
        else "Not sufficient evidence for this case."
    )
    return QualityQrel(
        chunkId=chunk.chunkId,
        relevance=relevance,
        supports=supports,
        sourceName=chunk.sourceName,
        sourceType=chunk.sourceType,
        sourceLevel="A" if chunk.sourceType in {"law", "regulation"} else "B",
        clauseId=chunk.clauseId,
        rationale=rationale,
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _content_root_hash(chunks: list[PolicyChunk]) -> str:
    return hashlib.sha256("|".join(chunk.contentHash for chunk in chunks).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
