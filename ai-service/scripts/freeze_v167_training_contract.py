from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
DATA = PRIVATE_ROOT / "synthetic-sft-v21"
AUDIT = ROOT / "data/private_research/audit"
DOCS = ROOT / "docs"


def load(name: str) -> dict:
    path = AUDIT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main() -> None:
    dataset = load("v167_synthetic_sft_v21_summary.json")
    canary = load("v167_base_prompt_canary.json")
    contract = load("v166_canonical_contract.json")
    prompt = load("v166_prompt_alignment.json")
    allowed = dataset.get("status") == "PRIVATE_SYNTHETIC_SFT_V21_DATASET_PASS" and canary.get("status") == "V167_BASE_PROMPT_CONTRACT_CANARY_PASS"
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "SYNTHETIC_SFT_V21_CONTRACT_FROZEN" if allowed else "SYNTHETIC_SFT_V21_CONTRACT_FREEZE_BLOCKED",
        "sft_v21_rebuild_status": "SYNTHETIC_SFT_V21_REBUILD_ALLOWED" if allowed else "SYNTHETIC_SFT_V21_REBUILD_BLOCKED",
        "contract_version": contract.get("schema_version", "v2.0.0"),
        "prompt_version": prompt.get("prompt_metadata", {}).get("prompt_version", "v2.0.0"),
        "evaluator_version": "v2.1.0",
        "completion_encoding_version": "completion_only_v2.0.0",
        "split_manifest_hash": file_hash(AUDIT / "v167_synthetic_sft_v21_split.json"),
        "train_manifest_hash": file_hash(DATA / "train.jsonl"),
        "validation_manifest_hash": file_hash(DATA / "validation.jsonl"),
        "holdout_manifest_hash": file_hash(DATA / "engineering_holdout_v21.jsonl"),
        "frozen_at": datetime.now(timezone.utc).isoformat() if allowed else None,
        "changes_require_new_experiment_version": True,
        "blocked_reason": None if allowed else "dataset or canary gate blocked",
    }
    (AUDIT / "v167_training_contract_freeze.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DOCS / "215_v167_training_contract_freeze.md").write_text(
        "# V1.6.7 Training Contract Freeze\n\n"
        f"Status: `{result['status']}`\n\n"
        f"- sft_v21_rebuild_status: `{result['sft_v21_rebuild_status']}`\n"
        f"- contract_version: `{result['contract_version']}`\n"
        f"- prompt_version: `{result['prompt_version']}`\n"
        f"- split_manifest_hash: `{result['split_manifest_hash']}`\n",
        encoding="utf-8",
    )
    print(result["sft_v21_rebuild_status"])


if __name__ == "__main__":
    main()
