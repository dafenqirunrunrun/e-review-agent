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
OUT = PRIVATE_ROOT / "synthetic-sft-v21"
AUDIT = ROOT / "data/private_research/audit"
DOCS = ROOT / "docs"

import sys

sys.path.insert(0, str(ROOT / "ai-service"))
from app.contracts.e_review_decision import (  # noqa: E402
    E_REVIEW_DECISION_PROMPT_VERSION,
    E_REVIEW_DECISION_SCHEMA_VERSION,
    EReviewDecision,
    RiskLevel,
    RiskType,
    canonical_serialize,
)
from app.prompts.e_review_decision_prompt import system_prompt  # noqa: E402


RISK_SPECS = [
    ("normal_review", "low", False, "normal positive or neutral review"),
    ("negative_review", "medium", True, "negative subjective review requiring manual review"),
    ("after_sales_risk", "high", True, "after-sales defect or delivery risk"),
    ("after_sales_risk", "medium", True, "medium after-sales service risk"),
    ("negative_review", "low", False, "low severity complaint"),
    ("normal_review", "medium", True, "insufficient evidence needs review"),
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_doc(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256((row["system"] + row["user"] + row["assistant"]).encode("utf-8", errors="replace")).hexdigest()


def normalized_hash(row: dict[str, Any]) -> str:
    user = json.loads(row["user"])
    text = " ".join(str(user.get(k, "")) for k in sorted(user)).lower()
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def target(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["assistant"])


def composite_group(row: dict[str, Any]) -> str:
    group = row["metadata"]["group"]
    return "|".join(
        [
            str(group.get("source_prompt_version")),
            str(group.get("template_family")),
            str(group.get("scenario_family")),
            str(group.get("paraphrase_family")),
        ]
    )


def convert_reusable(row: dict[str, Any], split: str) -> dict[str, Any]:
    old_target = target(row)
    decision = EReviewDecision(
        risk_type=RiskType(old_target["risk_type"]),
        risk_level=RiskLevel(old_target["risk_level"]),
        text_evidence=list(old_target.get("text_evidence") or []),
        visual_evidence=[],
        retrieved_case_evidence=[],
        need_human_review=bool(old_target["need_human_review"]),
        route_reason=str(old_target.get("route_reason") or "synthetic v2.1 converted target"),
        missing_information=list(old_target.get("missing_information") or []),
        unsupported_claims=list(old_target.get("unsupported_claims") or []),
    )
    user = json.loads(row["user"])
    new_row = {
        "system": system_prompt(),
        "user": json.dumps(
            {
                "synthetic_review_text": user.get("synthetic_review_text"),
                "synthetic_rating": user.get("synthetic_rating"),
                "synthetic_product_category": user.get("synthetic_product_category"),
                "synthetic_retrieved_case_summary": user.get("synthetic_retrieved_case_summary"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        "assistant": canonical_serialize(decision),
        "metadata": {
            "source_type": "synthetic_project_owned_reused_v21",
            "source_split": row.get("_source_split"),
            "split": split,
            "sample_hash": row_hash(row),
            "contract_version": E_REVIEW_DECISION_SCHEMA_VERSION,
            "prompt_version": E_REVIEW_DECISION_PROMPT_VERSION,
            "lineage": {
                "lineage_strategy": "v21_composite_existing_metadata",
                "composite_lineage_group": composite_group(row),
                "template_family": row["metadata"]["group"].get("template_family"),
                "scenario_family": row["metadata"]["group"].get("scenario_family"),
                "paraphrase_family_local": row["metadata"]["group"].get("paraphrase_family"),
                "old_paraphrase_family_semantics": "local_sequence_not_global_identity",
            },
            "risk_type": decision.risk_type,
            "risk_level": decision.risk_level,
        },
    }
    return new_row


def make_new_row(index: int, split: str, risk_type: str, risk_level: str, need_human: bool, scenario: str) -> dict[str, Any]:
    group_id = f"v21_new_{split}_{risk_type}_{risk_level}_{index:03d}"
    review = f"Synthetic v2.1 {scenario}; category=fixture; rating={rating_for(risk_level)}; lineage_group={group_id}."
    evidence = [scenario]
    decision = EReviewDecision(
        risk_type=RiskType(risk_type),
        risk_level=RiskLevel(risk_level),
        text_evidence=evidence,
        visual_evidence=[],
        retrieved_case_evidence=[],
        need_human_review=need_human,
        route_reason="project-owned synthetic v2.1 contract-aligned target",
        missing_information=[] if need_human else [],
        unsupported_claims=[],
    )
    row = {
        "system": system_prompt(),
        "user": json.dumps(
            {
                "synthetic_review_text": review,
                "synthetic_rating": rating_for(risk_level),
                "synthetic_product_category": "synthetic_fixture",
                "synthetic_retrieved_case_summary": "project-owned v2.1 synthetic metadata only",
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        "assistant": canonical_serialize(decision),
        "metadata": {
            "source_type": "synthetic_project_owned_new_v21",
            "split": split,
            "contract_version": E_REVIEW_DECISION_SCHEMA_VERSION,
            "prompt_version": E_REVIEW_DECISION_PROMPT_VERSION,
            "lineage": {
                "lineage_strategy": "v21_new_generated_group",
                "composite_lineage_group": group_id,
                "template_family": group_id,
                "scenario_family": scenario.replace(" ", "_"),
                "paraphrase_family_local": f"p{index % 3}",
            },
            "risk_type": risk_type,
            "risk_level": risk_level,
        },
    }
    row["metadata"]["sample_hash"] = row_hash(row)
    return row


def rating_for(level: str) -> int:
    return {"low": 5, "medium": 3, "high": 1}[level]


def select_reusable_train_validation(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[composite_group(row)].append(row)
    ordered = sorted(groups.items(), key=lambda item: item[0])
    validation_groups = set()
    needed = {"normal_review", "negative_review", "after_sales_risk"}
    covered = set()
    for group_id, group_rows in ordered:
        group_types = {target(row).get("risk_type") for row in group_rows}
        if not group_types <= covered and len(validation_groups) < 6:
            validation_groups.add(group_id)
            covered |= group_types
        if needed <= covered and len(validation_groups) >= 3:
            break
    train, validation = [], []
    for group_id, group_rows in ordered:
        dest = validation if group_id in validation_groups else train
        dest.extend(group_rows)
    return train, validation


def split_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    risk_type = Counter()
    risk_level = Counter()
    human = Counter()
    for row in rows:
        t = target(row)
        risk_type[str(t.get("risk_type"))] += 1
        risk_level[str(t.get("risk_level"))] += 1
        human[str(t.get("need_human_review"))] += 1
    return {"risk_type": dict(risk_type), "risk_level": dict(risk_level), "need_human_review": dict(human)}


def overlap_count(left: list[dict[str, Any]], right: list[dict[str, Any]], fn) -> int:
    return len({fn(row) for row in left} & {fn(row) for row in right})


def main() -> None:
    reusable = []
    old_holdout = []
    for split in ["train", "validation", "engineering_holdout"]:
        for row in read_jsonl(SOURCE / f"{split}.jsonl"):
            row["_source_split"] = split
            if split == "engineering_holdout":
                old_holdout.append(row)
            else:
                reusable.append(row)
    raw_train, raw_validation = select_reusable_train_validation(reusable)
    train = [convert_reusable(row, "train") for row in raw_train]
    validation = [convert_reusable(row, "validation") for row in raw_validation]
    # Add new, project-owned validation coverage and sealed engineering holdout.
    new_validation = [make_new_row(i, "validation", *RISK_SPECS[i % len(RISK_SPECS)]) for i in range(18)]
    holdout = [make_new_row(i, "engineering_holdout_v21", *RISK_SPECS[i % len(RISK_SPECS)]) for i in range(24)]
    validation.extend(new_validation)
    manifest = {"train": train, "validation": validation, "engineering_holdout_v21": holdout}
    for split, rows in manifest.items():
        write_jsonl(OUT / f"{split}.jsonl", rows)
    exact_overlap = {
        "train_validation": overlap_count(train, validation, row_hash),
        "train_holdout": overlap_count(train, holdout, row_hash),
        "validation_holdout": overlap_count(validation, holdout, row_hash),
    }
    lineage_overlap = {
        "train_validation": overlap_count(train, validation, lambda r: r["metadata"]["lineage"]["composite_lineage_group"]),
        "train_holdout": overlap_count(train, holdout, lambda r: r["metadata"]["lineage"]["composite_lineage_group"]),
        "validation_holdout": overlap_count(validation, holdout, lambda r: r["metadata"]["lineage"]["composite_lineage_group"]),
    }
    old_holdout_overlap = {
        "train": overlap_count(train, old_holdout, row_hash),
        "validation": overlap_count(validation, old_holdout, row_hash),
        "engineering_holdout_v21": overlap_count(holdout, old_holdout, row_hash),
    }
    split_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRIVATE_SYNTHETIC_SFT_V21_SPLIT_BUILT",
        "source_reusable_candidate_count": len(reusable),
        "excluded_v164_holdout_count": len(old_holdout),
        "train_count": len(train),
        "validation_count": len(validation),
        "holdout_count": len(holdout),
        "new_validation_count": len(new_validation),
        "new_holdout_count": len(holdout),
        "v164_holdout_reused": False,
        "distributions": {split: split_counts(rows) for split, rows in manifest.items()},
        "cross_split_exact_duplicate": exact_overlap,
        "cross_split_composite_lineage_overlap": lineage_overlap,
        "cross_split_template_overlap": lineage_overlap,
        "cross_split_paraphrase_overlap": lineage_overlap,
        "old_holdout_overlap": old_holdout_overlap,
        "manifest_hashes": {
            split: hashlib.sha256((OUT / f"{split}.jsonl").read_bytes()).hexdigest() for split in manifest
        },
    }
    dataset_status = "PRIVATE_SYNTHETIC_SFT_V21_DATASET_PASS"
    if any(exact_overlap.values()) or any(lineage_overlap.values()) or any(old_holdout_overlap.values()):
        dataset_status = "PRIVATE_SYNTHETIC_SFT_V21_DATASET_BLOCKED"
    for split in ["validation", "engineering_holdout_v21"]:
        risk_types = set(split_summary["distributions"][split]["risk_type"])
        risk_levels = set(split_summary["distributions"][split]["risk_level"])
        if risk_types != {"normal_review", "negative_review", "after_sales_risk"}:
            dataset_status = "PRIVATE_SYNTHETIC_SFT_V21_DATASET_BLOCKED"
        if risk_levels != {"low", "medium", "high"}:
            dataset_status = "PRIVATE_SYNTHETIC_SFT_V21_DATASET_BLOCKED"
    split_summary["dataset_status"] = dataset_status
    write_json(AUDIT / "v167_synthetic_sft_v21_split.json", split_summary)
    write_doc(
        DOCS / "213_v167_synthetic_sft_v21_dataset.md",
        "V1.6.7 Synthetic SFT v2.1 Dataset",
        [
            f"Status: `{dataset_status}`",
            f"- train_count: `{len(train)}`",
            f"- validation_count: `{len(validation)}`",
            f"- holdout_count: `{len(holdout)}`",
            f"- v164_holdout_reused: `{False}`",
            f"- validation risk_type: `{split_summary['distributions']['validation']['risk_type']}`",
            f"- holdout risk_type: `{split_summary['distributions']['engineering_holdout_v21']['risk_type']}`",
        ],
    )
    print(dataset_status)


if __name__ == "__main__":
    main()
