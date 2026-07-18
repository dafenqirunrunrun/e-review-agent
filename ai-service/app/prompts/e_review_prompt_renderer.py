from __future__ import annotations

import json
from typing import Any

from app.contracts.e_review_decision import EReviewDecision, canonical_serialize
from app.prompts.e_review_decision_prompt import generation_instruction, prompt_metadata, system_prompt

E_REVIEW_PROMPT_RENDERER_VERSION = "v2.1.0"


def render_user_content(input_record: dict[str, Any]) -> str:
    review = input_record.get("review_text") or input_record.get("synthetic_review_text") or ""
    rating = input_record.get("rating", input_record.get("synthetic_rating", ""))
    category = input_record.get("product_category") or input_record.get("synthetic_product_category") or "unknown"
    case_summary = input_record.get("retrieved_case_summary") or input_record.get("synthetic_retrieved_case_summary") or ""
    parts = [
        f"review: {review}",
        f"rating: {rating}",
        f"category: {category}",
    ]
    if case_summary:
        parts.append(f"case: {case_summary}")
    return "\n".join(parts) + "\n" + generation_instruction()


def render_training_messages(sample: dict[str, Any]) -> list[dict[str, str]]:
    user = json.loads(sample["user"]) if isinstance(sample.get("user"), str) else dict(sample.get("user") or {})
    assistant = json.loads(sample["assistant"]) if isinstance(sample.get("assistant"), str) else dict(sample.get("assistant") or {})
    decision = EReviewDecision.model_validate(assistant)
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": render_user_content(user)},
        {"role": "assistant", "content": canonical_serialize(decision)},
    ]


def render_inference_messages(input_record: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": render_user_content(input_record)},
    ]


def render_generation_prompt(input_record: dict[str, Any], tokenizer) -> str:
    messages = render_inference_messages(input_record)
    try:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def prompt_alignment_metadata() -> dict[str, Any]:
    return {**prompt_metadata(), "renderer": "app.prompts.e_review_prompt_renderer", "renderer_version": E_REVIEW_PROMPT_RENDERER_VERSION}
