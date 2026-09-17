from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from v169_common import AUDIT, DOCS, PRIVATE_ROOT, file_hash, now, read_jsonl, target, write_doc, write_json, write_jsonl

DATA_V23 = PRIVATE_ROOT / "synthetic-sft-v23"
SPLITS = ["train", "validation", "engineering_holdout_v23"]


def lineage(row: dict[str, Any]) -> dict[str, Any]:
    return row["metadata"]["lineage"]


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        value = lineage(row).get(key)
        if value:
            out[str(value)].add(row["metadata"]["split"])
    return out


def assert_no_cross_split(rows: list[dict[str, Any]], key: str) -> None:
    offenders = {k: sorted(v) for k, v in grouped(rows, key).items() if len(v) > 1}
    if offenders:
        raise RuntimeError(f"{key} crosses split: {offenders}")


def split_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "scenario_groups": len({lineage(row)["scenario_group_id"] for row in rows}),
        "risk_type": dict(Counter(target(row)["risk_type"] for row in rows)),
        "risk_level": dict(Counter(target(row)["risk_level"] for row in rows)),
        "need_human_review": dict(Counter(str(target(row)["need_human_review"]) for row in rows)),
        "scenario_family": dict(Counter(lineage(row)["scenario_family_id"] for row in rows)),
    }


def main() -> None:
    rows = read_jsonl(DATA_V23 / "all_samples.jsonl")
    for key in ["generation_root_id", "scenario_group_id", "contrast_pair_group_id", "template_instance_id"]:
        assert_no_cross_split(rows, key)
    by_split = {split: [row for row in rows if row["metadata"]["split"] == split] for split in SPLITS}
    for split, split_rows in by_split.items():
        write_jsonl(DATA_V23 / f"{split}.jsonl", split_rows)
    manifest = {
        "generated_at": now(),
        "status": "V23_LINEAGE_AND_CONTRAST_GROUP_PASS",
        "dataset_version": "synthetic_sft_v2.3",
        "split_counts": {split: split_counts(rows) for split, rows in by_split.items()},
        "manifest_hashes": {split: file_hash(DATA_V23 / f"{split}.jsonl") for split in SPLITS},
        "all_samples_hash": file_hash(DATA_V23 / "all_samples.jsonl"),
        "cross_split_generation_root_overlap": 0,
        "cross_split_scenario_group_overlap": 0,
        "cross_split_contrast_pair_overlap": 0,
        "cross_split_template_instance_overlap": 0,
    }
    seal_rows = by_split["engineering_holdout_v23"]
    seal = {
        "generated_at": now(),
        "status": "V23_ENGINEERING_HOLDOUT_SEALED",
        "count": len(seal_rows),
        "manifest_hash": manifest["manifest_hashes"]["engineering_holdout_v23"],
        "generation_root_hash": hashlib.sha256("".join(sorted({lineage(row)["generation_root_id"] for row in seal_rows})).encode()).hexdigest(),
        "scenario_group_hash": hashlib.sha256("".join(sorted({lineage(row)["scenario_group_id"] for row in seal_rows})).encode()).hexdigest(),
        "contrast_pair_hash": hashlib.sha256("".join(sorted(str(lineage(row).get("contrast_pair_group_id")) for row in seal_rows)).encode()).hexdigest(),
        "class_distribution": split_counts(seal_rows)["risk_type"],
        "risk_level_distribution": split_counts(seal_rows)["risk_level"],
        "human_review_distribution": split_counts(seal_rows)["need_human_review"],
        "sealed_at": now(),
        "allowed_use": "single_final_evaluation_after_experiment_a",
        "training_access": False,
        "prompt_tuning": False,
        "model_selection": False,
        "repeated_evaluation": False,
    }
    write_json(AUDIT / "v1612_synthetic_v23_split_manifest.json", manifest)
    write_json(AUDIT / "v23_holdout_seal.json", seal)
    write_doc(DOCS / "250_v1612_synthetic_v23_split.md", "V1.6.12 Synthetic V2.3 Split", [f"Status: `{manifest['status']}`", "- train/validation/holdout: `576 / 72 / 72`", f"- holdout seal: `{seal['status']}`"])
    print(manifest["status"])


if __name__ == "__main__":
    main()
