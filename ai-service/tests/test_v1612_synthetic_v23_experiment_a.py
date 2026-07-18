import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/private_research/audit"
PRIVATE = ROOT.parent / "data-private/synthetic-sft-v23"
sys.path.insert(0, str(ROOT / "ai-service"))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def target(row):
    return json.loads(row["assistant"])


def test_v1612_generates_120_groups_with_six_samples_each():
    audit = read_json(AUDIT / "v1612_synthetic_v23_dataset_audit.json")
    assert audit["status"] == "PRIVATE_SYNTHETIC_SFT_V23_DATASET_PASS"
    assert audit["total_count"] == 720
    assert audit["scenario_group_count"] == 120
    assert audit["group_size_distribution"] == {"6": 120}


def test_v1612_split_counts_and_class_balance_are_exact():
    audit = read_json(AUDIT / "v1612_synthetic_v23_dataset_audit.json")
    assert audit["train_count"] == 576
    assert audit["validation_count"] == 72
    assert audit["holdout_count"] == 72
    assert audit["validation_risk_type_distribution"] == {"normal_review": 24, "negative_review": 24, "after_sales_risk": 24}
    assert audit["holdout_risk_type_distribution"] == {"normal_review": 24, "negative_review": 24, "after_sales_risk": 24}
    assert audit["validation_risk_level_distribution"] == {"low": 24, "medium": 24, "high": 24}
    assert audit["holdout_risk_level_distribution"] == {"low": 24, "medium": 24, "high": 24}


def test_v1612_lineage_and_contrast_pairs_do_not_cross_split():
    audit = read_json(AUDIT / "v1612_synthetic_v23_dataset_audit.json")
    assert not any(audit["cross_split_exact_duplicate"].values())
    assert not any(audit["cross_split_normalized_duplicate"].values())
    for overlap in audit["cross_split_lineage_overlap"].values():
        assert not any(overlap.values())


def test_v1612_holdout_is_new_and_sealed():
    seal = read_json(AUDIT / "v23_holdout_seal.json")
    audit = read_json(AUDIT / "v1612_synthetic_v23_dataset_audit.json")
    assert seal["status"] == "V23_ENGINEERING_HOLDOUT_SEALED"
    assert seal["count"] == 72
    assert seal["training_access"] is False
    assert seal["prompt_tuning"] is False
    assert seal["model_selection"] is False
    assert seal["repeated_evaluation"] is False
    assert audit["v22_holdout_overlap"] == 0
    assert audit["v164_holdout_overlap"] == 0


def test_v1612_target_template_and_token_objective_gates_pass():
    audit = read_json(AUDIT / "v1612_synthetic_v23_dataset_audit.json")
    token = audit["token_objective"]
    assert audit["target_template_duplicate_rate"] <= 0.15
    assert audit["route_reason_top1_share"] <= 0.10
    assert audit["route_reason_top5_share"] <= 0.35
    assert token["status"] == "V23_SEMANTIC_TOKEN_SIGNAL_PASS"
    assert token["semantic_label_token_ratio"] >= 0.075
    assert token["target_truncation_rate"] == 0.0
    assert token["eos_trainable_rate"] == 1.0
    assert token["max_tokens"] <= 384


def test_v1612_boundary_and_difficult_negative_examples_exist():
    rows = read_jsonl(PRIVATE / "all_samples.jsonl")
    families = {row["metadata"]["lineage"]["scenario_family_id"] for row in rows}
    assert "normal_negative_boundary" in families
    assert "negative_after_sales_boundary" in families
    assert "evidence_conflict_human_review" in families
    texts = [json.loads(row["user"])["synthetic_review_text"].lower() for row in rows]
    assert any("not a random complaint" in text for text in texts)
    assert any("after_sales" in text and "after_sales_risk" in row["assistant"] for text, row in zip(texts, rows))


def test_v1612_experiment_a_changes_only_data():
    controls = read_json(AUDIT / "v1612_experiment_a_controls.json")
    assert controls["status"] == "V23_EXPERIMENT_A_SINGLE_FACTOR_FROZEN"
    assert controls["single_major_factor"] == "synthetic_dataset_v23"
    assert controls["prompt_changed"] is False
    assert controls["contract_changed"] is False
    assert controls["evaluator_changed"] is False
    assert controls["qlora_config_changed"] is False
    assert controls["old_adapter_warm_start"] is False
    assert controls["old_holdout_access"] is False


def test_v1612_external_sources_do_not_enter_training_data():
    audit = read_json(AUDIT / "v1612_synthetic_v23_dataset_audit.json")
    assert audit["amazon_overlap"] == 0
    assert audit["asap_overlap"] == 0
    assert audit["external_test_overlap"] == 0
    assert audit["public_pilot_overlap"] == 0


def test_v1612_fallback_metric_contract_is_preserved():
    from app.evaluation.e_review_task_evaluator import evaluate_e_review_outputs

    gold = [
        {"risk_type": "normal_review", "risk_level": "low", "need_human_review": False},
        {"risk_type": "negative_review", "risk_level": "medium", "need_human_review": True},
    ]
    valid = json.dumps(
        {
            "schema_version": "v2.0.0",
            "risk_type": "normal_review",
            "risk_level": "low",
            "text_evidence": ["ok"],
            "visual_evidence": [],
            "retrieved_case_evidence": [],
            "need_human_review": False,
            "route_reason": "normal low human no",
            "missing_information": [],
            "unsupported_claims": [],
        }
    )
    metrics = evaluate_e_review_outputs([valid, "not json"], gold)
    assert metrics["fallback_prediction_count"] == 1
    assert metrics["abstention_rate"] == 0.5
    assert metrics["coverage_adjusted_accuracy"] == 0.5


def test_v1612_adapter_files_are_not_in_git_dataset_artifacts():
    tracked_like = [path.name for path in PRIVATE.glob("**/*") if path.suffix in {".safetensors", ".bin", ".pt"}]
    assert tracked_like == []
