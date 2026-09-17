from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from v168_common import AUDIT, DATA, DOCS, ROOT, file_hash, now, read_json, read_jsonl, row_hash, write_doc, write_json


def git_blob_hash(path: str) -> str:
    proc = subprocess.run(["git", "show", f"da2e0399:{path}"], cwd=ROOT, capture_output=True, check=True)
    return hashlib.sha256(proc.stdout).hexdigest()


def chat_template_hash() -> str:
    import sys

    sys.path.insert(0, str(ROOT / "ai-service"))
    from transformers import AutoTokenizer
    from app.prompts.e_review_prompt_renderer import render_training_messages

    tokenizer = AutoTokenizer.from_pretrained(ROOT.parent / "models/Qwen3-1.7B", local_files_only=True, trust_remote_code=True)
    sample = read_jsonl(DATA / "train.jsonl")[0]
    messages = render_training_messages(sample)
    try:
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False, enable_thinking=False)
    except TypeError:
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return hashlib.sha256(rendered.encode("utf-8", errors="replace")).hexdigest()


def main() -> None:
    freeze = read_json(AUDIT / "v167_training_contract_freeze.json")
    split = read_json(AUDIT / "v167_synthetic_sft_v21_split.json")
    files = {
        "contract": "ai-service/app/contracts/e_review_decision.py",
        "prompt_renderer": "ai-service/app/prompts/e_review_prompt_renderer.py",
        "prompt": "ai-service/app/prompts/e_review_decision_prompt.py",
        "evaluator": "ai-service/app/evaluation/e_review_task_evaluator.py",
        "completion_encoder": "ai-service/app/training/completion_only.py",
    }
    current_hashes = {key: file_hash(ROOT / value) for key, value in files.items()}
    frozen_hashes = {key: git_blob_hash(value) for key, value in files.items()}
    manifest_hashes = {
        "train": file_hash(DATA / "train.jsonl"),
        "validation": file_hash(DATA / "validation.jsonl"),
        "holdout": file_hash(DATA / "engineering_holdout_v21.jsonl"),
    }
    chat_hash = chat_template_hash()
    pass_map = {
        **{f"{key}_hash_consistent": current_hashes[key] == frozen_hashes[key] for key in current_hashes},
        "train_manifest_hash_consistent": manifest_hashes["train"] == freeze["train_manifest_hash"] == split["manifest_hashes"]["train"],
        "validation_manifest_hash_consistent": manifest_hashes["validation"] == freeze["validation_manifest_hash"] == split["manifest_hashes"]["validation"],
        "holdout_manifest_hash_consistent": manifest_hashes["holdout"] == freeze["holdout_manifest_hash"] == split["manifest_hashes"]["engineering_holdout_v21"],
        "contract_version_consistent": freeze["contract_version"] == "v2.0.0",
        "prompt_version_consistent": freeze["prompt_version"] == "v2.0.0",
        "evaluator_version_consistent": freeze["evaluator_version"] == "v2.1.0",
        "completion_encoding_version_consistent": freeze["completion_encoding_version"] == "completion_only_v2.0.0",
    }
    result = {
        "generated_at": now(),
        "status": "V168_PRETRAIN_CONTRACT_INTEGRITY_PASS" if all(pass_map.values()) else "V168_PRETRAIN_CONTRACT_INTEGRITY_BLOCKED",
        "contract_version": freeze["contract_version"],
        "prompt_version": freeze["prompt_version"],
        "evaluator_version": freeze["evaluator_version"],
        "completion_encoding_version": freeze["completion_encoding_version"],
        "lineage_version": "v2.1_composite_lineage_group",
        "current_hashes": current_hashes,
        "frozen_git_head": "da2e0399",
        "frozen_hashes": frozen_hashes,
        "manifest_hashes": manifest_hashes,
        "frozen_manifest_hashes": {
            "train": freeze["train_manifest_hash"],
            "validation": freeze["validation_manifest_hash"],
            "holdout": freeze["holdout_manifest_hash"],
        },
        "chat_template_metadata": {"tokenizer": "Qwen3-1.7B", "enable_thinking": False, "hash": chat_hash},
        "pass_map": pass_map,
    }
    write_json(AUDIT / "v168_pretrain_contract_integrity.json", result)
    write_doc(
        DOCS / "218_v168_pretrain_contract_integrity.md",
        "V1.6.8 Pretrain Contract Integrity",
        [
            f"Status: `{result['status']}`",
            f"- contract_hash_consistent: `{pass_map['contract_hash_consistent']}`",
            f"- prompt_hash_consistent: `{pass_map['prompt_renderer_hash_consistent'] and pass_map['prompt_hash_consistent']}`",
            f"- evaluator_hash_consistent: `{pass_map['evaluator_hash_consistent']}`",
            f"- completion_encoder_hash_consistent: `{pass_map['completion_encoder_hash_consistent']}`",
            f"- train_manifest_hash_consistent: `{pass_map['train_manifest_hash_consistent']}`",
            f"- validation_manifest_hash_consistent: `{pass_map['validation_manifest_hash_consistent']}`",
            f"- holdout_manifest_hash_consistent: `{pass_map['holdout_manifest_hash_consistent']}`",
        ],
    )
    print(result["status"])


if __name__ == "__main__":
    main()
