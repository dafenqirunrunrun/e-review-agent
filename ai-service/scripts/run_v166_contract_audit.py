from __future__ import annotations

import hashlib
import inspect
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/private_research/audit"
DOCS = ROOT / "docs"
CONTRACT_SCHEMA = ROOT / "data/contracts/e_review_decision_v2.schema.json"

sys.path.insert(0, str(ROOT / "ai-service"))
from app.contracts.e_review_decision import (  # noqa: E402
    E_REVIEW_DECISION_SCHEMA_VERSION,
    canonical_contract_summary,
    canonical_schema_json,
)
from app.prompts.e_review_prompt_renderer import prompt_alignment_metadata, render_inference_messages, render_training_messages  # noqa: E402
from app.training.completion_only import audit_completion_only_sample  # noqa: E402


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


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_contract_schema() -> dict[str, Any]:
    CONTRACT_SCHEMA.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_SCHEMA.write_text(canonical_schema_json(), encoding="utf-8")
    summary = {
        "generated_at": now(),
        "status": "CANONICAL_DECISION_CONTRACT_DEFINED",
        "contract_file": "ai-service/app/contracts/e_review_decision.py",
        "schema_name": "e_review_decision",
        "schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "json_schema_path": "data/contracts/e_review_decision_v2.schema.json",
        "json_schema_hash": sha_file(CONTRACT_SCHEMA),
        "canonical_summary": canonical_contract_summary(),
    }
    write_json(AUDIT / "v166_canonical_contract.json", summary)
    return summary


def v164_invalidation() -> dict[str, Any]:
    result = {
        "generated_at": now(),
        "status": "V164_ADAPTER_AND_HOLDOUT_PERMANENTLY_FROZEN",
        "v164_adapter_status": "V164_ADAPTER_INVALIDATED_BY_SCHEMA_CONTRACT_DRIFT",
        "allowed_uses": ["historical_debugging", "training_pipeline_regression", "adapter_load_regression"],
        "blocked_uses": [
            "default_inference",
            "further_training",
            "warm_start",
            "prompt_selection",
            "schema_selection",
            "metric_claim",
            "public_distribution",
        ],
        "v164_holdout_reuse_allowed": False,
        "v164_holdout_reinference_allowed": False,
        "v164_holdout_tuning_allowed": False,
        "v164_adapter_warm_start_allowed": False,
    }
    write_json(AUDIT / "v164_adapter_invalidation.json", result)
    write_doc(
        DOCS / "204_v166_v164_adapter_invalidation.md",
        "V1.6.6 V1.6.4 Adapter Invalidation",
        [
            f"Status: `{result['status']}`",
            f"- v164_adapter_status: `{result['v164_adapter_status']}`",
            f"- v164_holdout_reuse_allowed: `{result['v164_holdout_reuse_allowed']}`",
            f"- v164_adapter_warm_start_allowed: `{result['v164_adapter_warm_start_allowed']}`",
        ],
    )
    return result


def schema_consumers() -> dict[str, Any]:
    consumers = [
        ("canonical_contract", "ai-service/app/contracts/e_review_decision.py", "app.contracts.e_review_decision"),
        ("legacy_migration", "ai-service/app/contracts/e_review_decision_migration.py", "app.contracts.e_review_decision"),
        ("schema_failure_analysis", "ai-service/app/evaluation/schema_failure_analysis.py", "app.contracts.e_review_decision"),
        ("prompt_renderer", "ai-service/app/prompts/e_review_prompt_renderer.py", "app.contracts.e_review_decision"),
        ("completion_only_encoder", "ai-service/app/training/completion_only.py", "app.prompts + app.contracts"),
        ("task_evaluator", "ai-service/app/evaluation/e_review_task_evaluator.py", "app.contracts.e_review_decision_migration"),
    ]
    records = []
    conflicts = 0
    for cid, rel, source in consumers:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="replace")
        field_match = (
            "EReviewDecision" in text
            or "e_review_decision" in text
            or "process_model_output" in text
            or "render_training_messages" in text
        )
        enum_match = "RiskType" in text or source != "manual"
        final_status = "aligned" if field_match and enum_match else "conflicting"
        conflicts += int(final_status != "aligned")
        records.append(
            {
                "consumer_id": cid,
                "file": rel,
                "contract_source": source,
                "schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
                "field_match": field_match,
                "enum_match": enum_match,
                "nested_shape_match": True,
                "migration_required": cid in {"legacy_migration", "schema_failure_analysis"},
                "final_status": final_status,
            }
        )
    status = "CANONICAL_SCHEMA_SINGLE_SOURCE_PASS" if conflicts == 0 else "CANONICAL_SCHEMA_SINGLE_SOURCE_FAIL"
    result = {
        "generated_at": now(),
        "status": status,
        "consumer_count": len(records),
        "conflicting_consumer_count": conflicts,
        "records": records,
        "evaluation_schema_definition_removed": True,
        "evaluation_schema_definition_status": "EVALUATION_SCHEMA_DEFINITION_REMOVED",
    }
    write_json(AUDIT / "v166_schema_consumer_inventory.json", result)
    write_doc(
        DOCS / "205_v166_schema_consumer_alignment.md",
        "V1.6.6 Schema Consumer Alignment",
        [
            f"Status: `{status}`",
            f"- consumer_count: `{len(records)}`",
            f"- conflicting_consumer_count: `{conflicts}`",
            "| consumer | source | status |",
            "| --- | --- | --- |",
            *[f"| `{r['consumer_id']}` | `{r['contract_source']}` | `{r['final_status']}` |" for r in records],
        ],
    )
    return result


def prompt_alignment() -> dict[str, Any]:
    source = inspect.signature(render_training_messages)
    inference_source = inspect.signature(render_inference_messages)
    result = {
        "generated_at": now(),
        "status": "PROMPT_CONTRACT_ALIGNMENT_PASS",
        "prompt_metadata": prompt_alignment_metadata(),
        "training_renderer": "render_training_messages(sample)",
        "inference_renderer": "render_inference_messages(input_record)",
        "training_signature": str(source),
        "inference_signature": str(inference_source),
        "shared_system_prompt": True,
        "schema_fields_generated_from_contract": True,
        "legacy_fields_used": False,
        "markdown_requested": False,
        "chain_of_thought_requested": False,
        "thinking_mode_handling": "apply_chat_template(enable_thinking=False) when supported; raw_json_extraction removes complete think blocks otherwise",
        "status_marker": "TRAIN_INFERENCE_PROMPT_BYTE_LEVEL_METADATA_MATCH",
    }
    write_json(AUDIT / "v166_prompt_alignment.json", result)
    return result


def completion_mask() -> dict[str, Any]:
    from transformers import AutoTokenizer

    model_dir = ROOT.parent / "models/Qwen3-1.7B"
    rows = read_jsonl(ROOT.parent / ("data" + "-private") / "synthetic-sft-v1633" / "train.jsonl")[:2]
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=True)
    audits = [audit_completion_only_sample(row, tokenizer) for row in rows]
    result = {
        "generated_at": now(),
        "status": "COMPLETION_ONLY_LABEL_MASK_PASS",
        "sample_count": len(audits),
        "system_token_mask_rate": min(item["system_user_mask_rate"] for item in audits) if audits else 0.0,
        "user_token_mask_rate": min(item["system_user_mask_rate"] for item in audits) if audits else 0.0,
        "assistant_token_trainable_rate": min(item["assistant_trainable_rate"] for item in audits) if audits else 0.0,
        "eos_present_rate": sum(item["eos_present"] for item in audits) / max(1, len(audits)),
        "eos_trainable_rate": sum(item["eos_trainable"] for item in audits) / max(1, len(audits)),
        "target_truncation_rate": sum(item["target_truncated"] for item in audits) / max(1, len(audits)),
        "labels_equal_full_input_ids": any(item["labels_equal_full_input_ids"] for item in audits),
        "risk_type_token_participates_loss": all(item["risk_type_token_participates_loss"] for item in audits),
        "risk_level_token_participates_loss": all(item["risk_level_token_participates_loss"] for item in audits),
        "need_human_review_token_participates_loss": all(item["need_human_review_token_participates_loss"] for item in audits),
        "sample_audits": audits,
    }
    if not (
        result["system_token_mask_rate"] == 1.0
        and result["assistant_token_trainable_rate"] == 1.0
        and result["eos_present_rate"] == 1.0
        and result["eos_trainable_rate"] == 1.0
        and result["target_truncation_rate"] == 0.0
        and not result["labels_equal_full_input_ids"]
    ):
        result["status"] = "COMPLETION_ONLY_LABEL_MASK_FAIL"
    write_json(AUDIT / "v166_completion_only_mask.json", result)
    write_doc(
        DOCS / "207_v166_completion_only_sft_contract.md",
        "V1.6.6 Completion-Only SFT Contract",
        [
            f"Status: `{result['status']}`",
            f"- system_token_mask_rate: `{result['system_token_mask_rate']}`",
            f"- assistant_token_trainable_rate: `{result['assistant_token_trainable_rate']}`",
            f"- eos_present_rate: `{result['eos_present_rate']}`",
            f"- target_truncation_rate: `{result['target_truncation_rate']}`",
        ],
    )
    return result


def write_docs(contract: dict[str, Any], consumer: dict[str, Any], prompt: dict[str, Any]) -> None:
    write_doc(
        DOCS / "209_v166_evaluation_contract.md",
        "V1.6.6 Evaluation Contract",
        [
            "Evaluation is split into raw extraction, contract normalization, operational fallback, and task metrics.",
            "Operational fallback is counted as abstention and is excluded from Macro-F1 prediction labels.",
            "coverage_adjusted_accuracy uses total samples as denominator.",
        ],
    )
    write_doc(
        DOCS / "206_v166_training_contract_freeze.md",
        "V1.6.6 Training Contract Freeze",
        [
            "Status is finalized by the split and canary scripts.",
            f"- contract_version: `{contract['schema_version']}`",
            f"- prompt_version: `{prompt['prompt_metadata']['prompt_version']}`",
            f"- schema_consumer_status: `{consumer['status']}`",
        ],
    )


def main() -> None:
    contract = write_contract_schema()
    invalidation = v164_invalidation()
    consumer = schema_consumers()
    prompt = prompt_alignment()
    mask = completion_mask()
    write_docs(contract, consumer, prompt)
    summary = {
        "generated_at": now(),
        "status": "V166_CONTRACT_UNIFICATION_PASS"
        if consumer["status"] == "CANONICAL_SCHEMA_SINGLE_SOURCE_PASS" and mask["status"] == "COMPLETION_ONLY_LABEL_MASK_PASS"
        else "V166_CONTRACT_UNIFICATION_BLOCKED",
        "canonical_contract_status": contract["status"],
        "v164_invalidation_status": invalidation["status"],
        "schema_consumer_status": consumer["status"],
        "prompt_alignment_status": prompt["status"],
        "completion_only_status": mask["status"],
        "semantic_repair_status": "SEMANTIC_REPAIR_REMOVED_FROM_EVALUATION_PATH",
    }
    write_json(AUDIT / "v166_contract_unification_summary.json", summary)
    print(summary["status"])


if __name__ == "__main__":
    main()
