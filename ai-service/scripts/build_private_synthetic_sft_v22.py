from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from v169_common import DATA_V21, DATA_V22, AUDIT, DOCS, compact_json, read_jsonl, sample_identity, target, write_doc, write_json, write_jsonl, now, file_hash

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
from app.contracts.e_review_decision import E_REVIEW_DECISION_SCHEMA_VERSION, validate_canonical_decision  # noqa: E402
from app.prompts.e_review_decision_prompt import E_REVIEW_DECISION_PROMPT_VERSION, system_prompt  # noqa: E402
from app.prompts.e_review_prompt_renderer import E_REVIEW_PROMPT_RENDERER_VERSION  # noqa: E402
from app.training.compact_target_serialization import COMPACT_TARGET_SERIALIZATION_VERSION, compact_canonical_serialize  # noqa: E402
from app.training.completion_only import COMPLETION_ONLY_ENCODING_VERSION  # noqa: E402


ROUTE_REASON = {
    ("normal_review", "low", False): "商品体验正常，无明确风险",
    ("negative_review", "medium", True): "存在负面体验，需复核",
    ("after_sales_risk", "medium", True): "存在售后风险，需复核",
    ("after_sales_risk", "high", True): "存在高售后风险，需人工处理",
}


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = re.sub(r"([。.!?；;])\1+", r"\1", text)
    parts = [part.strip() for part in re.split(r"(?<=[。.!?；;])\s*", text) if part.strip()]
    deduped = []
    seen = set()
    for part in parts or [text]:
        key = part.lower()
        if key not in seen:
            deduped.append(part)
            seen.add(key)
    return " ".join(deduped).strip()


def shortest_supported_evidence(review: str, decision: dict[str, Any]) -> list[str]:
    review_norm = normalize_text(review)
    candidates: list[str] = []
    for item in decision.get("text_evidence") or []:
        text = normalize_text(item)
        if text and text in review_norm:
            candidates.append(text[:48])
    lowered = review_norm.lower()
    keyword_groups = [
        ["leakage", "missing", "refund", "return", "damaged", "broken", "counterfeit", "battery", "safety", "wrong", "缺", "漏", "破", "坏", "退款", "退货", "安全"],
        ["negative", "delay", "bad", "poor", "no response", "差", "慢", "延迟", "失望"],
        ["normal", "positive", "neutral", "good", "完好", "正常", "满意"],
    ]
    for group in keyword_groups:
        for keyword in group:
            idx = lowered.find(keyword.lower())
            if idx >= 0:
                start = max(0, idx - 18)
                end = min(len(review_norm), idx + len(keyword) + 24)
                snippet = review_norm[start:end].strip(" ,.;:，。；：")
                if snippet:
                    candidates.append(snippet[:48])
                break
        if candidates:
            break
    if not candidates and review_norm:
        candidates.append(review_norm[:48])
    unique = []
    for item in candidates:
        if item and item not in unique and item in review_norm:
            unique.append(item)
    return unique[:1]


def compact_decision(row: dict[str, Any]) -> dict[str, Any]:
    user = json.loads(row["user"])
    decision = target(row)
    review = normalize_text(user.get("synthetic_review_text") or user.get("review_text") or "")
    risk_type = decision["risk_type"]
    risk_level = decision["risk_level"]
    need_human = bool(decision["need_human_review"])
    compacted = {
        "schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "risk_type": risk_type,
        "risk_level": risk_level,
        "text_evidence": shortest_supported_evidence(review, decision),
        "visual_evidence": [],
        "retrieved_case_evidence": [],
        "need_human_review": need_human,
        "route_reason": ROUTE_REASON.get((risk_type, risk_level, need_human), "需按评论证据复核"),
        "missing_information": list(decision.get("missing_information") or [])[:2],
        "unsupported_claims": list(decision.get("unsupported_claims") or [])[:2],
    }
    validate_canonical_decision(compacted)
    return compacted


def convert_row(row: dict[str, Any]) -> dict[str, Any]:
    user = json.loads(row["user"])
    review = normalize_text(user.get("synthetic_review_text") or user.get("review_text") or "")
    new_user = {
        "synthetic_review_text": review,
        "synthetic_rating": user.get("synthetic_rating"),
        "synthetic_product_category": user.get("synthetic_product_category") or "synthetic_fixture",
    }
    case_summary = user.get("synthetic_retrieved_case_summary")
    if case_summary:
        new_user["synthetic_retrieved_case_summary"] = normalize_text(case_summary)[:64]
    decision = compact_decision({**row, "user": compact_json(new_user)})
    metadata = dict(row.get("metadata") or {})
    metadata.update(
        {
            "contract_version": E_REVIEW_DECISION_SCHEMA_VERSION,
            "prompt_version": E_REVIEW_DECISION_PROMPT_VERSION,
            "renderer_version": E_REVIEW_PROMPT_RENDERER_VERSION,
            "completion_encoding_version": COMPLETION_ONLY_ENCODING_VERSION,
            "target_serialization_version": COMPACT_TARGET_SERIALIZATION_VERSION,
            "dataset_version": "synthetic_sft_v2.2",
            "source_sample_identity": sample_identity(row),
        }
    )
    return {
        "system": system_prompt(),
        "user": compact_json(new_user),
        "assistant": compact_canonical_serialize(decision),
        "metadata": metadata,
    }


def split_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "risk_type": dict(Counter(target(row)["risk_type"] for row in rows)),
        "risk_level": dict(Counter(target(row)["risk_level"] for row in rows)),
        "need_human_review": dict(Counter(str(target(row)["need_human_review"]) for row in rows)),
    }


def main() -> None:
    DATA_V22.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, list[dict[str, Any]]] = {}
    identity_changes = split_changes = lineage_changes = core_label_changes = 0
    for split in ["train", "validation", "engineering_holdout_v21"]:
        source = read_jsonl(DATA_V21 / f"{split}.jsonl")
        converted = []
        for row in source:
            new_row = convert_row(row)
            old_target = target(row)
            new_target = target(new_row)
            identity_changes += int(sample_identity(row) != sample_identity(new_row))
            split_changes += int(row.get("metadata", {}).get("split") != new_row.get("metadata", {}).get("split"))
            lineage_changes += int(row.get("metadata", {}).get("lineage") != new_row.get("metadata", {}).get("lineage"))
            core_label_changes += int(
                any(old_target[key] != new_target[key] for key in ["risk_type", "risk_level", "need_human_review"])
            )
            converted.append(new_row)
        manifest[split] = converted
        write_jsonl(DATA_V22 / f"{split}.jsonl", converted)
    summary = {
        "generated_at": now(),
        "status": "PRIVATE_SYNTHETIC_SFT_V22_BUILT",
        "total_count": sum(len(rows) for rows in manifest.values()),
        "train_count": len(manifest["train"]),
        "validation_count": len(manifest["validation"]),
        "holdout_count": len(manifest["engineering_holdout_v21"]),
        "identity_change_count": identity_changes,
        "split_identity_change_count": split_changes,
        "lineage_change_count": lineage_changes,
        "core_label_change_count": core_label_changes,
        "contract_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "prompt_version": E_REVIEW_DECISION_PROMPT_VERSION,
        "renderer_version": E_REVIEW_PROMPT_RENDERER_VERSION,
        "completion_encoding_version": COMPLETION_ONLY_ENCODING_VERSION,
        "target_serialization_version": COMPACT_TARGET_SERIALIZATION_VERSION,
        "distributions": {split: split_counts(rows) for split, rows in manifest.items()},
        "manifest_hashes": {split: file_hash(DATA_V22 / f"{split}.jsonl") for split in manifest},
    }
    write_json(AUDIT / "v169_sft_v22_build_summary.json", summary)
    write_doc(
        DOCS / "228_v169_sft_v22_token_contract.md",
        "V1.6.9 SFT V2.2 Token Contract",
        [
            f"Status: `{summary['status']}`",
            f"- total_count: `{summary['total_count']}`",
            f"- prompt_version: `{summary['prompt_version']}`",
            f"- renderer_version: `{summary['renderer_version']}`",
            f"- completion_encoding_version: `{summary['completion_encoding_version']}`",
            f"- core_label_change_count: `{summary['core_label_change_count']}`",
            f"- split_identity_change_count: `{summary['split_identity_change_count']}`",
            f"- lineage_change_count: `{summary['lineage_change_count']}`",
        ],
    )
    print(summary["status"])


if __name__ == "__main__":
    main()
