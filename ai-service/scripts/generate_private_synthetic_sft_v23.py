from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from v169_common import AUDIT, DOCS, compact_json, now, write_doc, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
DATA_V23 = PRIVATE_ROOT / "synthetic-sft-v23"
SEED = 231612

sys.path.insert(0, str(ROOT / "ai-service"))
from app.contracts.e_review_decision import E_REVIEW_DECISION_SCHEMA_VERSION, validate_canonical_decision  # noqa: E402
from app.prompts.e_review_decision_prompt import E_REVIEW_DECISION_PROMPT_VERSION, system_prompt  # noqa: E402
from app.training.compact_target_serialization import compact_canonical_serialize  # noqa: E402
from app.training.synthetic_v23_lineage import DATASET_VERSION, SyntheticV23Lineage  # noqa: E402
from app.training.synthetic_v23_surface_realizer import REALIZER_IDS, ScenarioSpec, render_surface  # noqa: E402


PRODUCTS = ["desk lamp", "travel mug", "phone case", "air purifier", "office chair", "kitchen scale"]
DETAILS = [
    "left hinge area",
    "inner lid",
    "charging port",
    "front fabric",
    "bottom seam",
    "control switch",
    "handle joint",
    "filter slot",
    "rubber edge",
    "display corner",
    "package insert",
    "side panel",
]

BASE_SIGNALS = {
    "normal_review": [
        "works normally",
        "slow delivery, item usable",
        "color disliked, function correct",
        "minor package crease, no damage",
    ],
    "negative_review": [
        "disappointing but usable",
        "description partly inaccurate",
        "minor flaw affects satisfaction",
        "slow support needs review",
    ],
    "after_sales_risk": [
        "may need after-sales handling",
        "cannot be used as expected",
        "key function unavailable",
        "safety or service risk",
    ],
}

BOUNDARY_SIGNALS = {
    "clear": "clear",
    "normal_negative_boundary": "normal_negative_boundary",
    "negative_after_sales_boundary": "negative_after_sales_boundary",
    "risk_level_contrast": "risk_level_contrast",
    "evidence_conflict_human_review": "evidence_conflict_human_review",
}

SEVERITY_SIGNALS = {
    "low": "low impact",
    "medium": "review needed",
    "high": "urgent handling",
}


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def split_type_level_plan(split: str) -> list[tuple[str, str, bool]]:
    if split in {"validation", "engineering_holdout_v23"}:
        return [
            ("normal_review", "low", False),
            ("normal_review", "low", False),
            ("normal_review", "medium", False),
            ("normal_review", "medium", True),
            ("negative_review", "low", False),
            ("negative_review", "low", True),
            ("negative_review", "medium", True),
            ("negative_review", "high", True),
            ("after_sales_risk", "medium", True),
            ("after_sales_risk", "high", True),
            ("after_sales_risk", "high", True),
            ("after_sales_risk", "high", True),
        ]
    plan: list[tuple[str, str, bool]] = []
    plan += [("normal_review", "low", False)] * 16
    plan += [("normal_review", "medium", False)] * 12
    plan += [("normal_review", "medium", True)] * 4
    plan += [("negative_review", "low", False)] * 8
    plan += [("negative_review", "low", True)] * 8
    plan += [("negative_review", "medium", True)] * 8
    plan += [("negative_review", "high", True)] * 8
    plan += [("after_sales_risk", "medium", True)] * 8
    plan += [("after_sales_risk", "high", True)] * 24
    assert len(plan) == 96
    return plan


def split_category_plan(split: str) -> list[str]:
    if split in {"validation", "engineering_holdout_v23"}:
        return ["clear"] * 4 + ["normal_negative_boundary"] * 2 + ["negative_after_sales_boundary"] * 2 + ["risk_level_contrast"] * 2 + ["evidence_conflict_human_review"] * 2
    return ["clear"] * 28 + ["normal_negative_boundary"] * 20 + ["negative_after_sales_boundary"] * 26 + ["risk_level_contrast"] * 14 + ["evidence_conflict_human_review"] * 8


def group_specs() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    specs: list[dict[str, Any]] = []
    split_order = ["validation", "engineering_holdout_v23", "train"]
    group_index = 0
    for split in split_order:
        labels = split_type_level_plan(split)
        cats = split_category_plan(split)
        assert len(labels) == len(cats)
        paired_waiting: dict[str, str] = {}
        for local_index, ((risk_type, risk_level, need_human), category) in enumerate(zip(labels, cats)):
            generation_root = f"v23_root_{split}_{local_index:03d}"
            group_id = f"v23_group_{group_index:03d}"
            contrast_id = None
            if category != "clear":
                if category in paired_waiting:
                    contrast_id = paired_waiting.pop(category)
                else:
                    contrast_id = f"v23_contrast_{split}_{category}_{local_index:03d}"
                    paired_waiting[category] = contrast_id
            product = rng.choice(PRODUCTS)
            detail = f"d{group_index:03d}"
            specs.append(
                {
                    "split": split,
                    "scenario_group_id": group_id,
                    "generation_root_id": generation_root,
                    "contrast_pair_group_id": contrast_id,
                    "template_instance_id": f"v23_template_{group_index:03d}",
                    "scenario_family_id": category,
                    "risk_type": risk_type,
                    "risk_level": risk_level,
                    "need_human_review": need_human,
                    "product": product,
                    "detail": detail,
                }
            )
            group_index += 1
        assert not paired_waiting
    assert len(specs) == 120
    return specs


def evidence_for(risk_type: str, risk_level: str, category: str, detail: str) -> str:
    if risk_type == "normal_review":
        return f"{detail} ok"
    if risk_type == "negative_review":
        return f"{detail} negative"
    return f"{detail} after_sales"


def route_reason(risk_type: str, risk_level: str, need_human: bool, category: str, group_id: str, surface: str, detail: str) -> str:
    review_part = "hy" if need_human else "hn"
    return f"{risk_type};{risk_level};{review_part};{detail};{surface}"


def make_decision(spec: dict[str, Any], evidence: str, surface: str) -> dict[str, Any]:
    decision = {
        "schema_version": E_REVIEW_DECISION_SCHEMA_VERSION,
        "risk_type": spec["risk_type"],
        "risk_level": spec["risk_level"],
        "text_evidence": [evidence],
        "visual_evidence": [],
        "retrieved_case_evidence": [],
        "need_human_review": bool(spec["need_human_review"]),
        "route_reason": route_reason(spec["risk_type"], spec["risk_level"], bool(spec["need_human_review"]), spec["scenario_family_id"], spec["scenario_group_id"], surface, spec["detail"]),
        "missing_information": ["confirm"] if spec["need_human_review"] and spec["scenario_family_id"] == "evidence_conflict_human_review" else [],
        "unsupported_claims": [],
    }
    validate_canonical_decision(decision)
    return decision


def make_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in group_specs():
        realizer_ids = REALIZER_IDS[:6]
        for variant_index, realizer_id in enumerate(realizer_ids):
            evidence = evidence_for(spec["risk_type"], spec["risk_level"], spec["scenario_family_id"], spec["detail"])
            surface_spec = ScenarioSpec(
                product=spec["product"],
                base_signal=BASE_SIGNALS[spec["risk_type"]][variant_index % len(BASE_SIGNALS[spec["risk_type"]])] + f" {spec['detail']}",
                boundary_signal=BOUNDARY_SIGNALS[spec["scenario_family_id"]],
                severity_signal=SEVERITY_SIGNALS[spec["risk_level"]],
                evidence_signal=evidence,
                risk_type=spec["risk_type"],
                risk_level=spec["risk_level"],
                need_human_review=bool(spec["need_human_review"]),
            )
            review = render_surface(surface_spec, realizer_id, variant_index)
            user = {
                "synthetic_review_text": review,
                "synthetic_rating": 5 if spec["risk_type"] == "normal_review" else (3 if spec["risk_type"] == "negative_review" else 1),
                "synthetic_product_category": spec["product"],
            }
            decision = make_decision(spec, evidence, realizer_id)
            lineage = SyntheticV23Lineage(
                generation_root_id=spec["generation_root_id"],
                scenario_group_id=spec["scenario_group_id"],
                contrast_pair_group_id=spec["contrast_pair_group_id"],
                template_instance_id=spec["template_instance_id"],
                scenario_family_id=spec["scenario_family_id"],
                surface_realizer_id=realizer_id,
                generation_seed=SEED,
            ).as_metadata()
            sample_hash = sha(spec["scenario_group_id"] + realizer_id + compact_json(user) + compact_canonical_serialize(decision))
            rows.append(
                {
                    "system": system_prompt(),
                    "user": compact_json(user),
                    "assistant": compact_canonical_serialize(decision),
                    "metadata": {
                        "dataset_version": DATASET_VERSION,
                        "split": spec["split"],
                        "sample_hash": sample_hash,
                        "risk_type": spec["risk_type"],
                        "risk_level": spec["risk_level"],
                        "need_human_review": bool(spec["need_human_review"]),
                        "lineage": lineage,
                        "source_policy": "abstract_spec_only",
                        "contract_version": E_REVIEW_DECISION_SCHEMA_VERSION,
                        "prompt_version": E_REVIEW_DECISION_PROMPT_VERSION,
                    },
                }
            )
    return rows


def main() -> None:
    DATA_V23.mkdir(parents=True, exist_ok=True)
    rows = make_rows()
    write_jsonl(DATA_V23 / "all_samples.jsonl", rows)
    summary = {
        "generated_at": now(),
        "status": "V23_GENERATION_FROM_ABSTRACT_SPEC_ONLY",
        "seed": SEED,
        "total_count": len(rows),
        "scenario_group_count": len({row["metadata"]["lineage"]["scenario_group_id"] for row in rows}),
        "group_size_distribution": dict(Counter(Counter(row["metadata"]["lineage"]["scenario_group_id"] for row in rows).values())),
        "split_distribution": dict(Counter(row["metadata"]["split"] for row in rows)),
        "risk_type_distribution": dict(Counter(row["metadata"]["risk_type"] for row in rows)),
        "risk_level_distribution": dict(Counter(row["metadata"]["risk_level"] for row in rows)),
        "scenario_family_distribution": dict(Counter(row["metadata"]["lineage"]["scenario_family_id"] for row in rows)),
        "uses_old_text": False,
        "uses_external_test": False,
        "uses_public_pilot": False,
        "uses_real_images": False,
        "uses_amazon_asap": False,
    }
    write_json(AUDIT / "v1612_synthetic_v23_generation_summary.json", summary)
    write_doc(DOCS / "249_v1612_synthetic_v23_generation.md", "V1.6.12 Synthetic V2.3 Generation", [f"Status: `{summary['status']}`", f"- total_count: `{summary['total_count']}`", f"- scenario_group_count: `{summary['scenario_group_count']}`", "- source: abstract scenario specifications only."])
    print(summary["status"])


if __name__ == "__main__":
    main()
