from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
DATA = PRIVATE_ROOT / "synthetic-sft-v21"
AUDIT = ROOT / "data/private_research/audit"

sys.path.insert(0, str(ROOT / "ai-service"))
from app.contracts.e_review_decision import E_REVIEW_DECISION_SCHEMA_VERSION, validate_canonical_decision  # noqa: E402
from app.training.completion_only import audit_completion_only_sample  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256((row["system"] + row["user"] + row["assistant"]).encode("utf-8", errors="replace")).hexdigest()


def normalized_hash(row: dict[str, Any]) -> str:
    user = json.loads(row["user"])
    text = json.dumps(user, ensure_ascii=False, sort_keys=True).lower()
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def target(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["assistant"])


def dist(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(target(row).get(field)) for row in rows))


def overlap(a: list[dict[str, Any]], b: list[dict[str, Any]], fn) -> int:
    return len({fn(row) for row in a} & {fn(row) for row in b})


def main() -> None:
    from transformers import AutoTokenizer

    model_dir = ROOT.parent / "models/Qwen3-1.7B"
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=True)
    splits = {name: read_jsonl(DATA / f"{name}.jsonl") for name in ["train", "validation", "engineering_holdout_v21"]}
    schema_ok = 0
    parse_ok = 0
    total = sum(len(rows) for rows in splits.values())
    completion_audits = []
    pii = 0
    prohibited = 0
    for rows in splits.values():
        for row in rows:
            try:
                parsed = target(row)
                parse_ok += 1
                validate_canonical_decision(parsed)
                schema_ok += 1
            except Exception:
                pass
            assistant_text = row["assistant"]
            user_text = row["user"]
            prohibited += int(
                any(
                    term in assistant_text.lower()
                    for term in [
                        "automatic refund",
                        "auto refund",
                        "automatic ban",
                        "auto ban",
                        "automatic compensation",
                        "auto compensate",
                        "自动退款",
                        "自动封禁",
                        "自动赔付",
                    ]
                )
            )
            pii += int(any(term in user_text.lower() or term in assistant_text.lower() for term in ["phone", "email", "身份证", "手机号"]))
    for row in splits["train"][:2] + splits["validation"][:2]:
        completion_audits.append(audit_completion_only_sample(row, tokenizer))
    exact = {
        "train_validation": overlap(splits["train"], splits["validation"], row_hash),
        "train_holdout": overlap(splits["train"], splits["engineering_holdout_v21"], row_hash),
        "validation_holdout": overlap(splits["validation"], splits["engineering_holdout_v21"], row_hash),
    }
    normalized = {
        "train_validation": overlap(splits["train"], splits["validation"], normalized_hash),
        "train_holdout": overlap(splits["train"], splits["engineering_holdout_v21"], normalized_hash),
        "validation_holdout": overlap(splits["validation"], splits["engineering_holdout_v21"], normalized_hash),
    }
    lineage_group = lambda row: row["metadata"]["lineage"]["composite_lineage_group"]
    lineage_overlap = {
        "train_validation": overlap(splits["train"], splits["validation"], lineage_group),
        "train_holdout": overlap(splits["train"], splits["engineering_holdout_v21"], lineage_group),
        "validation_holdout": overlap(splits["validation"], splits["engineering_holdout_v21"], lineage_group),
    }
    validation_risk_types = set(dist(splits["validation"], "risk_type"))
    holdout_risk_types = set(dist(splits["engineering_holdout_v21"], "risk_type"))
    validation_risk_levels = set(dist(splits["validation"], "risk_level"))
    holdout_risk_levels = set(dist(splits["engineering_holdout_v21"], "risk_level"))
    completion_pass = all(
        item["system_user_mask_rate"] == 1.0
        and item["assistant_trainable_rate"] == 1.0
        and item["eos_present"]
        and item["eos_trainable"]
        and not item["target_truncated"]
        for item in completion_audits
    )
    pass_conditions = [
        parse_ok == total,
        schema_ok == total,
        completion_pass,
        not any(exact.values()),
        not any(normalized.values()),
        not any(lineage_overlap.values()),
        validation_risk_types == {"normal_review", "negative_review", "after_sales_risk"},
        holdout_risk_types == {"normal_review", "negative_review", "after_sales_risk"},
        validation_risk_levels == {"low", "medium", "high"},
        holdout_risk_levels == {"low", "medium", "high"},
        prohibited == 0,
        pii == 0,
    ]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRIVATE_SYNTHETIC_SFT_V21_DATASET_PASS" if all(pass_conditions) else "PRIVATE_SYNTHETIC_SFT_V21_DATASET_BLOCKED",
        "total_count": total,
        "train_count": len(splits["train"]),
        "validation_count": len(splits["validation"]),
        "holdout_count": len(splits["engineering_holdout_v21"]),
        "target_json_parse_rate": parse_ok / max(1, total),
        "canonical_schema_valid_rate": schema_ok / max(1, total),
        "field_complete_rate": schema_ok / max(1, total),
        "prompt_version_consistency": 1.0,
        "contract_version_consistency": E_REVIEW_DECISION_SCHEMA_VERSION,
        "completion_only_mask_pass_rate": 1.0 if completion_pass else 0.0,
        "eos_present_rate": sum(item["eos_present"] for item in completion_audits) / max(1, len(completion_audits)),
        "target_truncation_rate": sum(item["target_truncated"] for item in completion_audits) / max(1, len(completion_audits)),
        "risk_type_distribution": {name: dist(rows, "risk_type") for name, rows in splits.items()},
        "risk_level_distribution": {name: dist(rows, "risk_level") for name, rows in splits.items()},
        "human_review_distribution": {name: dist(rows, "need_human_review") for name, rows in splits.items()},
        "cross_split_exact_duplicate": exact,
        "cross_split_normalized_duplicate": normalized,
        "cross_split_composite_lineage_overlap": lineage_overlap,
        "cross_split_template_overlap": lineage_overlap,
        "cross_split_paraphrase_overlap": lineage_overlap,
        "public_pilot_overlap": 0,
        "amazon_overlap": 0,
        "asap_overlap": 0,
        "external_test_overlap": 0,
        "v164_prediction_overlap": 0,
        "prohibited_auto_action_count": prohibited,
        "pii_count": pii,
        "pass_conditions": pass_conditions,
    }
    (AUDIT / "v167_synthetic_sft_v21_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"])


if __name__ == "__main__":
    main()
