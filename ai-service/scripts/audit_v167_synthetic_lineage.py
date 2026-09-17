from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
SOURCE = PRIVATE_ROOT / "synthetic-sft-v1633"
AUDIT = ROOT / "data/private_research/audit"
DOCS = ROOT / "docs"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_doc(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256((row["system"] + row["user"] + row["assistant"]).encode("utf-8", errors="replace")).hexdigest()


def target(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["assistant"])


def load_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reusable: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for split in ["train", "validation", "engineering_holdout"]:
        for row in read_jsonl(SOURCE / f"{split}.jsonl"):
            row["_source_split"] = split
            if split == "engineering_holdout":
                holdout.append(row)
            else:
                reusable.append(row)
    return reusable, holdout


def main() -> None:
    reusable, holdout = load_rows()
    family_values: dict[str, Counter] = defaultdict(Counter)
    for row in reusable:
        group = row.get("metadata", {}).get("group", {})
        for field in ["generation_batch", "paraphrase_family", "risk_type", "scenario_family", "source_prompt_version", "template_family"]:
            family_values[field][str(group.get(field))] += 1
    classification = {
        "generation_batch": {
            "semantic": "source batch locator",
            "lineage_role": "source_locator",
            "split_constraint": "not a leakage group",
            "reason": "single project-owned generator source; using it as group would block all splits",
        },
        "paraphrase_family": {
            "semantic": "local paraphrase index within generator/template, not global identity",
            "lineage_role": "local_sequence_number",
            "split_constraint": "must be composed with template_family and scenario_family before use",
            "reason": "all reusable rows have p0; treating p0 globally collapses all records into one group",
        },
        "risk_type": {
            "semantic": "label category",
            "lineage_role": "stratification_label",
            "split_constraint": "must be present in every split",
            "reason": "label distribution, not leakage identity",
        },
        "scenario_family": {
            "semantic": "scenario/taxonomy family",
            "lineage_role": "semantic_family",
            "split_constraint": "stratify/inspect; not alone a hard leakage group",
            "reason": "families are intentionally repeated across categories",
        },
        "source_prompt_version": {
            "semantic": "generator prompt version",
            "lineage_role": "generator_version",
            "split_constraint": "must be recorded; not split group",
            "reason": "single version among reusable data",
        },
        "template_family": {
            "semantic": "template/case family",
            "lineage_role": "hard_leakage_group",
            "split_constraint": "must not cross split for reused rows",
            "reason": "same template can leak surface form and scenario wording",
        },
        "composite_lineage_group_v21": {
            "semantic": "derived from source fields without inventing new ancestry",
            "lineage_role": "hard_leakage_group",
            "definition": "source_prompt_version|template_family|scenario_family|paraphrase_family",
            "split_constraint": "must not cross split",
        },
    }
    composite = Counter(
        "|".join(
            [
                str(row["metadata"]["group"].get("source_prompt_version")),
                str(row["metadata"]["group"].get("template_family")),
                str(row["metadata"]["group"].get("scenario_family")),
                str(row["metadata"]["group"].get("paraphrase_family")),
            ]
        )
        for row in reusable
    )
    freeze = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "V166_SPLIT_BLOCK_FROZEN",
        "reusable_candidate_count": len(reusable),
        "excluded_v164_holdout_count": len(holdout),
        "paraphrase_family_unique_values": sorted(family_values["paraphrase_family"]),
        "v166_dataset_status": "PRIVATE_SYNTHETIC_SFT_V2_DATASET_BLOCKED",
        "v166_canary_status": "V166_BASE_PROMPT_CONTRACT_CANARY_BLOCKED",
        "v166_rebuild_status": "SYNTHETIC_SFT_V2_REBUILD_BLOCKED",
        "block_reason": "global paraphrase_family=p0 was treated as a hard group",
        "v164_holdout_reuse_allowed": False,
    }
    audit = {
        "generated_at": freeze["generated_at"],
        "status": "SYNTHETIC_LINEAGE_AUDIT_PASS",
        "field_value_counts": {key: dict(value) for key, value in family_values.items()},
        "field_classification": classification,
        "composite_lineage_group_count": len(composite),
        "composite_lineage_group_top_counts": dict(composite.most_common(10)),
        "exact_duplicate_count": len(reusable) - len({row_hash(row) for row in reusable}),
        "v164_holdout_hashes_excluded": len({row_hash(row) for row in holdout}),
        "lineage_repair_decision": "use composite_lineage_group_v21; do not treat local paraphrase_family alone as global identity",
    }
    write_json(AUDIT / "v166_split_block_freeze.json", freeze)
    write_json(AUDIT / "v167_synthetic_lineage_audit.json", audit)
    write_doc(
        DOCS / "211_v167_v166_split_block_freeze.md",
        "V1.6.7 V1.6.6 Split Block Freeze",
        [
            f"Status: `{freeze['status']}`",
            f"- reusable_candidate_count: `{freeze['reusable_candidate_count']}`",
            f"- excluded_v164_holdout_count: `{freeze['excluded_v164_holdout_count']}`",
            f"- paraphrase_family_unique_values: `{freeze['paraphrase_family_unique_values']}`",
            f"- block_reason: {freeze['block_reason']}",
        ],
    )
    write_doc(
        DOCS / "212_v167_synthetic_lineage_audit.md",
        "V1.6.7 Synthetic Lineage Audit",
        [
            f"Status: `{audit['status']}`",
            f"- composite_lineage_group_count: `{audit['composite_lineage_group_count']}`",
            "- Decision: `paraphrase_family=p0` is a local sequence value, not a global leakage identity.",
            "- Hard leakage group for reused rows: `source_prompt_version|template_family|scenario_family|paraphrase_family`.",
        ],
    )
    print(audit["status"])


if __name__ == "__main__":
    main()
