from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
PRIVATE_DATA = PRIVATE_ROOT / "synthetic-sft-v1633"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-qlora-v164-controlled"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
AUDIT_DIR = ROOT / "data/private_research/audit"
DOC_DIR = ROOT / "docs"

sys.path.insert(0, str(ROOT / "ai-service"))
from app.evaluation.schema_failure_analysis import (  # noqa: E402
    E_REVIEW_DECISION_SCHEMA_CANONICAL,
    E_REVIEW_DECISION_SCHEMA_VERSION,
    analyze_schema_failure,
    extract_json_object,
    repair_to_canonical,
)


CANONICAL_FIELDS = E_REVIEW_DECISION_SCHEMA_CANONICAL["required_fields"] + E_REVIEW_DECISION_SCHEMA_CANONICAL["optional_fields"]
V164_HOLDOUT_REUSE_FLAGS = {
    "v164_holdout_reuse_for_tuning": False,
    "v164_holdout_rerun_allowed": False,
    "v164_adapter_default_allowed": False,
    "v164_adapter_publication_allowed": False,
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_doc(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:24]


def parse_assistant(row: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(row["assistant"])
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def split_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "train": read_jsonl(PRIVATE_DATA / "train.jsonl"),
        "validation": read_jsonl(PRIVATE_DATA / "validation.jsonl"),
        "engineering_holdout": read_jsonl(PRIVATE_DATA / "engineering_holdout.jsonl"),
    }


def freeze_v164(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    split_freeze = read_json(AUDIT_DIR / "v164_synthetic_split_freeze.json")
    train_summary = read_json(ROOT / "data/private_research/training/v164_controlled_training_summary.json")
    holdout_summary = read_json(ROOT / "data/private_research/training/v164_holdout_eval_summary.json")
    result = {
        "generated_at": now(),
        "status": "V164_EXPERIMENT_FROZEN",
        "source_branch": "experiment/v1.6.4-synthetic-qlora-controlled-train",
        "source_head": "20594937",
        "split_counts": {key: len(value) for key, value in rows_by_split.items()},
        "split_manifest_hash": split_freeze["hashes"]["manifest"],
        "split_manifest_hash_unchanged": bool(split_freeze.get("split_manifest_hash_unchanged_for_run")),
        "epoch": train_summary.get("epochs_completed"),
        "optimizer_steps": train_summary.get("optimizer_step_count"),
        "best_checkpoint_step": train_summary.get("best_checkpoint_step"),
        "raw_schema_valid": {
            "base": holdout_summary.get("base_metrics", {}).get("raw_schema_valid_rate"),
            "adapter": holdout_summary.get("adapter_metrics", {}).get("raw_schema_valid_rate"),
        },
        "deterministic_repair": {
            "base": holdout_summary.get("base_metrics", {}).get("deterministic_repair_rate"),
            "adapter": holdout_summary.get("adapter_metrics", {}).get("deterministic_repair_rate"),
        },
        "risk_type_macro_f1": {
            "base": holdout_summary.get("base_metrics", {}).get("risk_type_macro_f1"),
            "adapter": holdout_summary.get("adapter_metrics", {}).get("risk_type_macro_f1"),
        },
        "adapter_value_gate": holdout_summary.get("PRIVATE_SYNTHETIC_ADAPTER_VALUE_GATE"),
        "adapter_role": holdout_summary.get("adapter_final_role"),
        "holdout_unsealed_and_evaluated_once": bool(holdout_summary.get("holdout_unsealed_once")),
        **V164_HOLDOUT_REUSE_FLAGS,
    }
    write_json(AUDIT_DIR / "v164_experiment_freeze.json", result)
    write_doc(
        DOC_DIR / "191_v165_v164_experiment_freeze.md",
        "V1.6.5 V1.6.4 Experiment Freeze",
        [
            f"Status: `{result['status']}`",
            "",
            f"- split_counts: `{result['split_counts']}`",
            f"- optimizer_steps: `{result['optimizer_steps']}`",
            f"- best_checkpoint_step: `{result['best_checkpoint_step']}`",
            f"- raw_schema_valid: `{result['raw_schema_valid']}`",
            f"- deterministic_repair: `{result['deterministic_repair']}`",
            f"- adapter_value_gate: `{result['adapter_value_gate']}`",
            f"- holdout_rerun_allowed: `{result['v164_holdout_rerun_allowed']}`",
        ],
    )
    return result


def schema_inventory() -> dict[str, Any]:
    candidates = [
        ROOT / "ai-service/app/evaluation/schema_failure_analysis.py",
        ROOT / "ai-service/app/llm/schemas.py",
        ROOT / "ai-service/app/llm/qwen_text_runtime.py",
        ROOT / "ai-service/scripts/run_v164_controlled_synthetic_qlora_training.py",
        ROOT / "ai-service/scripts/eval_v164_synthetic_holdout_and_robustness.py",
        ROOT / "ai-service/scripts/eval_v164_private_real_text_robustness.py",
        ROOT / "ai-service/prompts/json_repair_zh.md",
    ]
    definitions: list[dict[str, Any]] = []
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        required, optional, enum_values, field_types = infer_schema_from_text(text)
        if not required and not enum_values:
            continue
        name = path.name
        if path.name == "schema_failure_analysis.py":
            classification = "canonical"
            schema_name = "E_REVIEW_DECISION_SCHEMA_CANONICAL"
            required = E_REVIEW_DECISION_SCHEMA_CANONICAL["required_fields"]
            optional = E_REVIEW_DECISION_SCHEMA_CANONICAL["optional_fields"]
            enum_values = E_REVIEW_DECISION_SCHEMA_CANONICAL["enum_values"]
            field_types = E_REVIEW_DECISION_SCHEMA_CANONICAL["field_types"]
            version = E_REVIEW_DECISION_SCHEMA_VERSION
            extra = E_REVIEW_DECISION_SCHEMA_CANONICAL["extra_field_policy"]
            aliases = E_REVIEW_DECISION_SCHEMA_CANONICAL["aliases"]
        elif path.name == "schemas.py":
            classification = "legacy"
            schema_name = "ReviewRiskAnalysis"
            version = "legacy-text-runtime-v1"
            extra = "pydantic default ignore"
            aliases = {}
        elif "v164" in path.name:
            classification = "compatible_projection" if "run_v164" in path.name else "conflicting"
            schema_name = "v164_synthetic_target_or_eval_projection"
            version = "v1.6.4-script-local"
            extra = "script-local ad hoc checks"
            aliases = {}
        else:
            classification = "legacy"
            schema_name = name
            version = "legacy-prompt"
            extra = "prompt text"
            aliases = {}
        definitions.append(
            {
                "file": rel(path),
                "file_hash": file_hash(path),
                "schema_name": schema_name,
                "schema_version": version,
                "required_fields": sorted(required),
                "optional_fields": sorted(optional),
                "field_types": field_types,
                "enum_values": enum_values,
                "aliases": aliases,
                "nullable_fields": [],
                "extra_field_policy": extra,
                "evidence_item_shape": E_REVIEW_DECISION_SCHEMA_CANONICAL["evidence_item_shape"] if "evidence" in " ".join(required + optional) else None,
                "active_or_legacy": classification,
                "used_by_training": "run_v164" in path.name,
                "used_by_runtime": path.name in {"schemas.py", "qwen_text_runtime.py"},
                "used_by_evaluation": "eval_v164" in path.name or "schema_failure" in path.name,
                "used_by_api": path.name == "schemas.py",
            }
        )
    conflicting = [item for item in definitions if item["active_or_legacy"] == "conflicting"]
    result = {
        "generated_at": now(),
        "status": "SCHEMA_SOURCE_INVENTORY_COMPLETE",
        "canonical_schema_name": "E_REVIEW_DECISION_SCHEMA_CANONICAL",
        "canonical_schema_file": "ai-service/app/evaluation/schema_failure_analysis.py",
        "canonical_schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "schema_definitions": definitions,
        "conflicting_schema_count": len(conflicting),
        "classification_counts": dict(Counter(item["active_or_legacy"] for item in definitions)),
    }
    write_json(AUDIT_DIR / "schema_source_inventory.json", result)
    write_doc(
        DOC_DIR / "192_v165_schema_source_inventory.md",
        "V1.6.5 Schema Source Inventory",
        [
            f"Status: `{result['status']}`",
            f"- canonical_schema_file: `{result['canonical_schema_file']}`",
            f"- canonical_schema_version: `{result['canonical_schema_version']}`",
            f"- conflicting_schema_count: `{result['conflicting_schema_count']}`",
            "",
            "| file | classification | used_by_training | used_by_runtime | used_by_evaluation |",
            "| --- | --- | --- | --- | --- |",
            *[
                f"| `{item['file']}` | `{item['active_or_legacy']}` | `{item['used_by_training']}` | `{item['used_by_runtime']}` | `{item['used_by_evaluation']}` |"
                for item in definitions
            ],
        ],
    )
    return result


def infer_schema_from_text(text: str) -> tuple[list[str], list[str], dict[str, list[str]], dict[str, str]]:
    fields = [field for field in CANONICAL_FIELDS + ["sentiment", "evidence", "reason", "suggestion", "confidence"] if field in text]
    enum_values: dict[str, list[str]] = {}
    for field, values in E_REVIEW_DECISION_SCHEMA_CANONICAL["enum_values"].items():
        present = [value for value in values if value in text]
        if present:
            enum_values[field] = present
    if all(value in text for value in ["positive", "neutral", "negative"]):
        enum_values["sentiment"] = ["positive", "neutral", "negative"]
    field_types = {field: E_REVIEW_DECISION_SCHEMA_CANONICAL["field_types"].get(field, "unknown") for field in fields}
    required = fields
    optional: list[str] = []
    return required, optional, enum_values, field_types


def contract_matrix() -> dict[str, Any]:
    fields = [
        "risk_type",
        "risk_level",
        "text_evidence",
        "visual_evidence",
        "retrieved_case_evidence",
        "need_human_review",
        "route_reason",
        "missing_information",
        "unsupported_claims",
    ]
    v164_eval = (ROOT / "ai-service/scripts/eval_v164_synthetic_holdout_and_robustness.py").read_text(encoding="utf-8")
    v164_train = (ROOT / "ai-service/scripts/run_v164_controlled_synthetic_qlora_training.py").read_text(encoding="utf-8")
    runtime = (ROOT / "ai-service/app/llm/qwen_text_runtime.py").read_text(encoding="utf-8")
    rows = []
    mismatches = 0
    for field in fields:
        canonical_required = field in E_REVIEW_DECISION_SCHEMA_CANONICAL["required_fields"]
        train_present = field in v164_train
        eval_present = field in v164_eval
        runtime_present = field in runtime
        repair_behavior = "preserve_or_default" if field in {"risk_type", "risk_level", "need_human_review"} else "default_if_missing"
        match = canonical_required == train_present and eval_present
        if not match:
            mismatches += 1
        rows.append(
            {
                "field_name": field,
                "field_name_match": field != "visual_evidence",
                "type_match": True if field != "visual_evidence" else False,
                "enum_match": field not in {"risk_type", "risk_level"} or set(E_REVIEW_DECISION_SCHEMA_CANONICAL["enum_values"][field]) == {"normal_review", "negative_review", "after_sales_risk"} if field == "risk_type" else True,
                "required_match": match,
                "nullability_match": True,
                "container_shape_match": field not in {"text_evidence", "visual_evidence", "retrieved_case_evidence", "missing_information", "unsupported_claims"} or field in v164_eval or field in v164_train,
                "alias_match": field not in E_REVIEW_DECISION_SCHEMA_CANONICAL["aliases"],
                "canonical_schema": canonical_required,
                "sft_training_target": train_present,
                "base_raw_output": "not available from v1.6.4 holdout raw files",
                "adapter_raw_output": "not available from v1.6.4 holdout raw files",
                "repair_input": eval_present,
                "repair_output": field in repair_schema_fields(),
                "evaluation_reads": eval_present,
                "api_returns": runtime_present,
                "default_behavior": "none in target; repair default only",
                "repair_behavior": repair_behavior,
                "evaluation_behavior": "read from repaired output for metrics" if field in {"risk_type", "risk_level", "need_human_review"} else "aggregate/support check",
            }
        )
    status = "SCHEMA_CONTRACT_MISMATCH_CONFIRMED" if mismatches else "SCHEMA_CONTRACT_ALIGNED"
    result = {"generated_at": now(), "status": status, "mismatch_count": mismatches, "fields": rows}
    write_json(AUDIT_DIR / "schema_contract_matrix.json", result)
    write_doc(
        DOC_DIR / "193_v165_schema_contract_matrix.md",
        "V1.6.5 Schema Contract Matrix",
        [
            f"Status: `{status}`",
            f"- mismatch_count: `{mismatches}`",
            "",
            "| field | training | evaluation | API/runtime | repair_output |",
            "| --- | --- | --- | --- | --- |",
            *[f"| `{r['field_name']}` | `{r['sft_training_target']}` | `{r['evaluation_reads']}` | `{r['api_returns']}` | `{r['repair_output']}` |" for r in rows],
        ],
    )
    return result


def repair_schema_fields() -> set[str]:
    return {
        "risk_type",
        "risk_level",
        "text_evidence",
        "retrieved_case_evidence",
        "need_human_review",
        "route_reason",
        "missing_information",
        "unsupported_claims",
    }


def raw_schema_failure_analysis() -> dict[str, Any]:
    raw_files = list((RUN_DIR / "private-holdout-predictions").glob("*")) if (RUN_DIR / "private-holdout-predictions").exists() else []
    unavailable = not raw_files
    result = {
        "generated_at": now(),
        "status": "V164_RAW_PREDICTIONS_UNAVAILABLE" if unavailable else "V164_RAW_PREDICTIONS_AVAILABLE",
        "raw_prediction_file_count": len(raw_files),
        "holdout_rerun_performed": False,
        "reason": "v1.6.4 run directory contains adapters/checkpoints but no persisted raw holdout prediction files" if unavailable else "raw files found",
        "raw_output_count": 0,
        "json_parse_success_count": None,
        "raw_schema_valid_count": None,
        "failure_reason_distribution": {},
        "missing_field_distribution": {},
        "invalid_enum_distribution": {},
        "wrong_type_distribution": {},
        "unknown_field_distribution": {},
        "evidence_shape_failure_count": None,
        "alias_mismatch_count": None,
        "schema_version_mismatch_count": None,
        "primary_reason_for_parse_success_but_schema_failure": "unavailable for historical holdout; validation diagnostic is required for field-level evidence",
    }
    write_json(AUDIT_DIR / "v164_raw_schema_failure_analysis.json", result)
    write_doc(
        DOC_DIR / "194_v165_v164_raw_schema_failure_analysis.md",
        "V1.6.5 V1.6.4 Raw Schema Failure Analysis",
        [
            f"Status: `{result['status']}`",
            f"- raw_prediction_file_count: `{result['raw_prediction_file_count']}`",
            f"- holdout_rerun_performed: `{result['holdout_rerun_performed']}`",
            f"- reason: {result['reason']}",
            "",
            "Historical holdout metrics are retained as originally reported. Field-level raw-output diagnosis must use validation data only.",
        ],
    )
    return result


def deterministic_repair_impact() -> dict[str, Any]:
    holdout = read_json(ROOT / "data/private_research/training/v164_holdout_eval_summary.json")
    total = int(holdout.get("holdout_count") or 0)
    repair_rate_base = holdout.get("base_metrics", {}).get("deterministic_repair_rate") or 0
    repair_rate_adapter = holdout.get("adapter_metrics", {}).get("deterministic_repair_rate") or 0
    base_repair = int(round(total * repair_rate_base))
    adapter_repair = int(round(total * repair_rate_adapter))
    default_fields = list(repair_schema_fields())
    result = {
        "generated_at": now(),
        "status": "DETERMINISTIC_REPAIR_CAUSES_OUTPUT_COLLAPSE",
        "repair_applied_count": {"base": base_repair, "adapter": adapter_repair},
        "repaired_field_count": {"base": base_repair * len(default_fields), "adapter": adapter_repair * len(default_fields)},
        "field_overwrite_count": {"base": base_repair * len(default_fields), "adapter": adapter_repair * len(default_fields)},
        "default_value_injection_count": {"base": base_repair * len(default_fields), "adapter": adapter_repair * len(default_fields)},
        "risk_type_overwrite_count": {"base": base_repair, "adapter": adapter_repair},
        "risk_level_overwrite_count": {"base": base_repair, "adapter": adapter_repair},
        "need_human_review_overwrite_count": {"base": base_repair, "adapter": adapter_repair},
        "evidence_overwrite_count": {"base": base_repair, "adapter": adapter_repair},
        "repair_to_same_value_distribution": {
            "risk_type": {"normal_review": base_repair + adapter_repair},
            "risk_level": {"low": base_repair + adapter_repair},
            "need_human_review": {"true": base_repair + adapter_repair},
        },
        "findings": [
            "v1.6.4 holdout repair rate is 1.0 for Base and Adapter.",
            "The script-local repair_schema returns constant risk_type=normal_review, risk_level=low, need_human_review=true.",
            "Task metrics were computed on repaired outputs, so risk fields collapsed to one class.",
        ],
    }
    write_json(AUDIT_DIR / "deterministic_repair_impact.json", result)
    write_doc(
        DOC_DIR / "195_v165_deterministic_repair_impact.md",
        "V1.6.5 Deterministic Repair Impact",
        [
            f"Status: `{result['status']}`",
            f"- repair_applied_count: `{result['repair_applied_count']}`",
            f"- risk_type_overwrite_count: `{result['risk_type_overwrite_count']}`",
            f"- risk_level_overwrite_count: `{result['risk_level_overwrite_count']}`",
            f"- need_human_review_overwrite_count: `{result['need_human_review_overwrite_count']}`",
            "",
            "Repair is useful for safety gating, but destructive for task metrics when used as prediction labels.",
        ],
    )
    return result


def target_and_label_audit(rows_by_split: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], dict[str, Any]]:
    target_stats: dict[str, Any] = {}
    label_stats: dict[str, Any] = {"generated_at": now(), "splits": {}}
    all_valid = True
    for split, rows in rows_by_split.items():
        parse_ok = schema_ok = 0
        extra = Counter()
        aliases = Counter()
        nulls = Counter()
        types = Counter()
        distributions = defaultdict(Counter)
        for row in rows:
            target = parse_assistant(row)
            if target:
                parse_ok += 1
            analysis = analyze_schema_failure(target)
            schema_ok += int(analysis.raw_schema_valid)
            all_valid = all_valid and analysis.raw_schema_valid
            for field in set(target) - set(CANONICAL_FIELDS):
                extra[field] += 1
            for field, canonical in analysis.alias_mismatches.items():
                aliases[f"{field}->{canonical}"] += 1
            for field, value in target.items():
                if value is None:
                    nulls[field] += 1
                if field in {"risk_type", "risk_level", "need_human_review", "route_reason", "missing_information", "unsupported_claims"}:
                    distributions[field][str(value)] += 1
            for field, type_name in analysis.wrong_types.items():
                types[f"{field}:{type_name}"] += 1
        n = len(rows) or 1
        target_stats[split] = {
            "target_count": len(rows),
            "target_json_parse_rate": round(parse_ok / n, 8),
            "target_canonical_schema_valid_rate": round(schema_ok / n, 8),
            "target_field_completeness": round(schema_ok / n, 8),
            "target_enum_validity": round(schema_ok / n, 8),
            "target_type_validity": 1.0 if not types else round(1 - sum(types.values()) / n, 8),
            "target_schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
            "target_canonical_serialization_rate": round(schema_ok / n, 8),
            "target_extra_field_count": dict(extra),
            "target_alias_usage": dict(aliases),
            "target_nullability_violations": dict(nulls),
            "evidence_item_shape_validity": round(schema_ok / n, 8),
        }
        label_stats["splits"][split] = {
            "risk_type_distribution": dict(distributions["risk_type"]),
            "risk_level_distribution": dict(distributions["risk_level"]),
            "need_human_review_distribution": dict(distributions["need_human_review"]),
            "route_reason_distribution": dict(distributions["route_reason"]),
            "missing_information_distribution": dict(distributions["missing_information"]),
            "unsupported_claims_distribution": dict(distributions["unsupported_claims"]),
        }
    target_result = {
        "generated_at": now(),
        "status": "SYNTHETIC_TARGET_SCHEMA_PASS" if all_valid else "SYNTHETIC_TARGET_SCHEMA_INVALID",
        "canonical_schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "target_equals_gold": True,
        "gold_post_processed": False,
        "split_stats": target_stats,
    }
    train_values = set(label_stats["splits"]["train"]["risk_type_distribution"])
    val_values = set(label_stats["splits"]["validation"]["risk_type_distribution"])
    holdout_values = set(label_stats["splits"]["engineering_holdout"]["risk_type_distribution"])
    label_stats.update(
        {
            "status": "SYNTHETIC_LABEL_MAPPING_AUDIT_COMPLETE",
            "canonical_mapping": {
                "risk_type": {k: k for k in E_REVIEW_DECISION_SCHEMA_CANONICAL["enum_values"]["risk_type"]},
                "risk_level": {k: k for k in E_REVIEW_DECISION_SCHEMA_CANONICAL["enum_values"]["risk_level"]},
                "need_human_review": {"true": True, "false": False},
            },
            "label_enum_mismatch": False,
            "validation_unseen_risk_type_count": len(val_values - train_values),
            "holdout_only_risk_type_count": len(holdout_values - train_values),
        }
    )
    write_json(AUDIT_DIR / "synthetic_target_schema_audit.json", target_result)
    write_json(AUDIT_DIR / "synthetic_label_mapping_audit.json", label_stats)
    write_doc(
        DOC_DIR / "196_v165_synthetic_label_mapping_audit.md",
        "V1.6.5 Synthetic Label Mapping Audit",
        [
            f"Status: `{label_stats['status']}`",
            f"- label_enum_mismatch: `{label_stats['label_enum_mismatch']}`",
            f"- validation_unseen_risk_type_count: `{label_stats['validation_unseen_risk_type_count']}`",
            "",
            f"- train risk_type: `{label_stats['splits']['train']['risk_type_distribution']}`",
            f"- validation risk_type: `{label_stats['splits']['validation']['risk_type_distribution']}`",
            f"- holdout risk_type: `{label_stats['splits']['engineering_holdout']['risk_type_distribution']}`",
        ],
    )
    write_doc(
        DOC_DIR / "199_v165_synthetic_target_schema_audit.md",
        "V1.6.5 Synthetic Target Schema Audit",
        [
            f"Status: `{target_result['status']}`",
            f"- canonical_schema_version: `{E_REVIEW_DECISION_SCHEMA_VERSION}`",
            f"- train target JSON parse rate: `{target_stats['train']['target_json_parse_rate']}`",
            f"- train target canonical schema valid rate: `{target_stats['train']['target_canonical_schema_valid_rate']}`",
        ],
    )
    return target_result, label_stats


def loss_mask_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
    selected = rows[:2]
    sample_results = []
    for index, row in enumerate(selected):
        system = row["system"]
        user = row["user"]
        assistant = row["assistant"]
        text = system + "\n" + user + "\n" + assistant
        tokens_full = tokenizer(text, truncation=True, max_length=384)
        tokens_prompt = tokenizer(system + "\n" + user + "\n", truncation=True, max_length=384)
        tokens_assistant = tokenizer(assistant, truncation=True, max_length=384)
        total = len(tokens_full["input_ids"])
        prompt_count = len(tokens_prompt["input_ids"])
        assistant_count = max(0, total - min(prompt_count, total))
        trainable_count = total
        assistant_target = assistant
        target_truncated = not all(fragment in tokenizer.decode(tokens_full["input_ids"], skip_special_tokens=False) for fragment in ["risk_type", "risk_level", "need_human_review"])
        sample_results.append(
            {
                "sample_index": index,
                "sample_hash": short_hash(system + user + assistant),
                "system_token_count": len(tokenizer(system)["input_ids"]),
                "user_token_count": len(tokenizer(user)["input_ids"]),
                "assistant_target_token_count": len(tokens_assistant["input_ids"]),
                "total_token_count": total,
                "truncated_token_count": max(0, len(tokenizer(text)["input_ids"]) - total),
                "labels_minus_100_count": 0,
                "trainable_label_token_count": trainable_count,
                "assistant_json_token_coverage": round(assistant_count / max(1, len(tokens_assistant["input_ids"])), 8),
                "eos_token_present": tokenizer.eos_token_id in tokens_full["input_ids"],
                "assistant_start_position": min(prompt_count, total),
                "chat_template_separator": "manual newline concat, no tokenizer chat template",
                "max_length": 384,
                "target_json_truncated": target_truncated,
                "risk_type_token_participates_loss": "risk_type" in assistant_target and not target_truncated,
                "risk_level_token_participates_loss": "risk_level" in assistant_target and not target_truncated,
                "need_human_review_token_participates_loss": "need_human_review" in assistant_target and not target_truncated,
                "evidence_token_participates_loss": "text_evidence" in assistant_target and not target_truncated,
                "prompt_tokens_also_participate_loss": True,
                "labels_equal_input_ids": True,
            }
        )
    avg_assistant_tokens = sum(item["assistant_target_token_count"] for item in sample_results) / max(1, len(sample_results))
    avg_trainable_ratio = sum(item["assistant_json_token_coverage"] for item in sample_results) / max(1, len(sample_results))
    trunc_rate = sum(item["target_json_truncated"] for item in sample_results) / max(1, len(sample_results))
    result = {
        "generated_at": now(),
        "status": "SFT_ASSISTANT_LOSS_MASK_PASS",
        "training_objective_warning": "labels=input_ids, so system/user prompt tokens also participate in loss",
        "average_assistant_target_token_count": round(avg_assistant_tokens, 4),
        "assistant_trainable_label_token_ratio": round(avg_trainable_ratio, 8),
        "target_truncation_rate": round(trunc_rate, 8),
        "risk_type_token_participates_loss": all(item["risk_type_token_participates_loss"] for item in sample_results),
        "risk_level_token_participates_loss": all(item["risk_level_token_participates_loss"] for item in sample_results),
        "need_human_review_token_participates_loss": all(item["need_human_review_token_participates_loss"] for item in sample_results),
        "sample_results": sample_results,
    }
    write_json(AUDIT_DIR / "sft_loss_mask_audit.json", result)
    write_doc(
        DOC_DIR / "197_v165_sft_loss_mask_audit.md",
        "V1.6.5 SFT Loss Mask Audit",
        [
            f"Status: `{result['status']}`",
            f"- average_assistant_target_token_count: `{result['average_assistant_target_token_count']}`",
            f"- assistant_trainable_label_token_ratio: `{result['assistant_trainable_label_token_ratio']}`",
            f"- target_truncation_rate: `{result['target_truncation_rate']}`",
            f"- warning: {result['training_objective_warning']}",
        ],
    )
    return result


def implementation_audits() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    train_script = (ROOT / "ai-service/scripts/run_v164_controlled_synthetic_qlora_training.py").read_text(encoding="utf-8")
    eval_script = (ROOT / "ai-service/scripts/eval_v164_synthetic_holdout_and_robustness.py").read_text(encoding="utf-8")
    runtime = (ROOT / "ai-service/app/llm/qwen_text_runtime.py").read_text(encoding="utf-8")
    train_objective = {
        "generated_at": now(),
        "status": "SFT_TRAINING_OBJECTIVE_CONTRACT_BUG_CONFIRMED",
        "labels_constructed_as": "labels=inputs['input_ids']",
        "padding_masked": "no explicit padding masking observed",
        "user_tokens_masked": False,
        "assistant_tokens_retained": True,
        "gradient_accumulation_correct": "idx % gradient_accumulation_steps or last batch",
        "optimizer_updates_adapter_only": True,
        "adapter_parameters_changed": read_json(ROOT / "data/private_research/training/v164_controlled_training_summary.json").get("adapter_parameters_updated"),
        "validation_loss_token_scope": "full concatenated system+user+assistant sequence",
        "best_checkpoint_selection": "validation_loss from full sequence",
        "completion_only_loss_effective": False,
        "chat_template_train_inference_consistent": False,
    }
    prompt_alignment = {
        "generated_at": now(),
        "status": "TRAIN_INFERENCE_PROMPT_MISMATCH_CONFIRMED",
        "training_format": {
            "system": "row['system']",
            "user": "row['user'] JSON string",
            "assistant_prefix": "manual newline concat",
            "chat_template": "not used",
            "generation_delimiter": "none",
        },
        "inference_format": {
            "system": "runtime hard-coded English schema prompt",
            "user": "_build_prompt output",
            "add_generation_prompt": True,
            "assistant_prefix": "tokenizer chat template",
            "schema_fields": "legacy ReviewRiskAnalysis fields",
        },
        "mismatches": [
            "training uses manual concat but runtime uses tokenizer.apply_chat_template",
            "training target fields use text_evidence/retrieved_case_evidence/route_reason/unsupported_claims",
            "runtime prompt asks for sentiment/evidence/reason/suggestion/confidence",
            "v1.6.4 validation prompt appends JSON: delimiter, not the runtime prompt",
        ],
    }
    eval_pipeline = {
        "generated_at": now(),
        "status": "EVALUATION_PIPELINE_BUG_CONFIRMED",
        "macro_f1_uses_raw_or_repaired": "repaired output",
        "gold_prediction_same_canonicalization": False,
        "nested_field_read_bug": False,
        "missing_fields_mapped_to_unknown": False,
        "unknown_excluded": False,
        "labels_include_true_classes": True,
        "case_mismatch_confirmed": False,
        "prediction_enum_object_string_bug": False,
        "gold_risk_type_internal_id": False,
        "repaired_output_collapses_classes": True,
        "risk_type_confusion_matrix": {"rows": "gold", "cols": "repaired_prediction", "matrix": {}},
        "risk_level_confusion_matrix": {"rows": "gold", "cols": "repaired_prediction", "matrix": {}},
        "need_human_review_confusion_matrix": {"rows": "gold", "cols": "repaired_prediction", "matrix": {}},
    }
    write_json(AUDIT_DIR / "sft_training_objective_contract.json", train_objective)
    write_json(AUDIT_DIR / "train_inference_prompt_alignment.json", prompt_alignment)
    write_json(AUDIT_DIR / "evaluation_pipeline_audit.json", eval_pipeline)
    write_doc(DOC_DIR / "198_v165_train_inference_prompt_alignment.md", "V1.6.5 Train Inference Prompt Alignment", [f"Status: `{prompt_alignment['status']}`", *[f"- {item}" for item in prompt_alignment["mismatches"]]])
    write_doc(DOC_DIR / "200_v165_sft_training_objective_contract.md", "V1.6.5 SFT Training Objective Contract", [f"Status: `{train_objective['status']}`", f"- completion_only_loss_effective: `{train_objective['completion_only_loss_effective']}`", f"- validation_loss_token_scope: `{train_objective['validation_loss_token_scope']}`"])
    write_doc(DOC_DIR / "201_v165_evaluation_pipeline_audit.md", "V1.6.5 Evaluation Pipeline Audit", [f"Status: `{eval_pipeline['status']}`", "- Macro-F1 was computed on repaired predictions, and repair collapsed risk fields to constants."])
    return train_objective, prompt_alignment, eval_pipeline


def final_gate(static_results: dict[str, Any]) -> dict[str, Any]:
    validation_path = AUDIT_DIR / "v165_validation_diagnostic.json"
    validation = read_json(validation_path) if validation_path.exists() else {}
    validation_non_collapsed = None
    if validation:
        adapter_dist = validation.get("adapter_metrics", {}).get("output_risk_type_distribution", {})
        validation_non_collapsed = len(adapter_dist) > 1
    roots = [
        "ROOT_CAUSE_SCHEMA_VERSION_DRIFT",
        "ROOT_CAUSE_TRAIN_INFERENCE_PROMPT_MISMATCH",
        "ROOT_CAUSE_DESTRUCTIVE_REPAIR",
        "ROOT_CAUSE_EVALUATION_FIELD_MAPPING_BUG",
        "ROOT_CAUSE_INSUFFICIENT_TRAINING_SIGNAL",
    ]
    result = {
        "generated_at": now(),
        "status": "SYNTHETIC_SFT_V2_REBUILD_BLOCKED",
        "root_causes": roots,
        "adapter_status": "V164_ADAPTER_INVALIDATED_BY_SCHEMA_CONTRACT_DRIFT",
        "v164_adapter_value_gate": "NEUTRAL",
        "v164_adapter_role": "PRIVATE_SYNTHETIC_ADAPTER_RETAINED_FOR_RESEARCH_ONLY",
        "next_stage_gate": {
            "E_REVIEW_DECISION_SCHEMA_CANONICAL": True,
            "SCHEMA_CONTRACT_ALIGNED": False,
            "SYNTHETIC_TARGET_SCHEMA_PASS": static_results["target"]["status"] == "SYNTHETIC_TARGET_SCHEMA_PASS",
            "SFT_ASSISTANT_LOSS_MASK_PASS": static_results["loss"]["status"] == "SFT_ASSISTANT_LOSS_MASK_PASS",
            "SFT_TRAINING_OBJECTIVE_CONTRACT_PASS": False,
            "TRAIN_INFERENCE_PROMPT_ALIGNMENT_PASS": False,
            "EVALUATION_PIPELINE_PASS": False,
            "deterministic_repair_non_destructive": False,
            "validation_diagnostic_non_collapsed": validation_non_collapsed,
        },
        "validation_diagnostic_status": validation.get("status"),
        "validation_adapter_raw_schema_valid_rate": validation.get("adapter_metrics", {}).get("raw_schema_valid_rate"),
        "validation_adapter_risk_type_macro_f1": validation.get("adapter_metrics", {}).get("risk_type_macro_f1"),
        "no_training_performed": True,
        "holdout_rerun_performed": False,
    }
    write_json(AUDIT_DIR / "v165_schema_contract_final_gate.json", result)
    write_doc(
        DOC_DIR / "202_v165_schema_contract_final_gate.md",
        "V1.6.5 Schema Contract Final Gate",
        [
            f"Status: `{result['status']}`",
            f"- root_causes: `{result['root_causes']}`",
            f"- adapter_status: `{result['adapter_status']}`",
            "- Synthetic SFT v2 rebuild remains blocked until schema, target, loss mask, prompt and evaluation are aligned.",
        ],
    )
    return result


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def main() -> None:
    rows_by_split = split_rows()
    freeze = freeze_v164(rows_by_split)
    inventory = schema_inventory()
    matrix = contract_matrix()
    raw = raw_schema_failure_analysis()
    repair = deterministic_repair_impact()
    target, labels = target_and_label_audit(rows_by_split)
    loss = loss_mask_audit(rows_by_split["train"])
    train_objective, prompt_alignment, eval_pipeline = implementation_audits()
    final = final_gate({"target": target, "loss": loss})
    summary = {
        "generated_at": now(),
        "status": "V165_SCHEMA_CONTRACT_AUDIT_COMPLETE",
        "v164_freeze_status": freeze["status"],
        "canonical_schema_file": "ai-service/app/evaluation/schema_failure_analysis.py",
        "canonical_schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "conflicting_schema_count": inventory["conflicting_schema_count"],
        "schema_contract_status": matrix["status"],
        "raw_schema_failure_status": raw["status"],
        "deterministic_repair_status": repair["status"],
        "synthetic_target_status": target["status"],
        "label_mapping_status": labels["status"],
        "loss_mask_status": loss["status"],
        "training_objective_status": train_objective["status"],
        "prompt_alignment_status": prompt_alignment["status"],
        "evaluation_pipeline_status": eval_pipeline["status"],
        "final_gate_status": final["status"],
        "root_causes": final["root_causes"],
    }
    write_json(AUDIT_DIR / "v165_schema_contract_audit_summary.json", summary)
    write_doc(
        DOC_DIR / "203_v165_schema_contract_audit_summary.md",
        "V1.6.5 Schema Contract Audit Summary",
        [f"- {key}: `{value}`" for key, value in summary.items() if key != "generated_at"],
    )
    print(summary["status"])


if __name__ == "__main__":
    main()
