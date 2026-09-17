from __future__ import annotations

from pathlib import Path

from v169_common import AUDIT, DATA_V22, DOCS, percentile, read_jsonl, write_doc, write_json, now


MAX_LENGTH = 384
RECOMMENDED_MAX = 368


def summarize(values: list[int]) -> dict[str, float | int | None]:
    return {
        "p50": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values) if values else None,
        "mean": round(sum(values) / len(values), 4) if values else None,
    }


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    from transformers import AutoTokenizer
    from app.training.completion_only import audit_completion_only_sample, encode_completion_only_sample

    tokenizer = AutoTokenizer.from_pretrained(Path(__file__).resolve().parents[2].parent / "models/Qwen3-1.7B", local_files_only=True, trust_remote_code=True)
    splits = {name: read_jsonl(DATA_V22 / f"{name}.jsonl") for name in ["train", "validation", "engineering_holdout_v21"]}
    rows = [row for split in splits.values() for row in split]
    totals: list[int] = []
    prompts: list[int] = []
    completions: list[int] = []
    trainables: list[int] = []
    audits = []
    for row in rows:
        encoding = encode_completion_only_sample(row, tokenizer, max_length=MAX_LENGTH)
        audit = audit_completion_only_sample(row, tokenizer, max_length=MAX_LENGTH)
        audits.append(audit)
        totals.append(len(encoding.input_ids))
        prompts.append(encoding.prompt_token_count)
        completions.append(encoding.assistant_token_count)
        trainables.append(sum(1 for label in encoding.labels if label != -100))
    total_count = len(rows)
    over_368 = sum(1 for value in totals if value > RECOMMENDED_MAX)
    over_384 = sum(1 for value in totals if value > MAX_LENGTH)
    truncation = sum(1 for item in audits if item["target_truncated"])
    result = {
        "generated_at": now(),
        "status": "V22_TOKEN_BUDGET_DATA_PASS",
        "total_count": total_count,
        "train_count": len(splits["train"]),
        "validation_count": len(splits["validation"]),
        "holdout_count": len(splits["engineering_holdout_v21"]),
        "max_length": MAX_LENGTH,
        "total_tokens": summarize(totals),
        "prompt_tokens": summarize(prompts),
        "completion_tokens": summarize(completions),
        "trainable_tokens": summarize(trainables),
        "over_368_count": over_368,
        "over_384_count": over_384,
        "target_truncation_count": truncation,
        "target_truncation_rate": truncation / total_count,
        "eos_present_rate": sum(item["eos_present"] for item in audits) / total_count,
        "eos_trainable_rate": sum(item["eos_trainable"] for item in audits) / total_count,
        "prompt_mask_rate": min(item["system_user_mask_rate"] for item in audits),
        "completion_trainable_rate": min(item["assistant_trainable_rate"] for item in audits),
        "zero_trainable_sample_count": sum(1 for item in audits if item["assistant_token_count"] == 0),
        "risk_type_token_trainable_rate": sum(item["risk_type_token_participates_loss"] for item in audits) / total_count,
        "risk_level_token_trainable_rate": sum(item["risk_level_token_participates_loss"] for item in audits) / total_count,
        "need_human_review_token_trainable_rate": sum(item["need_human_review_token_participates_loss"] for item in audits) / total_count,
    }
    pass_conditions = [
        over_384 == 0,
        truncation == 0,
        result["eos_present_rate"] == 1.0,
        result["eos_trainable_rate"] == 1.0,
        result["prompt_mask_rate"] == 1.0,
        result["completion_trainable_rate"] == 1.0,
        result["zero_trainable_sample_count"] == 0,
        result["risk_type_token_trainable_rate"] == 1.0,
        result["risk_level_token_trainable_rate"] == 1.0,
        result["need_human_review_token_trainable_rate"] == 1.0,
        over_368 <= max(4, int(total_count * 0.01)),
    ]
    result["status"] = "V22_TOKEN_BUDGET_DATA_PASS" if all(pass_conditions) else "V22_TOKEN_BUDGET_DATA_BLOCKED"
    write_json(AUDIT / "v169_sft_v22_token_audit.json", result)
    write_doc(
        DOCS / "229_v169_sft_v22_dataset.md",
        "V1.6.9 SFT V2.2 Dataset",
        [
            f"Token status: `{result['status']}`",
            f"- total_count: `{total_count}`",
            f"- total P95/P99/max: `{result['total_tokens']['p95']}` / `{result['total_tokens']['p99']}` / `{result['total_tokens']['max']}`",
            f"- over_368_count: `{over_368}`",
            f"- over_384_count: `{over_384}`",
            f"- target_truncation_rate: `{result['target_truncation_rate']}`",
            f"- eos_trainable_rate: `{result['eos_trainable_rate']}`",
        ],
    )
    print(result["status"])


if __name__ == "__main__":
    main()
