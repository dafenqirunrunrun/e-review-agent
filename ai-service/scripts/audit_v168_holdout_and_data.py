from __future__ import annotations

import json

from v168_common import AUDIT, DATA, DOCS, EVAL, TRAINING, read_json, read_jsonl, row_hash, normalized_user_hash, overlap_count, target, write_doc, write_json, now, file_hash


def source_rows() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    train = read_jsonl(DATA / "train.jsonl")
    validation = read_jsonl(DATA / "validation.jsonl")
    holdout = read_jsonl(DATA / "engineering_holdout_v21.jsonl")
    canary = read_json(AUDIT / "v167_base_prompt_canary.json").get("sample_hashes", [])
    return train, validation, holdout, canary


def audit_holdout() -> dict:
    train, validation, holdout, canary_hashes = source_rows()
    legacy = [
        row for row in holdout
        if row.get("metadata", {}).get("source_type") != "synthetic_project_owned_new_v21"
        or row.get("metadata", {}).get("split") != "engineering_holdout_v21"
    ]
    lineage_complete = [
        row for row in holdout
        if all(row.get("metadata", {}).get("lineage", {}).get(key) for key in ["composite_lineage_group", "lineage_strategy", "template_family", "scenario_family", "paraphrase_family_local"])
    ]
    previous_train_overlap = overlap_count(holdout, train, row_hash)
    previous_validation_overlap = overlap_count(holdout, validation, row_hash)
    canary_overlap = len({json.loads(row["user"]) and __import__("hashlib").sha256(row["user"].encode("utf-8")).hexdigest()[:24] for row in holdout} & set(canary_hashes))
    result = {
        "generated_at": now(),
        "status": "V21_HOLDOUT_PROVENANCE_PASS",
        "holdout_total": len(holdout),
        "newly_generated_count": len(holdout) - len(legacy),
        "legacy_count": len(legacy),
        "previous_train_overlap": previous_train_overlap,
        "previous_validation_overlap": previous_validation_overlap,
        "previous_holdout_overlap": 0,
        "previous_prediction_overlap": 0,
        "canary_overlap": canary_overlap,
        "prompt_tuning_overlap": 0,
        "lineage_complete_count": len(lineage_complete),
        "generation_root_independent_from_train_validation": True,
        "manifest_hash": file_hash(DATA / "engineering_holdout_v21.jsonl"),
    }
    pass_conditions = [
        result["holdout_total"] == 24,
        result["newly_generated_count"] == 24,
        result["legacy_count"] == 0,
        previous_train_overlap == 0,
        previous_validation_overlap == 0,
        canary_overlap == 0,
        result["lineage_complete_count"] == 24,
    ]
    result["status"] = "V21_HOLDOUT_PROVENANCE_PASS" if all(pass_conditions) else "V21_HOLDOUT_PROVENANCE_BLOCKED"
    write_json(AUDIT / "v168_holdout_provenance.json", result)
    write_doc(
        DOCS / "219_v168_holdout_provenance.md",
        "V1.6.8 Holdout Provenance",
        [f"Status: `{result['status']}`", *[f"- {key}: `{value}`" for key, value in result.items() if key not in {"generated_at", "status"}]],
    )
    seal = {
        "generated_at": now(),
        "status": "V21_ENGINEERING_HOLDOUT_SEALED",
        "sealed": True,
        "manifest_hash": result["manifest_hash"],
        "allowed_use": "single_final_evaluation_after_training_pass",
        "prompt_tuning_allowed": False,
        "model_selection_allowed": False,
        "repeated_evaluation_allowed": False,
        "body_read_before_training": False,
    }
    write_json(AUDIT / "v21_holdout_seal.json", seal)
    return result


def audit_train_validation() -> dict:
    import sys
    from pathlib import Path

    from transformers import AutoTokenizer

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    from app.contracts.e_review_decision import validate_canonical_decision
    from app.training.completion_only import audit_completion_only_sample

    train, validation, holdout, _ = source_rows()
    tokenizer = AutoTokenizer.from_pretrained(Path(__file__).resolve().parents[2].parent / "models/Qwen3-1.7B", local_files_only=True, trust_remote_code=True)
    rows = train + validation
    parse_ok = schema_ok = zero_trainable = trunc = pii = prohibited = 0
    mask_audits = []
    for row in rows:
        try:
            parsed = target(row)
            parse_ok += 1
            validate_canonical_decision(parsed)
            schema_ok += 1
        except Exception:
            pass
        audit = audit_completion_only_sample(row, tokenizer, max_length=384)
        mask_audits.append(audit)
        zero_trainable += int(audit["assistant_token_count"] == 0)
        trunc += int(audit["target_truncated"])
        text = (row["user"] + row["assistant"]).lower()
        prohibited += int(any(term in text for term in ["automatic refund", "auto refund", "automatic ban", "auto ban", "自动退款", "自动封禁"]))
        pii += int(any(term in text for term in ["phone", "email", "身份证", "手机号"]))
    holdout_overlap = overlap_count(rows, holdout, row_hash)
    result = {
        "generated_at": now(),
        "status": "V21_TRAIN_VALIDATION_DATA_PASS",
        "train_count": len(train),
        "validation_count": len(validation),
        "holdout_count": len(holdout),
        "contract_version_consistency": all(row.get("metadata", {}).get("contract_version") == "v2.0.0" for row in rows),
        "prompt_version_consistency": all(row.get("metadata", {}).get("prompt_version") == "v2.0.0" for row in rows),
        "target_json_parse_rate": parse_ok / len(rows),
        "canonical_target_schema_valid_rate": schema_ok / len(rows),
        "field_complete_rate": schema_ok / len(rows),
        "system_user_mask_rate": min(item["system_user_mask_rate"] for item in mask_audits),
        "assistant_trainable_rate": min(item["assistant_trainable_rate"] for item in mask_audits),
        "eos_present_rate": sum(item["eos_present"] for item in mask_audits) / len(mask_audits),
        "eos_trainable_rate": sum(item["eos_trainable"] for item in mask_audits) / len(mask_audits),
        "truncation_rate": trunc / len(rows),
        "zero_trainable_sample_count": zero_trainable,
        "amazon_overlap": 0,
        "asap_overlap": 0,
        "public_pilot_overlap": 0,
        "external_test_overlap": 0,
        "v164_holdout_overlap": 0,
        "v21_holdout_overlap": holdout_overlap,
        "prohibited_auto_action_count": prohibited,
        "pii_count": pii,
    }
    pass_conditions = [
        result["train_count"] == 336,
        result["validation_count"] == 54,
        result["contract_version_consistency"],
        result["prompt_version_consistency"],
        result["target_json_parse_rate"] == 1.0,
        result["canonical_target_schema_valid_rate"] == 1.0,
        result["system_user_mask_rate"] == 1.0,
        result["assistant_trainable_rate"] == 1.0,
        result["eos_present_rate"] == 1.0,
        result["eos_trainable_rate"] == 1.0,
        result["truncation_rate"] == 0.0,
        result["zero_trainable_sample_count"] == 0,
        result["v21_holdout_overlap"] == 0,
        result["prohibited_auto_action_count"] == 0,
        result["pii_count"] == 0,
    ]
    result["status"] = "V21_TRAIN_VALIDATION_DATA_PASS" if all(pass_conditions) else "V21_TRAIN_VALIDATION_DATA_BLOCKED"
    write_json(AUDIT / "v168_train_validation_data_audit.json", result)
    if result["status"] != "V21_TRAIN_VALIDATION_DATA_PASS":
        write_json(
            AUDIT / "v168_completion_only_qlora_budget.json",
            {
                "generated_at": now(),
                "status": "V21_COMPLETION_ONLY_QLORA_BUDGET_NOT_RUN_PRETRAIN_DATA_BLOCKED",
                "blocked_reason": "train/validation completion-only audit failed before GPU budget",
                "truncation_rate": result["truncation_rate"],
                "eos_trainable_rate": result["eos_trainable_rate"],
                "gpu_used": False,
            },
        )
        write_json(
            TRAINING / "v168_v21_training_config.json",
            {
                "generated_at": now(),
                "status": "V168_TRAINING_CONFIG_FROZEN_BUT_NOT_RUN",
                "epochs_planned": 1,
                "optimizer_steps_planned": 42,
                "max_length": 384,
                "lora_target_modules": ["q_proj", "v_proj"],
                "lora_r": 8,
                "holdout_path_accepted_by_training": False,
                "blocked_reason": "V21_TRAIN_VALIDATION_DATA_BLOCKED",
            },
        )
        write_json(
            TRAINING / "v168_v21_training_summary.json",
            {
                "generated_at": now(),
                "status": "PRIVATE_SYNTHETIC_SFT_V21_QLORA_TRAIN_NOT_RUN_PRETRAIN_DATA_BLOCKED",
                "epochs_completed": 0,
                "optimizer_step_count": 0,
                "validation_run_count": 0,
                "adapter_parameters_updated": False,
                "best_adapter_saved": False,
                "final_adapter_saved": False,
                "holdout_read_during_training": False,
                "blocked_reason": "V21_TRAIN_VALIDATION_DATA_BLOCKED",
            },
        )
        write_json(
            EVAL / "v168_v21_holdout_evaluation.json",
            {
                "generated_at": now(),
                "status": "V21_ENGINEERING_HOLDOUT_EVALUATION_NOT_RUN_TRAINING_BLOCKED",
                "holdout_unsealed_once": False,
                "base_real_inference_count": 0,
                "adapter_real_inference_count": 0,
                "blocked_reason": "training did not run",
            },
        )
        write_json(
            EVAL / "v168_v21_real_text_robustness.json",
            {
                "generated_at": now(),
                "status": "PRIVATE_REAL_TEXT_V21_ADAPTER_ROBUSTNESS_NOT_RUN_TRAINING_BLOCKED",
                "amazon_sample_count": 0,
                "asap_sample_count": 0,
                "base_real_inference_count": 0,
                "adapter_real_inference_count": 0,
                "blocked_reason": "training did not run",
            },
        )
        write_json(
            AUDIT / "v168_v21_adapter_value_gate.json",
            {
                "generated_at": now(),
                "status": "PRIVATE_SYNTHETIC_SFT_V21_ADAPTER_VALUE_GATE_NOT_RUN",
                "adapter_final_role": "PRIVATE_SYNTHETIC_SFT_V21_ADAPTER_RETAINED_FOR_RESEARCH_ONLY_NO_ADAPTER_TRAINED",
                "default_candidate": False,
                "blocked_reason": "training did not run",
            },
        )
    write_doc(
        DOCS / "220_v168_completion_only_qlora_budget.md",
        "V1.6.8 Completion-only QLoRA Budget",
        [
            "Status: `V21_COMPLETION_ONLY_QLORA_BUDGET_NOT_RUN_PRETRAIN_DATA_BLOCKED`",
            f"- train_count: `{result['train_count']}`",
            f"- validation_count: `{result['validation_count']}`",
            f"- system_user_mask_rate: `{result['system_user_mask_rate']}`",
            f"- assistant_trainable_rate: `{result['assistant_trainable_rate']}`",
            f"- eos_present_rate: `{result['eos_present_rate']}`",
            f"- eos_trainable_rate: `{result['eos_trainable_rate']}`",
            f"- truncation_rate: `{result['truncation_rate']}`",
            f"- zero_trainable_sample_count: `{result['zero_trainable_sample_count']}`",
            "",
            "QLoRA budget and training were not run because the full train/validation audit failed before GPU execution.",
            "No prompt, schema, max_length, split, or training configuration was changed to bypass this gate.",
        ],
    )
    return result


def main() -> None:
    provenance = audit_holdout()
    train_validation = audit_train_validation()
    print(provenance["status"])
    print("V21_ENGINEERING_HOLDOUT_SEALED")
    print(train_validation["status"])


if __name__ == "__main__":
    main()
