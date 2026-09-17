from __future__ import annotations

import hashlib
from pathlib import Path

from v169_common import AUDIT, DATA_V22, DOCS, MODEL_DIR, ROOT, file_hash, now, read_json, read_jsonl, write_doc, write_json


def chat_template_hash() -> str:
    import sys

    sys.path.insert(0, str(ROOT / "ai-service"))
    from transformers import AutoTokenizer
    from app.prompts.e_review_prompt_renderer import render_training_messages

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
    messages = render_training_messages(read_jsonl(DATA_V22 / "train.jsonl")[0])
    try:
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False, enable_thinking=False)
    except TypeError:
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return hashlib.sha256(rendered.encode("utf-8", errors="replace")).hexdigest()


def main() -> None:
    token_gate = read_json(AUDIT / "v169_sft_v22_token_audit.json")
    dataset_gate = read_json(AUDIT / "v169_sft_v22_dataset_audit.json")
    canary = read_json(AUDIT / "v169_base_prompt_canary.json")
    seal_path = AUDIT / "v22_holdout_seal.json"
    seal = read_json(seal_path)
    pass_conditions = [
        token_gate["status"] == "V22_TOKEN_BUDGET_DATA_PASS",
        dataset_gate["status"] == "PRIVATE_SYNTHETIC_SFT_V22_DATASET_PASS",
        canary["status"] == "V169_BASE_PROMPT_V21_CANARY_PASS",
        seal["status"] == "V22_ENGINEERING_HOLDOUT_SEALED",
    ]
    files = {
        "contract_hash": ROOT / "ai-service/app/contracts/e_review_decision.py",
        "prompt_hash": ROOT / "ai-service/app/prompts/e_review_decision_prompt.py",
        "renderer_hash": ROOT / "ai-service/app/prompts/e_review_prompt_renderer.py",
        "evaluator_hash": ROOT / "ai-service/app/evaluation/e_review_task_evaluator.py",
        "completion_encoder_hash": ROOT / "ai-service/app/training/completion_only.py",
        "compact_target_hash": ROOT / "ai-service/app/training/compact_target_serialization.py",
    }
    result = {
        "generated_at": now(),
        "status": "SYNTHETIC_SFT_V22_CONTRACT_FROZEN" if all(pass_conditions) else "SYNTHETIC_SFT_V22_CONTRACT_FREEZE_BLOCKED",
        "contract_version": "v2.0.0",
        "prompt_version": "v2.1.0",
        "renderer_version": "v2.1.0",
        "evaluator_version": "v2.1.0",
        "completion_encoding_version": "completion_only_v2.2.0",
        "max_length": 384,
        "max_new_tokens": 160,
        **{key: file_hash(path) for key, path in files.items()},
        "train_manifest_hash": file_hash(DATA_V22 / "train.jsonl"),
        "validation_manifest_hash": file_hash(DATA_V22 / "validation.jsonl"),
        "holdout_manifest_hash": file_hash(DATA_V22 / "engineering_holdout_v21.jsonl"),
        "holdout_seal_hash": file_hash(seal_path),
        "tokenizer_metadata": {"model": "Qwen3-1.7B", "local_files_only": True},
        "chat_template_metadata": {"enable_thinking": False, "hash": chat_template_hash()},
        "pass_conditions": pass_conditions,
    }
    write_json(AUDIT / "v169_v22_training_contract_freeze.json", result)
    write_doc(
        DOCS / "231_v169_v22_training_contract_freeze.md",
        "V1.6.9 V2.2 Training Contract Freeze",
        [
            f"Status: `{result['status']}`",
            f"- contract_version: `{result['contract_version']}`",
            f"- prompt_version: `{result['prompt_version']}`",
            f"- renderer_version: `{result['renderer_version']}`",
            f"- completion_encoding_version: `{result['completion_encoding_version']}`",
            f"- train_manifest_hash: `{result['train_manifest_hash']}`",
            f"- validation_manifest_hash: `{result['validation_manifest_hash']}`",
            f"- holdout_manifest_hash: `{result['holdout_manifest_hash']}`",
        ],
    )
    print(result["status"])


if __name__ == "__main__":
    main()
