from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/private_research/audit"
DOCS = ROOT / "docs"


def load(name: str) -> dict:
    path = AUDIT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    contract = load("v166_contract_unification_summary.json")
    dataset = load("v166_synthetic_sft_v2_summary.json")
    gates = {
        "CANONICAL_SCHEMA_SINGLE_SOURCE_PASS": contract.get("schema_consumer_status") == "CANONICAL_SCHEMA_SINGLE_SOURCE_PASS",
        "PROMPT_CONTRACT_ALIGNMENT_PASS": contract.get("prompt_alignment_status") == "PROMPT_CONTRACT_ALIGNMENT_PASS",
        "COMPLETION_ONLY_LABEL_MASK_PASS": contract.get("completion_only_status") == "COMPLETION_ONLY_LABEL_MASK_PASS",
        "PRIVATE_SYNTHETIC_SFT_V2_DATASET_PASS": dataset.get("audit_status") == "PRIVATE_SYNTHETIC_SFT_V2_DATASET_PASS",
    }
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "V166_BASE_PROMPT_CONTRACT_CANARY_BLOCKED",
        "gates": gates,
        "blocked_reason": "v2 dataset gate did not pass; canary cannot run without validation split",
        "holdout_read": False,
        "old_adapter_used": False,
        "real_inference_count": 0,
        "raw_json_parse_success_rate": None,
        "raw_canonical_schema_valid_rate": None,
        "required_field_presence_rate": None,
        "input_echo_rate": None,
        "operational_fallback_rate": None,
        "prohibited_auto_action_count": None,
        "avg_generate_ms": None,
        "p95_generate_ms": None,
    }
    write_json(AUDIT / "v166_base_prompt_canary.json", result)
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "210_v166_base_prompt_contract_canary.md").write_text(
        "# V1.6.6 Base Prompt Contract Canary\n\n"
        f"Status: `{result['status']}`\n\n"
        f"- gates: `{gates}`\n"
        f"- blocked_reason: {result['blocked_reason']}\n",
        encoding="utf-8",
    )
    print(result["status"])


if __name__ == "__main__":
    main()

