import json
import sys
from pathlib import Path

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.contracts.e_review_decision import (
    E_REVIEW_DECISION_SCHEMA_VERSION,
    EReviewDecision,
    RiskLevel,
    RiskType,
    canonical_schema_dict,
    validate_canonical_decision,
)
from app.contracts.e_review_decision_migration import contract_normalization, process_model_output, raw_json_extraction
from app.evaluation.e_review_task_evaluator import evaluate_e_review_outputs
from app.prompts.e_review_prompt_renderer import render_inference_messages, render_training_messages
from app.training.completion_only import audit_completion_only_sample


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "e_review_contract"


def load_json(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_v166_canonical_schema_exports_from_pydantic():
    schema = canonical_schema_dict()
    assert schema["x-schema-version"] == E_REVIEW_DECISION_SCHEMA_VERSION
    assert "risk_type" in schema["properties"]
    assert RiskType.after_sales_risk.value == "after_sales_risk"
    assert RiskLevel.high.value == "high"


def test_v166_canonical_valid_fixtures_pass():
    for name in ["canonical_valid_normal.json", "canonical_valid_negative.json", "canonical_valid_after_sales.json"]:
        assert validate_canonical_decision(load_json(name)).schema_version == E_REVIEW_DECISION_SCHEMA_VERSION


def test_v166_legacy_alias_and_case_migration_do_not_semantically_overwrite():
    alias = contract_normalization(load_json("legacy_alias_valid.json"))
    assert alias.normalization_success is True
    assert alias.semantic_field_changed is False
    assert alias.normalized_prediction["risk_type"] == "negative_review"
    case = contract_normalization(load_json("enum_case_normalizable.json"))
    assert case.normalization_success is True
    assert case.semantic_field_changed is False
    assert case.normalized_prediction["risk_type"] == "normal_review"
    assert case.normalized_prediction["need_human_review"] is False


def test_v166_normalization_does_not_default_missing_semantic_fields():
    result = contract_normalization(load_json("missing_risk_type.json"))
    assert result.normalization_success is False
    assert "risk_type" not in result.normalized_prediction


def test_v166_raw_extraction_cleans_markdown_and_think_only():
    markdown = raw_json_extraction((FIXTURES / "markdown_wrapped_json.txt").read_text(encoding="utf-8"))
    assert markdown.extraction_success is True
    assert "markdown_fence_removed" in markdown.syntax_operations
    think = raw_json_extraction((FIXTURES / "think_then_json.txt").read_text(encoding="utf-8"))
    assert think.extraction_success is True
    assert "think_block_removed" in think.syntax_operations


def test_v166_fallback_is_separate_and_not_prediction_eligible():
    processed = process_model_output((FIXTURES / "operational_fallback_required.txt").read_text(encoding="utf-8"))
    assert processed["prediction_eligible"] is False
    assert processed["abstained"] is True
    assert processed["operational_result"]["prediction_source"] == "operational_safety_fallback"


def test_v166_evaluator_excludes_fallback_from_macro_f1_and_uses_total_denominator():
    gold = [load_json("canonical_valid_normal.json"), load_json("canonical_valid_after_sales.json")]
    raw = [(FIXTURES / "canonical_valid_normal.json").read_text(encoding="utf-8"), "not json"]
    metrics = evaluate_e_review_outputs(raw, gold)
    assert metrics["eligible_prediction_count"] == 1
    assert metrics["fallback_prediction_count"] == 1
    assert metrics["coverage_adjusted_accuracy"] == 0.5
    assert metrics["abstention_rate"] == 0.5


def test_v166_prompt_uses_canonical_fields_without_legacy_names():
    sample = {
        "user": json.dumps({"synthetic_review_text": "synthetic prompt fixture", "synthetic_rating": 5, "synthetic_product_category": "fixture"}),
        "assistant": json.dumps(load_json("canonical_valid_normal.json")),
    }
    train_messages = render_training_messages(sample)
    infer_messages = render_inference_messages({"review_text": "synthetic prompt fixture", "rating": 5})
    assert train_messages[0]["content"] == infer_messages[0]["content"]
    assert "visual_evidence" in train_messages[0]["content"]
    assert "sentiment" not in train_messages[0]["content"]
    assert "Markdown" in train_messages[0]["content"]


class TinyTokenizer:
    eos_token_id = 0

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, enable_thinking=False):
        text = "".join(f"<{m['role']}>{m['content']}" for m in messages)
        if add_generation_prompt:
            text += "<assistant>"
        return text

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(ch) % 251 + 1 for ch in text]}

    def decode(self, ids, skip_special_tokens=False):
        return "".join(chr((i - 1) % 251) for i in ids if i != 0)


def test_v166_completion_only_masks_prompt_and_trains_assistant_and_eos():
    sample = {
        "user": json.dumps({"synthetic_review_text": "synthetic completion fixture", "synthetic_rating": 1}),
        "assistant": json.dumps(load_json("canonical_valid_after_sales.json")),
    }
    audit = audit_completion_only_sample(sample, TinyTokenizer(), max_length=10000)
    assert audit["system_user_mask_rate"] == 1.0
    assert audit["assistant_trainable_rate"] == 1.0
    assert audit["labels_equal_full_input_ids"] is False
    assert audit["eos_present"] is True
    assert audit["eos_trainable"] is True
    assert audit["target_truncated"] is False
