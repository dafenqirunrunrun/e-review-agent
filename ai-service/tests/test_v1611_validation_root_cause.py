import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/private_research/audit"
sys.path.insert(0, str(ROOT / "ai-service" / "scripts"))

import run_v1611_validation_root_cause_analysis as v1611
from app.evaluation.dataset_access_guard import DatasetAccessViolation, guard_validation_rows
from app.evaluation.e_review_task_evaluator import evaluate_e_review_outputs
from app.evaluation.no_go_root_cause_engine import determine_no_go_root_causes


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validation_row(text: str, sample_hash: str = "h1") -> dict:
    return {
        "user": text,
        "assistant": "{}",
        "metadata": {"split": "validation", "sample_hash": sample_hash},
    }


def write_prediction_fixture(tmp_path: Path, rows: list[dict], manifest_hash: str) -> tuple[Path, Path, Path]:
    pred_file = tmp_path / "predictions.jsonl"
    pred_meta = tmp_path / "predictions_meta.json"
    audit = tmp_path / "audit"
    audit.mkdir()
    lines = []
    for role in ["base", "adapter"]:
        for row in rows:
            lines.append({"model_role": role, "sample_hash": row["metadata"]["sample_hash"], "raw_output": "{}"})
    pred_file.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    pred_meta.write_text(
        json.dumps(
            {
                "validation_manifest_hash": manifest_hash,
                "prompt_version": "v2.1.0",
                "contract_version": "v2.0.0",
                "evaluator_version": "v2.1.0",
                "contains_holdout_sample_hash": False,
            }
        ),
        encoding="utf-8",
    )
    return pred_file, pred_meta, audit


def test_holdout_role_access_is_blocked():
    rows = [{"metadata": {"split": "holdout", "sample_hash": "sealed-1"}}]
    with pytest.raises(DatasetAccessViolation):
        guard_validation_rows(rows)


def test_engineering_holdout_role_cannot_enter_validation_analysis():
    rows = [{"metadata": {"role": "engineering_holdout_v22", "sample_hash": "sealed-2"}}]
    with pytest.raises(DatasetAccessViolation):
        guard_validation_rows(rows)


def test_sealed_sample_hash_cannot_enter_validation_analysis():
    rows = [{"metadata": {"split": "validation", "sample_hash": "sealed-3"}}]
    with pytest.raises(DatasetAccessViolation):
        guard_validation_rows(rows, sealed_holdout_hashes={"sealed-3"})


def test_validation_predictions_are_reused_offline_when_manifest_matches(tmp_path, monkeypatch):
    rows = [validation_row("alpha", "a"), validation_row("beta", "b")]
    pred_file, pred_meta, audit = write_prediction_fixture(tmp_path, rows, v1611.hash_rows(rows))
    monkeypatch.setattr(v1611, "PRED_FILE", pred_file)
    monkeypatch.setattr(v1611, "PRED_META", pred_meta)
    monkeypatch.setattr(v1611, "AUDIT", audit)

    inv = v1611.inventory(rows)

    assert inv["status"] == "VALIDATION_PREDICTIONS_REUSED_OFFLINE"
    assert inv["prediction_count"] == 4
    assert inv["expected_prediction_count"] == 4
    assert inv["model_role_counts"] == {"base": 2, "adapter": 2}


def test_prediction_hash_mismatch_refuses_reuse(tmp_path, monkeypatch):
    rows = [validation_row("alpha", "a"), validation_row("beta", "b")]
    pred_file, pred_meta, audit = write_prediction_fixture(tmp_path, rows, "wrong-hash")
    monkeypatch.setattr(v1611, "PRED_FILE", pred_file)
    monkeypatch.setattr(v1611, "PRED_META", pred_meta)
    monkeypatch.setattr(v1611, "AUDIT", audit)

    inv = v1611.inventory(rows)

    assert inv["status"] == "VALIDATION_PREDICTIONS_REQUIRED_ONCE"
    assert inv["decision_reason"] == "prediction_hash_or_metadata_mismatch"


def test_fallback_counts_as_abstention_and_coverage_adjusted_accuracy_uses_total_denominator():
    gold = [
        {"risk_type": "normal_review", "risk_level": "low", "need_human_review": False},
        {"risk_type": "after_sales_risk", "risk_level": "high", "need_human_review": True},
    ]
    valid = json.dumps(
        {
            "schema_version": "v2.0.0",
            "risk_type": "normal_review",
            "risk_level": "low",
            "need_human_review": False,
            "text_evidence": ["ok"],
            "visual_evidence": [],
            "retrieved_case_evidence": [],
            "route_reason": "normal review",
            "missing_information": [],
            "unsupported_claims": [],
        }
    )

    metrics = evaluate_e_review_outputs([valid, "not json"], gold)

    assert metrics["fallback_prediction_count"] == 1
    assert metrics["abstention_rate"] == 0.5
    assert metrics["coverage_adjusted_accuracy"] == 0.5


def test_class_collapse_detection_flags_single_dominant_prediction():
    ops = [{"risk_type": "normal_review"} for _ in range(9)] + [{"risk_type": "negative_review"}]
    gold = [{"risk_type": "normal_review"}, {"risk_type": "negative_review"}, {"risk_type": "after_sales_risk"}] * 4

    result = v1611.distribution(ops, gold, "adapter")

    assert result["adapter_dominant_class_rate"] == 0.9
    assert result["adapter_missing_class_count"] == 1
    assert result["adapter_classification"] == "CLASS_BIAS"


def test_template_duplicate_rate_calculation_is_deterministic():
    assert v1611.duplicate_rate(["a", "a", "b", "c"]) == 0.25
    assert v1611.duplicate_rate([]) == 0.0


def test_token_objective_ratio_is_recorded_as_weak_alignment():
    token = read_json(AUDIT / "v1611_token_objective_analysis.json")
    assert token["status"] == "SFT_TOKEN_OBJECTIVE_ALIGNMENT_WEAK"
    assert 0 < token["semantic_label_token_ratio"] < 0.1


def test_root_cause_engine_outputs_evidence():
    report = {
        "validation_metrics": read_json(AUDIT / "v1611_validation_metrics.json"),
        "training_curve_analysis": read_json(AUDIT / "v1611_training_curve_analysis.json"),
        "class_distribution_analysis": read_json(AUDIT / "v1611_class_distribution_analysis.json"),
        "target_template_analysis": read_json(AUDIT / "v1611_target_template_analysis.json"),
        "scenario_diversity_analysis": read_json(AUDIT / "v1611_scenario_diversity_analysis.json"),
        "token_objective_analysis": read_json(AUDIT / "v1611_token_objective_analysis.json"),
    }

    causes = determine_no_go_root_causes(report)

    assert causes
    assert all(cause["supporting_metrics"] for cause in causes)
    assert {cause["code"] for cause in causes} >= {
        "ROOT_CAUSE_TARGET_TEMPLATE_OVERFIT",
        "ROOT_CAUSE_SYNTHETIC_SCENARIO_HOMOGENEITY",
    }


def test_v23_design_excludes_old_holdouts_and_external_datasets():
    design = read_json(AUDIT / "v1611_synthetic_v23_design.json")

    assert design["holdout_requirements"]["exclude_v22_holdout"] is True
    assert design["holdout_requirements"]["exclude_v164_holdout"] is True
    assert design["amazon_asap_included"] is False
    assert design["external_test_included"] is False


def test_experiment_matrix_changes_only_one_major_factor_per_round():
    matrix = read_json(AUDIT / "v1611_experiment_matrix.json")

    assert matrix["experiments"]
    assert all("single_major_factor_change" in experiment for experiment in matrix["experiments"])
    assert matrix["experiments"][0]["single_major_factor_change"] == "Synthetic v2.3 data"


def test_external_and_holdout_sources_do_not_enter_build_gate():
    gate = read_json(AUDIT / "v1611_v23_build_gate.json")

    assert gate["status"] == "SYNTHETIC_SFT_V23_BUILD_ALLOWED"
    assert gate["v22_holdout_excluded_from_v23"] is True
    assert "V22_HOLDOUT_EXCLUDED_FROM_V23" in gate["required_gates"]
