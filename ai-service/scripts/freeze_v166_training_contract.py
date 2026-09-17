from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/private_research/audit"
DOCS = ROOT / "docs"


def load(name: str) -> dict:
    path = AUDIT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main() -> None:
    contract = load("v166_canonical_contract.json")
    prompt = load("v166_prompt_alignment.json")
    dataset = load("v166_synthetic_sft_v2_split.json")
    canary = load("v166_base_prompt_canary.json")
    allowed = all(
        [
            load("v166_contract_unification_summary.json").get("schema_consumer_status") == "CANONICAL_SCHEMA_SINGLE_SOURCE_PASS",
            load("v166_contract_unification_summary.json").get("semantic_repair_status") == "SEMANTIC_REPAIR_REMOVED_FROM_EVALUATION_PATH",
            load("v166_contract_unification_summary.json").get("completion_only_status") == "COMPLETION_ONLY_LABEL_MASK_PASS",
            load("v166_synthetic_sft_v2_summary.json").get("audit_status") == "PRIVATE_SYNTHETIC_SFT_V2_DATASET_PASS",
            canary.get("status") == "V166_BASE_PROMPT_CONTRACT_CANARY_PASS",
        ]
    )
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "SYNTHETIC_SFT_V2_CONTRACT_FROZEN" if allowed else "SYNTHETIC_SFT_V2_CONTRACT_FREEZE_BLOCKED",
        "sft_v2_rebuild_status": "SYNTHETIC_SFT_V2_REBUILD_ALLOWED" if allowed else "SYNTHETIC_SFT_V2_REBUILD_BLOCKED",
        "contract_version": contract.get("schema_version"),
        "prompt_version": prompt.get("prompt_metadata", {}).get("prompt_version"),
        "evaluator_version": "v2.0.0",
        "completion_encoding_version": "completion_only_v2.0.0",
        "split_manifest_hash": file_hash(AUDIT / "v166_synthetic_sft_v2_split.json"),
        "validation_manifest_hash": None,
        "holdout_manifest_hash": None,
        "changes_require_new_experiment_version": True,
        "blocked_reason": "dataset/canary gates blocked" if not allowed else None,
    }
    (AUDIT / "v166_training_contract_freeze.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DOCS / "206_v166_training_contract_freeze.md").write_text(
        "# V1.6.6 Training Contract Freeze\n\n"
        f"Status: `{result['status']}`\n\n"
        f"- sft_v2_rebuild_status: `{result['sft_v2_rebuild_status']}`\n"
        f"- contract_version: `{result['contract_version']}`\n"
        f"- prompt_version: `{result['prompt_version']}`\n"
        f"- blocked_reason: `{result['blocked_reason']}`\n",
        encoding="utf-8",
    )
    print(result["sft_v2_rebuild_status"])


if __name__ == "__main__":
    main()
