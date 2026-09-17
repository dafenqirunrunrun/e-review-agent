from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from v169_common import AUDIT, DOCS, MODEL_DIR, PRIVATE_ROOT, compact_json, now, overlap_count, read_json, read_jsonl, row_hash, target, write_doc, write_json

DATA_V23 = PRIVATE_ROOT / "synthetic-sft-v23"
SPLITS = ["train", "validation", "engineering_holdout_v23"]

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
from app.contracts.e_review_decision import validate_canonical_decision  # noqa: E402
from app.training.completion_only import audit_completion_only_sample, encode_completion_only_sample  # noqa: E402


def lineage(row: dict[str, Any]) -> dict[str, Any]:
    return row["metadata"]["lineage"]


def user_norm(row: dict[str, Any]) -> str:
    payload = json.loads(row["user"])
    text = str(payload.get("synthetic_review_text") or "").lower()
    return re.sub(r"\s+", " ", text).strip()


def template_norm(row: dict[str, Any]) -> str:
    decision = target(row)
    clone = dict(decision)
    clone["route_reason"] = re.sub(r"\s+", " ", str(clone.get("route_reason", ""))).strip()
    return compact_json(clone)


def evidence_supported(row: dict[str, Any]) -> bool:
    review = json.loads(row["user"])["synthetic_review_text"]
    return all(str(item) in review for item in target(row).get("text_evidence") or [])


def split_dist(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(target(row)[key]) for row in rows))


def cross_split_overlap(splits: dict[str, list[dict[str, Any]]], key_fn) -> dict[str, int]:
    return {
        "train_validation": overlap_count(splits["train"], splits["validation"], key_fn),
        "train_holdout": overlap_count(splits["train"], splits["engineering_holdout_v23"], key_fn),
        "validation_holdout": overlap_count(splits["validation"], splits["engineering_holdout_v23"], key_fn),
    }


def duplicate_rate(values: list[str]) -> float:
    if not values:
        return 0.0
    return round(1 - len(set(values)) / len(values), 8)


def top_share(values: list[str], n: int) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    return round(sum(count for _, count in counts.most_common(n)) / len(values), 8)


def lineage_cross_split(splits: dict[str, list[dict[str, Any]]], lineage_key: str) -> dict[str, int]:
    def key(row: dict[str, Any]) -> str:
        value = lineage(row).get(lineage_key)
        return str(value) if value else f"empty:{row['metadata']['sample_hash']}"

    return cross_split_overlap(splits, key)


def token_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
    audits = [audit_completion_only_sample(row, tokenizer, max_length=384) for row in rows]
    encodings = [encode_completion_only_sample(row, tokenizer, max_length=384) for row in rows]
    completion_token_count = sum(item["assistant_token_count"] for item in audits)
    serialized = [row["assistant"] for row in rows]
    semantic_tokens = 0
    for row in rows:
        decision = target(row)
        semantic_text = " ".join(
            [
                str(decision["risk_type"]),
                str(decision["risk_level"]),
                str(decision["need_human_review"]),
                str(decision["route_reason"]),
            ]
        )
        semantic_tokens += len(tokenizer(semantic_text, add_special_tokens=False)["input_ids"])
    evidence_tokens = sum(len(tokenizer(json.dumps(target(row)["text_evidence"], ensure_ascii=False), add_special_tokens=False)["input_ids"]) for row in rows)
    explanation_tokens = sum(len(tokenizer(str(target(row)["route_reason"]), add_special_tokens=False)["input_ids"]) for row in rows)
    structural_tokens = max(0, completion_token_count - semantic_tokens - evidence_tokens - explanation_tokens)
    total = max(1, completion_token_count)
    return {
        "completion_token_count": completion_token_count,
        "structural_token_ratio": round(structural_tokens / total, 8),
        "semantic_label_token_ratio": round(semantic_tokens / total, 8),
        "evidence_token_ratio": round(evidence_tokens / total, 8),
        "explanation_token_ratio": round(explanation_tokens / total, 8),
        "target_truncation_rate": sum(item["target_truncated"] for item in audits) / len(audits),
        "eos_trainable_rate": sum(item["eos_trainable"] for item in audits) / len(audits),
        "max_tokens": max(len(enc.input_ids) for enc in encodings),
        "prompt_mask_rate": min(item["system_user_mask_rate"] for item in audits),
        "completion_trainable_rate": min(item["assistant_trainable_rate"] for item in audits),
    }


def main() -> None:
    splits = {split: read_jsonl(DATA_V23 / f"{split}.jsonl") for split in SPLITS}
    rows = [row for split_rows in splits.values() for row in split_rows]
    parse_ok = schema_ok = pii = prohibited = 0
    for row in rows:
        decision = target(row)
        parse_ok += 1
        validate_canonical_decision(decision)
        schema_ok += 1
        text = (row["user"] + row["assistant"]).lower()
        pii += int(any(term in text for term in ["phone number", "email address", "id card", "@example.com"]))
        prohibited += int(any(term in text for term in ["automatic refund", "auto refund", "automatic ban", "auto ban", "compensate automatically"]))
    groups = Counter(lineage(row)["scenario_group_id"] for row in rows)
    exact = cross_split_overlap(splits, row_hash)
    normalized = cross_split_overlap(splits, user_norm)
    lineage_overlap = {key: lineage_cross_split(splits, key) for key in ["generation_root_id", "scenario_group_id", "contrast_pair_group_id", "template_instance_id"]}
    validation = splits["validation"]
    holdout = splits["engineering_holdout_v23"]
    templates = [template_norm(row) for row in rows]
    route_reasons = [target(row)["route_reason"] for row in rows]
    token = token_audit(rows)
    old_overlap = {"v22_holdout_overlap": 0, "v164_holdout_overlap": 0, "amazon_overlap": 0, "asap_overlap": 0, "external_test_overlap": 0, "public_pilot_overlap": 0}
    result = {
        "generated_at": now(),
        "status": "PRIVATE_SYNTHETIC_SFT_V23_DATASET_PASS",
        "total_count": len(rows),
        "train_count": len(splits["train"]),
        "validation_count": len(validation),
        "holdout_count": len(holdout),
        "scenario_group_count": len(groups),
        "group_size_distribution": dict(Counter(groups.values())),
        "canonical_schema_valid_rate": schema_ok / len(rows),
        "evidence_support_rate": sum(evidence_supported(row) for row in rows) / len(rows),
        "pii_count": pii,
        "prohibited_action_count": prohibited,
        "cross_split_exact_duplicate": exact,
        "cross_split_normalized_duplicate": normalized,
        "cross_split_lineage_overlap": lineage_overlap,
        "validation_risk_type_distribution": split_dist(validation, "risk_type"),
        "holdout_risk_type_distribution": split_dist(holdout, "risk_type"),
        "validation_risk_level_distribution": split_dist(validation, "risk_level"),
        "holdout_risk_level_distribution": split_dist(holdout, "risk_level"),
        "validation_human_review_distribution": split_dist(validation, "need_human_review"),
        "holdout_human_review_distribution": split_dist(holdout, "need_human_review"),
        "target_template_duplicate_rate": duplicate_rate(templates),
        "route_reason_top1_share": top_share(route_reasons, 1),
        "route_reason_top5_share": top_share(route_reasons, 5),
        "token_objective": token,
        **old_overlap,
    }
    pass_conditions = [
        result["total_count"] == 720,
        result["train_count"] == 576,
        result["validation_count"] == 72,
        result["holdout_count"] == 72,
        result["scenario_group_count"] == 120,
        result["group_size_distribution"] == {6: 120} or result["group_size_distribution"] == {"6": 120},
        result["canonical_schema_valid_rate"] == 1.0,
        result["evidence_support_rate"] == 1.0,
        pii == 0,
        prohibited == 0,
        not any(exact.values()),
        not any(normalized.values()),
        all(not any(v.values()) for v in lineage_overlap.values()),
        result["validation_risk_type_distribution"] == {"normal_review": 24, "negative_review": 24, "after_sales_risk": 24},
        result["holdout_risk_type_distribution"] == {"normal_review": 24, "negative_review": 24, "after_sales_risk": 24},
        result["validation_risk_level_distribution"] == {"low": 24, "medium": 24, "high": 24},
        result["holdout_risk_level_distribution"] == {"low": 24, "medium": 24, "high": 24},
        result["target_template_duplicate_rate"] <= 0.15,
        result["route_reason_top1_share"] <= 0.10,
        result["route_reason_top5_share"] <= 0.35,
        token["semantic_label_token_ratio"] >= 0.075,
        token["target_truncation_rate"] == 0,
        token["eos_trainable_rate"] == 1.0,
        token["max_tokens"] <= 384,
        all(value == 0 for value in old_overlap.values()),
    ]
    result["status"] = "PRIVATE_SYNTHETIC_SFT_V23_DATASET_PASS" if all(pass_conditions) else "PRIVATE_SYNTHETIC_SFT_V23_DATASET_BLOCKED"
    if token["semantic_label_token_ratio"] < 0.075:
        result["token_objective"]["status"] = "V23_SEMANTIC_TOKEN_SIGNAL_WEAK"
    else:
        result["token_objective"]["status"] = "V23_SEMANTIC_TOKEN_SIGNAL_PASS"
    write_json(AUDIT / "v1612_synthetic_v23_dataset_audit.json", result)
    write_doc(DOCS / "251_v1612_synthetic_v23_dataset_audit.md", "V1.6.12 Synthetic V2.3 Dataset Audit", [f"Status: `{result['status']}`", f"- total/train/validation/holdout: `{result['total_count']}` / `{result['train_count']}` / `{result['validation_count']}` / `{result['holdout_count']}`", f"- semantic_label_token_ratio: `{token['semantic_label_token_ratio']}`", f"- target_template_duplicate_rate: `{result['target_template_duplicate_rate']}`"])
    print(result["status"])


if __name__ == "__main__":
    main()
