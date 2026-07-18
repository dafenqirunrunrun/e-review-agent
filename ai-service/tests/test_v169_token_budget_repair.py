import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))
AUDIT = ROOT / "data/private_research/audit"
TRAINING = ROOT / "data/private_research/training"
EVAL = ROOT / "data/private_research/eval"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_prompt_v21_keeps_contract_fields_enums_and_safety_boundaries():
    from app.contracts.e_review_decision import E_REVIEW_DECISION_PROMPT_VERSION, RiskLevel, RiskType, canonical_field_order
    from app.prompts.e_review_decision_prompt import system_prompt
    from app.prompts.e_review_prompt_renderer import E_REVIEW_PROMPT_RENDERER_VERSION

    prompt = system_prompt()
    assert E_REVIEW_DECISION_PROMPT_VERSION == "v2.1.0"
    assert E_REVIEW_PROMPT_RENDERER_VERSION == "v2.1.0"
    for field in canonical_field_order():
        assert field in prompt
    for item in RiskType:
        assert item.value in prompt
    for item in RiskLevel:
        assert item.value in prompt
    for boundary in ["JSON", "Markdown", "think", "refund", "ban", "compensation", "input echo"]:
        assert boundary in prompt


def test_v22_token_budget_passes_without_expanding_max_length():
    token = read_json(AUDIT / "v169_sft_v22_token_audit.json")

    assert token["status"] == "V22_TOKEN_BUDGET_DATA_PASS"
    assert token["max_length"] == 384
    assert token["over_384_count"] == 0
    assert token["target_truncation_count"] == 0
    assert token["eos_present_rate"] == 1.0
    assert token["eos_trainable_rate"] == 1.0
    assert token["prompt_mask_rate"] == 1.0
    assert token["completion_trainable_rate"] == 1.0
    assert token["zero_trainable_sample_count"] == 0


def test_v22_dataset_preserves_identity_lineage_and_core_labels():
    dataset = read_json(AUDIT / "v169_sft_v22_dataset_audit.json")

    assert dataset["status"] == "PRIVATE_SYNTHETIC_SFT_V22_DATASET_PASS"
    assert dataset["total_count"] == 414
    assert dataset["train_count"] == 336
    assert dataset["validation_count"] == 54
    assert dataset["holdout_count"] == 24
    assert dataset["identity_change_count"] == 0
    assert dataset["split_identity_change_count"] == 0
    assert dataset["lineage_change_count"] == 0
    assert dataset["core_label_change_count"] == 0
    assert dataset["evidence_support_rate"] == 1.0
    assert not any(dataset["cross_split_lineage_overlap"].values())


def test_v22_holdout_is_resealed_and_not_evaluated_after_blocked_training():
    seal = read_json(AUDIT / "v22_holdout_seal.json")
    holdout_eval = read_json(EVAL / "v169_v22_holdout_evaluation.json")

    assert seal["status"] == "V22_ENGINEERING_HOLDOUT_SEALED"
    assert seal["training_access_allowed"] is False
    assert seal["prompt_tuning_allowed"] is False
    assert seal["model_selection_allowed"] is False
    assert seal["repeated_evaluation_allowed"] is False
    assert holdout_eval["status"] == "V22_ENGINEERING_HOLDOUT_EVALUATION_NOT_RUN_TRAINING_BLOCKED"
    assert holdout_eval["holdout_unsealed_once"] is False


def test_v22_budget_passed_but_training_stopped_on_memory_gate_without_eval():
    budget = read_json(AUDIT / "v169_v22_qlora_budget.json")
    training = read_json(TRAINING / "v169_v22_training_summary.json")
    gate = read_json(AUDIT / "v169_v22_adapter_value_gate.json")

    assert budget["status"] == "V22_COMPLETION_ONLY_QLORA_BUDGET_PASS"
    assert budget["total_tokens"] <= 384
    assert budget["prompt_labels_masked"] is True
    assert budget["completion_labels_trainable"] is True
    assert budget["eos_trainable"] is True
    assert training["status"] == "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_BLOCKED"
    assert training["new_adapter_initialized_from_base"] is True
    assert training["old_adapter_loaded"] is False
    assert training["optimizer_step_count"] < training["optimizer_steps_planned"]
    assert training["error_sanitized"] == "free memory below 200MB"
    assert gate["status"] == "PRIVATE_SYNTHETIC_SFT_V22_ADAPTER_VALUE_GATE_NOT_RUN"
    assert gate["default_candidate"] is False


def test_v169_adapter_artifacts_are_not_in_git_tree():
    forbidden = {"adapter_config.json", "adapter_model.safetensors", "optimizer.pt", "scheduler.pt", "trainer_state.json"}
    files = {path.name for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts}
    assert forbidden.isdisjoint(files)
