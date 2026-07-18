import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data/private_research/audit"
TRAINING = ROOT / "data/private_research/training"
EVAL = ROOT / "data/private_research/eval"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_v168_pretrain_contract_integrity_passes_against_frozen_head():
    result = read_json(AUDIT / "v168_pretrain_contract_integrity.json")
    assert result["status"] == "V168_PRETRAIN_CONTRACT_INTEGRITY_PASS"
    assert result["pass_map"]["contract_hash_consistent"] is True
    assert result["pass_map"]["prompt_renderer_hash_consistent"] is True
    assert result["pass_map"]["evaluator_hash_consistent"] is True
    assert result["pass_map"]["completion_encoder_hash_consistent"] is True
    assert result["pass_map"]["train_manifest_hash_consistent"] is True
    assert result["pass_map"]["validation_manifest_hash_consistent"] is True
    assert result["pass_map"]["holdout_manifest_hash_consistent"] is True


def test_v168_holdout_is_new_generated_and_sealed():
    provenance = read_json(AUDIT / "v168_holdout_provenance.json")
    seal = read_json(AUDIT / "v21_holdout_seal.json")

    assert provenance["status"] == "V21_HOLDOUT_PROVENANCE_PASS"
    assert provenance["holdout_total"] == 24
    assert provenance["newly_generated_count"] == 24
    assert provenance["legacy_count"] == 0
    assert provenance["previous_train_overlap"] == 0
    assert provenance["previous_validation_overlap"] == 0
    assert provenance["previous_holdout_overlap"] == 0
    assert provenance["canary_overlap"] == 0
    assert seal["status"] == "V21_ENGINEERING_HOLDOUT_SEALED"
    assert seal["sealed"] is True
    assert seal["prompt_tuning_allowed"] is False
    assert seal["model_selection_allowed"] is False
    assert seal["repeated_evaluation_allowed"] is False


def test_v168_train_validation_blocks_before_gpu_on_truncation():
    audit = read_json(AUDIT / "v168_train_validation_data_audit.json")
    budget = read_json(AUDIT / "v168_completion_only_qlora_budget.json")
    training = read_json(TRAINING / "v168_v21_training_summary.json")

    assert audit["status"] == "V21_TRAIN_VALIDATION_DATA_BLOCKED"
    assert audit["train_count"] == 336
    assert audit["validation_count"] == 54
    assert audit["truncation_rate"] > 0
    assert audit["eos_trainable_rate"] < 1.0
    assert budget["status"] == "V21_COMPLETION_ONLY_QLORA_BUDGET_NOT_RUN_PRETRAIN_DATA_BLOCKED"
    assert budget["gpu_used"] is False
    assert training["status"] == "PRIVATE_SYNTHETIC_SFT_V21_QLORA_TRAIN_NOT_RUN_PRETRAIN_DATA_BLOCKED"
    assert training["optimizer_step_count"] == 0
    assert training["holdout_read_during_training"] is False


def test_v168_no_holdout_eval_or_adapter_value_gate_when_training_blocked():
    holdout_eval = read_json(EVAL / "v168_v21_holdout_evaluation.json")
    real_text = read_json(EVAL / "v168_v21_real_text_robustness.json")
    value_gate = read_json(AUDIT / "v168_v21_adapter_value_gate.json")

    assert holdout_eval["status"] == "V21_ENGINEERING_HOLDOUT_EVALUATION_NOT_RUN_TRAINING_BLOCKED"
    assert holdout_eval["holdout_unsealed_once"] is False
    assert real_text["status"] == "PRIVATE_REAL_TEXT_V21_ADAPTER_ROBUSTNESS_NOT_RUN_TRAINING_BLOCKED"
    assert value_gate["status"] == "PRIVATE_SYNTHETIC_SFT_V21_ADAPTER_VALUE_GATE_NOT_RUN"
    assert value_gate["default_candidate"] is False


def test_v168_adapter_artifacts_are_not_in_git_tree():
    forbidden_names = {"adapter_config.json", "adapter_model.safetensors", "optimizer.pt", "scheduler.pt", "trainer_state.json"}
    git_files = {path.name for path in ROOT.rglob("*") if ".git" not in path.parts and path.is_file()}
    assert forbidden_names.isdisjoint(git_files)
