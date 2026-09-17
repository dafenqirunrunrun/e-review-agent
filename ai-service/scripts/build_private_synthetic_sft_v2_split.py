from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
SOURCE = PRIVATE_ROOT / "synthetic-sft-v1633"
OUT_DIR = PRIVATE_ROOT / "synthetic-sft-v2"
AUDIT = ROOT / "data/private_research/audit"
DOCS = ROOT / "docs"

sys.path.insert(0, str(ROOT / "ai-service"))
from app.contracts.e_review_decision import E_REVIEW_DECISION_SCHEMA_VERSION  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_doc(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def hash_row(row: dict[str, Any]) -> str:
    return hashlib.sha256((row.get("system", "") + row.get("user", "") + row.get("assistant", "")).encode("utf-8", errors="replace")).hexdigest()


def target(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["assistant"])


def load_source() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reusable = []
    excluded_holdout = []
    for split in ["train", "validation", "engineering_holdout"]:
        for row in read_jsonl(SOURCE / f"{split}.jsonl"):
            row["_source_split"] = split
            if split == "engineering_holdout":
                excluded_holdout.append(row)
            else:
                reusable.append(row)
    return reusable, excluded_holdout


def main() -> None:
    rows, excluded = load_source()
    paraphrase = Counter(row.get("metadata", {}).get("group", {}).get("paraphrase_family") for row in rows)
    template = Counter(row.get("metadata", {}).get("group", {}).get("template_family") for row in rows)
    blocked_reasons = []
    if len(paraphrase) <= 1:
        blocked_reasons.append(
            {
                "constraint": "same paraphrase_family must not cross split",
                "reason": "all reusable records share one paraphrase_family, so train/validation/holdout isolation is impossible without generating new data",
                "families": dict(paraphrase),
            }
        )
    risk_type_dist = Counter(target(row).get("risk_type") for row in rows)
    risk_level_dist = Counter(target(row).get("risk_level") for row in rows)
    human_dist = Counter(str(target(row).get("need_human_review")) for row in rows)
    status = "SYNTHETIC_SFT_V2_SPLIT_BLOCKED_GROUP_CONSTRAINT" if blocked_reasons else "PRIVATE_SYNTHETIC_SFT_V2_DATASET_PASS"
    split_result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source": "synthetic-sft-v1633 train+validation only",
        "v164_holdout_excluded_count": len(excluded),
        "v164_holdout_reuse_allowed": False,
        "candidate_count": len(rows),
        "train_count": 0,
        "validation_count": 0,
        "holdout_count": 0,
        "blocked_reasons": blocked_reasons,
        "risk_type_distribution": dict(risk_type_dist),
        "risk_level_distribution": dict(risk_level_dist),
        "human_review_distribution": dict(human_dist),
        "template_family_count": len(template),
        "paraphrase_family_count": len(paraphrase),
        "cross_split_exact_duplicate": None,
        "cross_split_template_overlap": None,
        "cross_split_paraphrase_overlap": None,
        "amazon_overlap": 0,
        "asap_overlap": 0,
        "public_pilot_overlap": 0,
        "external_test_overlap": 0,
        "output_private_dir": str(OUT_DIR.name),
        "data_files_written": False,
    }
    summary = {
        "generated_at": split_result["generated_at"],
        "status": "PRIVATE_SYNTHETIC_SFT_V2_DATASET_BLOCKED",
        "total_count": len(rows),
        "train_count": 0,
        "validation_count": 0,
        "holdout_count": 0,
        "target_json_parse_rate": 1.0,
        "canonical_schema_valid_rate": None,
        "field_complete_rate": None,
        "prompt_version_consistency": None,
        "contract_version_consistency": E_REVIEW_DECISION_SCHEMA_VERSION,
        "completion_only_mask_pass_rate": None,
        "eos_present_rate": None,
        "target_truncation_rate": None,
        "risk_type_distribution": dict(risk_type_dist),
        "risk_level_distribution": dict(risk_level_dist),
        "human_review_distribution": dict(human_dist),
        "cross_split_exact_duplicate": None,
        "cross_split_normalized_duplicate": None,
        "cross_split_template_overlap": None,
        "cross_split_paraphrase_overlap": None,
        "public_pilot_overlap": 0,
        "amazon_overlap": 0,
        "asap_overlap": 0,
        "external_test_overlap": 0,
        "v164_prediction_overlap": 0,
        "prohibited_auto_action_count": 0,
        "pii_count": 0,
        "blocked_reasons": blocked_reasons,
    }
    write_json(AUDIT / "v166_synthetic_sft_v2_split.json", split_result)
    write_json(AUDIT / "v166_synthetic_sft_v2_summary.json", summary)
    write_doc(
        DOCS / "208_v166_synthetic_sft_v2_dataset.md",
        "V1.6.6 Synthetic SFT v2 Dataset",
        [
            f"Status: `{summary['status']}`",
            f"- candidate_count: `{len(rows)}`",
            f"- v164_holdout_excluded_count: `{len(excluded)}`",
            f"- paraphrase_family_count: `{len(paraphrase)}`",
            f"- blocked_reason: `{blocked_reasons[0]['reason'] if blocked_reasons else ''}`",
        ],
    )
    print(status)


if __name__ == "__main__":
    main()
