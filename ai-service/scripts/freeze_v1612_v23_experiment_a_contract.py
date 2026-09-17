from __future__ import annotations

import hashlib
from pathlib import Path

from v169_common import AUDIT, DOCS, PRIVATE_ROOT, file_hash, now, write_doc, write_json

ROOT = Path(__file__).resolve().parents[2]
DATA_V23 = PRIVATE_ROOT / "synthetic-sft-v23"


def path_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    result = {
        "generated_at": now(),
        "status": "V23_EXPERIMENT_A_CONTRACT_FROZEN",
        "contract_version": "v2.0.0",
        "prompt_version": "v2.1.0",
        "evaluator_version": "v2.1.0",
        "data_version": "v2.3",
        "train_hash": file_hash(DATA_V23 / "train.jsonl"),
        "validation_hash": file_hash(DATA_V23 / "validation.jsonl"),
        "holdout_hash": file_hash(DATA_V23 / "engineering_holdout_v23.jsonl"),
        "lineage_version": "synthetic_v23_lineage_v1.0.0",
        "generator_version": path_hash(ROOT / "ai-service/scripts/generate_private_synthetic_sft_v23.py"),
        "max_length": 384,
        "target_modules": ["q_proj", "v_proj"],
        "lora_r": 8,
        "epoch": 1,
        "old_adapter_warm_start": False,
        "holdout_training_access": False,
    }
    write_json(AUDIT / "v1612_experiment_a_contract_freeze.json", result)
    write_doc(DOCS / "252_v1612_experiment_a_contract_freeze.md", "V1.6.12 Experiment A Contract Freeze", [f"Status: `{result['status']}`", f"- train_hash: `{result['train_hash']}`", f"- validation_hash: `{result['validation_hash']}`", f"- holdout_hash: `{result['holdout_hash']}`", "- q/v, r=8, epoch=1 remain frozen."])
    print(result["status"])


if __name__ == "__main__":
    main()
