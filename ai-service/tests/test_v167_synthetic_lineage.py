import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/private_research/audit"


def read_json(name):
    return json.loads((AUDIT / name).read_text(encoding="utf-8"))


def test_v167_lineage_audit_preserves_p0_as_local_sequence():
    audit = read_json("v167_synthetic_lineage_audit.json")

    assert audit["status"] == "SYNTHETIC_LINEAGE_AUDIT_PASS"
    assert list(audit["field_value_counts"]["paraphrase_family"]) == ["p0"]
    assert audit["field_classification"]["paraphrase_family"]["lineage_role"] == "local_sequence_number"
    assert "must be composed" in audit["field_classification"]["paraphrase_family"]["split_constraint"]
    assert audit["field_classification"]["template_family"]["lineage_role"] == "hard_leakage_group"


def test_v167_split_excludes_old_holdout_and_covers_required_labels():
    split = read_json("v167_synthetic_sft_v21_summary.json")

    assert split["status"] == "PRIVATE_SYNTHETIC_SFT_V21_DATASET_PASS"
    assert split["train_count"] == 336
    assert split["validation_count"] == 54
    assert split["holdout_count"] == 24
    assert set(split["risk_type_distribution"]["validation"]) == {
        "normal_review",
        "negative_review",
        "after_sales_risk",
    }
    assert set(split["risk_type_distribution"]["engineering_holdout_v21"]) == {
        "normal_review",
        "negative_review",
        "after_sales_risk",
    }
    assert set(split["risk_level_distribution"]["validation"]) == {"low", "medium", "high"}
    assert set(split["risk_level_distribution"]["engineering_holdout_v21"]) == {"low", "medium", "high"}


def test_v167_split_has_no_cross_split_or_external_overlap():
    split = read_json("v167_synthetic_sft_v21_summary.json")

    assert not any(split["cross_split_exact_duplicate"].values())
    assert not any(split["cross_split_normalized_duplicate"].values())
    assert not any(split["cross_split_composite_lineage_overlap"].values())
    assert split["public_pilot_overlap"] == 0
    assert split["amazon_overlap"] == 0
    assert split["asap_overlap"] == 0
    assert split["external_test_overlap"] == 0
    assert split["v164_prediction_overlap"] == 0


def test_v167_canary_and_freeze_do_not_use_old_holdout_or_adapter():
    canary = read_json("v167_base_prompt_canary.json")
    freeze = read_json("v167_training_contract_freeze.json")

    assert canary["status"] == "V167_BASE_PROMPT_CONTRACT_CANARY_PASS"
    assert canary["holdout_read"] is False
    assert canary["old_adapter_used"] is False
    assert canary["real_inference_count"] == canary["sample_count"] == 12
    assert freeze["status"] == "SYNTHETIC_SFT_V21_CONTRACT_FROZEN"
    assert freeze["sft_v21_rebuild_status"] == "SYNTHETIC_SFT_V21_REBUILD_ALLOWED"
    assert freeze["contract_version"] == "v2.0.0"
    assert freeze["prompt_version"] == "v2.0.0"
