from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.prompts.e_review_prompt_renderer import render_training_messages

COMPLETION_ONLY_ENCODING_VERSION = "completion_only_v2.2.0"


@dataclass(frozen=True)
class CompletionOnlyEncoding:
    input_ids: list[int]
    attention_mask: list[int]
    labels: list[int]
    prompt_token_count: int
    assistant_token_count: int
    eos_token_id: int | None
    truncated: bool


def encode_completion_only_sample(sample: dict[str, Any], tokenizer, max_length: int = 384) -> CompletionOnlyEncoding:
    messages = render_training_messages(sample)
    prompt_messages = messages[:2]
    assistant_text = messages[2]["content"]

    try:
        prompt_text = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        prompt_text = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True)

    assistant_ids = tokenizer(assistant_text, add_special_tokens=False)["input_ids"]
    eos_id = tokenizer.eos_token_id
    if eos_id is not None:
        assistant_ids = assistant_ids + [eos_id]

    prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
    full_ids = prompt_ids + assistant_ids
    truncated = len(full_ids) > max_length
    full_ids = full_ids[:max_length]
    prompt_len = min(len(prompt_ids), len(full_ids))
    labels = [-100] * prompt_len + full_ids[prompt_len:]
    labels = labels[: len(full_ids)]
    attention = [1] * len(full_ids)
    return CompletionOnlyEncoding(
        input_ids=full_ids,
        attention_mask=attention,
        labels=labels,
        prompt_token_count=prompt_len,
        assistant_token_count=max(0, len(full_ids) - prompt_len),
        eos_token_id=eos_id,
        truncated=truncated,
    )


def audit_completion_only_sample(sample: dict[str, Any], tokenizer, max_length: int = 384) -> dict[str, Any]:
    encoding = encode_completion_only_sample(sample, tokenizer, max_length=max_length)
    prompt_labels = encoding.labels[: encoding.prompt_token_count]
    assistant_labels = encoding.labels[encoding.prompt_token_count :]
    eos_present = encoding.eos_token_id in encoding.input_ids if encoding.eos_token_id is not None else False
    eos_trainable = False
    if eos_present and encoding.eos_token_id is not None:
        for token, label in zip(encoding.input_ids, encoding.labels):
            if token == encoding.eos_token_id and label == token:
                eos_trainable = True
                break
    decoded_trainable = tokenizer.decode([label for label in encoding.labels if label != -100], skip_special_tokens=False)
    return {
        "total_token_count": len(encoding.input_ids),
        "prompt_token_count": encoding.prompt_token_count,
        "assistant_token_count": encoding.assistant_token_count,
        "system_user_mask_rate": 1.0 if prompt_labels and all(label == -100 for label in prompt_labels) else 0.0,
        "assistant_trainable_rate": (
            sum(1 for label in assistant_labels if label != -100) / len(assistant_labels) if assistant_labels else 0.0
        ),
        "labels_equal_full_input_ids": encoding.labels == encoding.input_ids,
        "eos_present": eos_present,
        "eos_trainable": eos_trainable,
        "target_truncated": encoding.truncated,
        "risk_type_token_participates_loss": "risk_type" in decoded_trainable,
        "risk_level_token_participates_loss": "risk_level" in decoded_trainable,
        "need_human_review_token_participates_loss": "need_human_review" in decoded_trainable,
    }
