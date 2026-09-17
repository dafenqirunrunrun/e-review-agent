from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/private_research/audit"


def main() -> None:
    split_path = AUDIT / "v166_synthetic_sft_v2_split.json"
    summary_path = AUDIT / "v166_synthetic_sft_v2_summary.json"
    split = json.loads(split_path.read_text(encoding="utf-8")) if split_path.exists() else {"status": "SPLIT_NOT_BUILT"}
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    pass_conditions = [
        split.get("status") == "PRIVATE_SYNTHETIC_SFT_V2_DATASET_PASS",
        summary.get("target_json_parse_rate") == 1.0,
        summary.get("canonical_schema_valid_rate") == 1.0,
        summary.get("completion_only_mask_pass_rate") == 1.0,
        summary.get("target_truncation_rate") == 0,
        summary.get("cross_split_exact_duplicate") == 0,
        summary.get("cross_split_template_overlap") == 0,
        summary.get("cross_split_paraphrase_overlap") == 0,
        summary.get("amazon_overlap") == 0,
        summary.get("asap_overlap") == 0,
        summary.get("external_test_overlap") == 0,
    ]
    result = {
        **summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_status": "PRIVATE_SYNTHETIC_SFT_V2_DATASET_PASS" if all(pass_conditions) else "PRIVATE_SYNTHETIC_SFT_V2_DATASET_BLOCKED",
        "split_status": split.get("status"),
        "pass_conditions": pass_conditions,
    }
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["audit_status"])


if __name__ == "__main__":
    main()
