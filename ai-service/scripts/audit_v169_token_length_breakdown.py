from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from v169_common import AUDIT, DATA_V21, DOCS, percentile, read_json, read_jsonl, target, write_doc, write_json, now


MAX_LENGTH = 384


def token_count(tokenizer, text: str) -> int:
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


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


def first_truncated(parts: list[tuple[str, int]]) -> str:
    total = 0
    for name, count in parts:
        total += count
        if total > MAX_LENGTH:
            return name
    return "none"


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(Path(__file__).resolve().parents[2].parent / "models/Qwen3-1.7B", local_files_only=True, trust_remote_code=True)
    rows = read_jsonl(DATA_V21 / "train.jsonl") + read_jsonl(DATA_V21 / "validation.jsonl")
    system_counts, user_counts, completion_counts, total_counts = [], [], [], []
    field_counts: dict[str, list[int]] = defaultdict(list)
    first_sources = Counter()
    longest_fields = Counter()
    over = eos_truncated = 0
    for row in rows:
        user = json.loads(row["user"])
        decision = target(row)
        system = row["system"]
        review = str(user.get("synthetic_review_text") or user.get("review_text") or "")
        metadata_payload = {key: value for key, value in user.items() if key not in {"synthetic_review_text", "review_text"}}
        metadata_text = json.dumps(metadata_payload, ensure_ascii=False, sort_keys=True)
        assistant = row["assistant"]
        system_n = token_count(tokenizer, system)
        review_n = token_count(tokenizer, review)
        metadata_n = token_count(tokenizer, metadata_text)
        user_n = token_count(tokenizer, row["user"])
        completion_n = token_count(tokenizer, assistant) + 1
        total = system_n + user_n + completion_n
        system_counts.append(system_n)
        user_counts.append(user_n)
        completion_counts.append(completion_n)
        total_counts.append(total)
        parts = [("system", system_n), ("user", user_n), ("assistant_json", completion_n)]
        if total > MAX_LENGTH:
            over += 1
            first_sources[first_truncated(parts)] += 1
            eos_truncated += 1
        for field, value in decision.items():
            value_text = json.dumps({field: value}, ensure_ascii=False, separators=(",", ":"))
            field_counts[f"{field}_tokens"].append(token_count(tokenizer, value_text))
        longest = max(field_counts, key=lambda k: field_counts[k][-1])
        longest_fields[longest] += 1
    root_cause = "MULTIPLE_CAUSES"
    if first_sources:
        top_source, top_count = first_sources.most_common(1)[0]
        if top_source == "system":
            root_cause = "PROMPT_SYSTEM_TOO_VERBOSE"
        elif top_source == "user":
            root_cause = "USER_SERIALIZATION_TOO_VERBOSE"
        elif top_source == "assistant_json":
            route_p95 = summarize(field_counts.get("route_reason_tokens", []))["p95"] or 0
            evidence_p95 = summarize(field_counts.get("text_evidence_tokens", []))["p95"] or 0
            root_cause = "TARGET_EVIDENCE_TOO_VERBOSE" if evidence_p95 >= route_p95 else "TARGET_ROUTE_REASON_TOO_VERBOSE"
        if top_count / max(1, over) < 0.70:
            root_cause = "MULTIPLE_CAUSES"
    result = {
        "generated_at": now(),
        "status": "V169_TOKEN_LENGTH_BREAKDOWN_COMPLETE",
        "sample_count": len(rows),
        "max_length": MAX_LENGTH,
        "total_tokens": summarize(total_counts),
        "system_tokens": summarize(system_counts),
        "user_tokens": summarize(user_counts),
        "completion_tokens": summarize(completion_counts),
        "field_tokens": {key: summarize(values) for key, values in field_counts.items()},
        "truncated_sample_count": over,
        "truncation_rate": over / len(rows),
        "first_truncated_component_distribution": dict(first_sources),
        "longest_field_distribution": dict(longest_fields),
        "eos_truncated_count": eos_truncated,
        "primary_root_cause": root_cause,
    }
    write_json(AUDIT / "v169_token_length_breakdown.json", result)
    write_doc(
        DOCS / "226_v169_token_length_breakdown.md",
        "V1.6.9 Token Length Breakdown",
        [
            f"Status: `{result['status']}`",
            f"- sample_count: `{result['sample_count']}`",
            f"- original_truncation_rate: `{result['truncation_rate']}`",
            f"- total P95/P99/max: `{result['total_tokens']['p95']}` / `{result['total_tokens']['p99']}` / `{result['total_tokens']['max']}`",
            f"- system P95: `{result['system_tokens']['p95']}`",
            f"- user P95: `{result['user_tokens']['p95']}`",
            f"- completion P95: `{result['completion_tokens']['p95']}`",
            f"- primary_root_cause: `{result['primary_root_cause']}`",
            f"- first_truncated_component_distribution: `{result['first_truncated_component_distribution']}`",
        ],
    )
    block = read_json(AUDIT / "v168_train_validation_data_audit.json")
    freeze = {
        "generated_at": now(),
        "status": "V168_TRUNCATION_BLOCK_RESULT_FROZEN",
        "train_count": block["train_count"],
        "validation_count": block["validation_count"],
        "holdout_count": block["holdout_count"],
        "max_length": MAX_LENGTH,
        "truncation_rate": block["truncation_rate"],
        "eos_trainable_rate": block["eos_trainable_rate"],
        "zero_trainable_sample_count": block["zero_trainable_sample_count"],
        "qlora_budget_executed": False,
        "training_executed": False,
        "holdout_unsealed": False,
        "blocked_reason": "completion_target_truncation",
    }
    write_json(AUDIT / "v168_truncation_block_freeze.json", freeze)
    write_doc(
        DOCS / "225_v169_v168_truncation_block_freeze.md",
        "V1.6.9 V1.6.8 Truncation Block Freeze",
        [f"Status: `{freeze['status']}`", f"- truncation_rate: `{freeze['truncation_rate']}`", f"- eos_trainable_rate: `{freeze['eos_trainable_rate']}`", f"- training_executed: `{freeze['training_executed']}`"],
    )
    print(result["status"])
    print(freeze["status"])


if __name__ == "__main__":
    main()
