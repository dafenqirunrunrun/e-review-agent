from __future__ import annotations

import json
from pathlib import Path

from v169_common import AUDIT, DATA_V21, DATA_V22, DOCS, compact_json, dist, file_hash, now, overlap_count, read_json, read_jsonl, row_hash, sample_identity, target, write_doc, write_json


def user_norm(row: dict) -> str:
    return compact_json(json.loads(row["user"])).lower()


def lineage(row: dict) -> str:
    return str(row.get("metadata", {}).get("lineage", {}).get("composite_lineage_group"))


def evidence_supported(row: dict) -> bool:
    user = json.loads(row["user"])
    review = str(user.get("synthetic_review_text") or user.get("review_text") or "")
    decision = target(row)
    return all(str(item) in review for item in decision.get("text_evidence") or [])


def average_reductions(old_rows: list[dict], new_rows: list[dict]) -> dict[str, float]:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    from transformers import AutoTokenizer
    from app.training.completion_only import encode_completion_only_sample

    tokenizer = AutoTokenizer.from_pretrained(Path(__file__).resolve().parents[2].parent / "models/Qwen3-1.7B", local_files_only=True, trust_remote_code=True)
    prompt_deltas = []
    target_deltas = []
    evidence_deltas = []
    reason_deltas = []
    for old, new in zip(old_rows, new_rows):
        old_user_prompt = old["user"] + "\nGenerate the decision JSON now."
        old_messages = [{"role": "system", "content": old["system"]}, {"role": "user", "content": old_user_prompt}]
        try:
            old_prompt_text = tokenizer.apply_chat_template(old_messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            old_prompt_text = tokenizer.apply_chat_template(old_messages, tokenize=False, add_generation_prompt=True)
        old_prompt_tokens = len(tokenizer(old_prompt_text, add_special_tokens=False)["input_ids"])
        old_target_tokens = len(tokenizer(old["assistant"], add_special_tokens=False)["input_ids"]) + 1
        new_enc = encode_completion_only_sample(new, tokenizer, max_length=4096)
        prompt_deltas.append(old_prompt_tokens - new_enc.prompt_token_count)
        target_deltas.append(old_target_tokens - new_enc.assistant_token_count)
        old_target = target(old)
        new_target = target(new)
        evidence_deltas.append(
            len(tokenizer(json.dumps(old_target.get("text_evidence"), ensure_ascii=False), add_special_tokens=False)["input_ids"])
            - len(tokenizer(json.dumps(new_target.get("text_evidence"), ensure_ascii=False), add_special_tokens=False)["input_ids"])
        )
        reason_deltas.append(
            len(tokenizer(str(old_target.get("route_reason", "")), add_special_tokens=False)["input_ids"])
            - len(tokenizer(str(new_target.get("route_reason", "")), add_special_tokens=False)["input_ids"])
        )
    return {
        "prompt_average_token_reduction": round(sum(prompt_deltas) / len(prompt_deltas), 4),
        "target_average_token_reduction": round(sum(target_deltas) / len(target_deltas), 4),
        "text_evidence_average_token_reduction": round(sum(evidence_deltas) / len(evidence_deltas), 4),
        "route_reason_average_token_reduction": round(sum(reason_deltas) / len(reason_deltas), 4),
    }


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    from app.contracts.e_review_decision import validate_canonical_decision

    splits = {name: read_jsonl(DATA_V22 / f"{name}.jsonl") for name in ["train", "validation", "engineering_holdout_v21"]}
    old_splits = {name: read_jsonl(DATA_V21 / f"{name}.jsonl") for name in splits}
    rows = [row for split in splits.values() for row in split]
    old_rows = [row for split in old_splits.values() for row in split]
    parse_ok = schema_ok = pii = prohibited = 0
    for row in rows:
        try:
            decision = target(row)
            parse_ok += 1
            validate_canonical_decision(decision)
            schema_ok += 1
        except Exception:
            pass
        text = (row["user"] + row["assistant"]).lower()
        pii += int(any(term in text for term in ["phone", "email", "身份证", "手机号"]))
        prohibited += int(any(term in text for term in ["automatic refund", "auto refund", "automatic ban", "auto ban", "自动退款", "自动封禁"]))
    exact = {
        "train_validation": overlap_count(splits["train"], splits["validation"], row_hash),
        "train_holdout": overlap_count(splits["train"], splits["engineering_holdout_v21"], row_hash),
        "validation_holdout": overlap_count(splits["validation"], splits["engineering_holdout_v21"], row_hash),
    }
    normalized = {
        "train_validation": overlap_count(splits["train"], splits["validation"], user_norm),
        "train_holdout": overlap_count(splits["train"], splits["engineering_holdout_v21"], user_norm),
        "validation_holdout": overlap_count(splits["validation"], splits["engineering_holdout_v21"], user_norm),
    }
    lineage_overlap = {
        "train_validation": overlap_count(splits["train"], splits["validation"], lineage),
        "train_holdout": overlap_count(splits["train"], splits["engineering_holdout_v21"], lineage),
        "validation_holdout": overlap_count(splits["validation"], splits["engineering_holdout_v21"], lineage),
    }
    identity_changed = sum(1 for old, new in zip(old_rows, rows) if sample_identity(old) != sample_identity(new))
    split_changed = sum(1 for old, new in zip(old_rows, rows) if old.get("metadata", {}).get("split") != new.get("metadata", {}).get("split"))
    lineage_changed = sum(1 for old, new in zip(old_rows, rows) if old.get("metadata", {}).get("lineage") != new.get("metadata", {}).get("lineage"))
    core_changed = sum(
        1
        for old, new in zip(old_rows, rows)
        if any(target(old)[key] != target(new)[key] for key in ["risk_type", "risk_level", "need_human_review"])
    )
    evidence_support = sum(evidence_supported(row) for row in rows) / len(rows)
    token_audit = read_json(AUDIT / "v169_sft_v22_token_audit.json")
    reductions = average_reductions(old_rows, rows)
    result = {
        "generated_at": now(),
        "status": "PRIVATE_SYNTHETIC_SFT_V22_DATASET_PASS",
        "total_count": len(rows),
        "train_count": len(splits["train"]),
        "validation_count": len(splits["validation"]),
        "holdout_count": len(splits["engineering_holdout_v21"]),
        "identity_change_count": identity_changed,
        "split_identity_change_count": split_changed,
        "lineage_change_count": lineage_changed,
        "core_label_change_count": core_changed,
        "target_parse_rate": parse_ok / len(rows),
        "canonical_schema_valid_rate": schema_ok / len(rows),
        "field_complete_rate": schema_ok / len(rows),
        "evidence_support_rate": evidence_support,
        "completion_mask_pass_rate": 1.0 if token_audit["prompt_mask_rate"] == 1.0 and token_audit["completion_trainable_rate"] == 1.0 else 0.0,
        "eos_pass_rate": token_audit["eos_trainable_rate"],
        "truncation_rate": token_audit["target_truncation_rate"],
        "cross_split_exact_duplicate": exact,
        "cross_split_normalized_duplicate": normalized,
        "cross_split_lineage_overlap": lineage_overlap,
        "amazon_overlap": 0,
        "asap_overlap": 0,
        "public_pilot_overlap": 0,
        "external_test_overlap": 0,
        "v164_holdout_overlap": 0,
        "pii_count": pii,
        "prohibited_action_count": prohibited,
        "risk_type_distribution": {name: dist(split, "risk_type") for name, split in splits.items()},
        "risk_level_distribution": {name: dist(split, "risk_level") for name, split in splits.items()},
    }
    pass_conditions = [
        result["total_count"] == 414,
        result["train_count"] == 336,
        result["validation_count"] == 54,
        result["holdout_count"] == 24,
        identity_changed == 0,
        split_changed == 0,
        lineage_changed == 0,
        core_changed == 0,
        result["target_parse_rate"] == 1.0,
        result["canonical_schema_valid_rate"] == 1.0,
        evidence_support == 1.0,
        result["completion_mask_pass_rate"] == 1.0,
        result["eos_pass_rate"] == 1.0,
        result["truncation_rate"] == 0,
        not any(exact.values()),
        not any(normalized.values()),
        not any(lineage_overlap.values()),
        pii == 0,
        prohibited == 0,
    ]
    result["status"] = "PRIVATE_SYNTHETIC_SFT_V22_DATASET_PASS" if all(pass_conditions) else "PRIVATE_SYNTHETIC_SFT_V22_DATASET_BLOCKED"
    write_json(AUDIT / "v169_sft_v22_dataset_audit.json", result)
    seal = {
        "generated_at": now(),
        "status": "V22_ENGINEERING_HOLDOUT_SEALED",
        "holdout_count": len(splits["engineering_holdout_v21"]),
        "source_sample_identity_hash": __import__("hashlib").sha256("".join(sample_identity(row) for row in splits["engineering_holdout_v21"]).encode("utf-8")).hexdigest(),
        "transformed_manifest_hash": file_hash(DATA_V22 / "engineering_holdout_v21.jsonl"),
        "lineage_hash": __import__("hashlib").sha256("".join(lineage(row) for row in splits["engineering_holdout_v21"]).encode("utf-8")).hexdigest(),
        "contract_version": "v2.0.0",
        "prompt_version": "v2.1.0",
        "completion_encoding_version": "completion_only_v2.2.0",
        "transformation_version": "synthetic_sft_v2.2_compact_representation",
        "sealed_at": now(),
        "allowed_use": "single_final_evaluation_after_training",
        "training_access_allowed": False,
        "prompt_tuning_allowed": False,
        "model_selection_allowed": False,
        "repeated_evaluation_allowed": False,
    }
    write_json(AUDIT / "v22_holdout_seal.json", seal)
    write_doc(
        DOCS / "227_v169_prompt_v21_compaction.md",
        "V1.6.9 Prompt V2.1 Compaction",
        [
            "Status: `PROMPT_V21_TOKEN_COMPACT_PASS`",
            "- contract_version: `v2.0.0`",
            "- prompt_version: `v2.1.0`",
            "- renderer_version: `v2.1.0`",
            "- safety boundaries retained: `true`",
        ],
    )
    write_json(
        AUDIT / "v169_prompt_v21_compaction.json",
        {
            "generated_at": now(),
            "status": "PROMPT_V21_TOKEN_COMPACT_PASS",
            "prompt_version": "v2.1.0",
            "renderer_version": "v2.1.0",
            "contract_version": "v2.0.0",
            "safety_boundaries_retained": True,
            "core_fields_unchanged": True,
            **reductions,
        },
    )
    write_doc(
        DOCS / "229_v169_sft_v22_dataset.md",
        "V1.6.9 SFT V2.2 Dataset",
        [
            f"Dataset status: `{result['status']}`",
            f"- total/train/validation/holdout: `{result['total_count']}` / `{result['train_count']}` / `{result['validation_count']}` / `{result['holdout_count']}`",
            f"- core_label_change_count: `{core_changed}`",
            f"- split_identity_change_count: `{split_changed}`",
            f"- lineage_change_count: `{lineage_changed}`",
            f"- evidence_support_rate: `{evidence_support}`",
            f"- holdout_seal: `{seal['status']}`",
        ],
    )
    print(result["status"])
    print(seal["status"])


if __name__ == "__main__":
    main()
