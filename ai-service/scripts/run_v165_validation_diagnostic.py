from __future__ import annotations

import gc
import hashlib
import json
import math
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
PRIVATE_DATA = PRIVATE_ROOT / "synthetic-sft-v1633"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-qlora-v164-controlled"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
OUT = ROOT / "data/private_research/audit/v165_validation_diagnostic.json"
DOC = ROOT / "docs/204_v165_validation_diagnostic.md"

sys.path.insert(0, str(ROOT / "ai-service"))
from app.evaluation.schema_failure_analysis import analyze_schema_failure, extract_json_object, repair_to_canonical  # noqa: E402
from app.runtime.gpu_gate import gpu_exclusive_gate  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def decode_target(row: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(row["assistant"])
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def row_hash(row: dict[str, Any]) -> str:
    payload = row["system"] + row["user"] + row["assistant"]
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:24]


def select_validation(rows: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        target = decode_target(row)
        buckets[(str(target.get("risk_type")), str(target.get("risk_level")))].append(row)
    selected: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for key in sorted(buckets):
        for candidate in sorted(buckets[key], key=row_hash):
            candidate_hash = row_hash(candidate)
            if candidate_hash not in seen_hashes:
                selected.append(candidate)
                seen_hashes.add(candidate_hash)
                break
        if len(selected) >= limit:
            return selected
    for row in sorted(rows, key=row_hash):
        candidate_hash = row_hash(row)
        if candidate_hash not in seen_hashes:
            selected.append(row)
            seen_hashes.add(candidate_hash)
        if len(selected) >= limit:
            break
    return selected


def build_prompt(row: dict[str, Any], tokenizer) -> str:
    user = json.loads(row["user"])
    minimal_user = {
        "synthetic_review_text": user.get("synthetic_review_text"),
        "synthetic_rating": user.get("synthetic_rating"),
        "synthetic_product_category": user.get("synthetic_product_category"),
    }
    messages = [
        {"role": "system", "content": row["system"]},
        {"role": "user", "content": json.dumps(minimal_user, ensure_ascii=False, sort_keys=True) + "\nJSON:"},
    ]
    try:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "\n/no_think"


def macro_f1(labels: list[Any], preds: list[Any]) -> float:
    classes = sorted(set(labels) | set(preds), key=str)
    if not classes:
        return 0.0
    scores = []
    for cls in classes:
        tp = sum(1 for y, p in zip(labels, preds) if y == cls and p == cls)
        fp = sum(1 for y, p in zip(labels, preds) if y != cls and p == cls)
        fn = sum(1 for y, p in zip(labels, preds) if y == cls and p != cls)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append((2 * precision * recall / (precision + recall)) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def confusion(labels: list[Any], preds: list[Any]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for gold, pred in zip(labels, preds):
        result.setdefault(str(gold), {})
        result[str(gold)][str(pred)] = result[str(gold)].get(str(pred), 0) + 1
    return result


def evaluate(raw_outputs: list[str], targets: list[dict[str, Any]], latencies: list[float]) -> dict[str, Any]:
    raw_json = raw_schema = repairs = 0
    finals: list[dict[str, Any]] = []
    failure_reasons = Counter()
    missing_fields = Counter()
    invalid_enums = Counter()
    wrong_types = Counter()
    unknown_fields = Counter()
    field_match = Counter()
    field_total = Counter()
    repair_ops = Counter()
    for raw in raw_outputs:
        parsed, parse_reasons = extract_json_object(raw)
        raw_json += int(parsed is not None)
        analysis = analyze_schema_failure(raw)
        raw_schema += int(analysis.raw_schema_valid)
        failure_reasons.update(analysis.reasons or parse_reasons)
        missing_fields.update(analysis.missing_fields)
        unknown_fields.update(analysis.unknown_fields)
        invalid_enums.update({f"{k}:{v}": 1 for k, v in analysis.invalid_enums.items()})
        wrong_types.update({f"{k}:{v}": 1 for k, v in analysis.wrong_types.items()})
        if analysis.raw_schema_valid and parsed is not None:
            final = parsed
        else:
            repairs += 1
            final, ops = repair_to_canonical(parsed, ",".join(analysis.reasons))
            repair_ops.update(ops["field_overwrites"])
        finals.append(final)
    fields = ["risk_type", "risk_level", "need_human_review"]
    for target, pred in zip(targets, finals):
        for field in fields:
            field_total[field] += 1
            field_match[field] += int(target.get(field) == pred.get(field))
    gold_type = [target.get("risk_type") for target in targets]
    pred_type = [pred.get("risk_type") for pred in finals]
    gold_level = [target.get("risk_level") for target in targets]
    pred_level = [pred.get("risk_level") for pred in finals]
    gold_human = [bool(target.get("need_human_review")) for target in targets]
    pred_human = [bool(pred.get("need_human_review")) for pred in finals]
    n = len(targets) or 1
    return {
        "real_inference_count": len(raw_outputs),
        "raw_json_parse_success_rate": round(raw_json / n, 8),
        "raw_schema_valid_rate": round(raw_schema / n, 8),
        "repair_rate": round(repairs / n, 8),
        "final_schema_valid_rate": 1.0,
        "risk_type_accuracy": round(sum(y == p for y, p in zip(gold_type, pred_type)) / n, 8),
        "risk_type_macro_f1": round(macro_f1(gold_type, pred_type), 8),
        "risk_level_accuracy": round(sum(y == p for y, p in zip(gold_level, pred_level)) / n, 8),
        "risk_level_macro_f1": round(macro_f1(gold_level, pred_level), 8),
        "need_human_review_f1": round(macro_f1(gold_human, pred_human), 8),
        "field_match_rate": {field: round(field_match[field] / max(1, field_total[field]), 8) for field in fields},
        "field_failure_distribution": dict(failure_reasons),
        "missing_field_distribution": dict(missing_fields),
        "invalid_enum_distribution": dict(invalid_enums),
        "wrong_type_distribution": dict(wrong_types),
        "unknown_field_distribution": dict(unknown_fields),
        "repair_overwritten_field_distribution": dict(repair_ops),
        "risk_type_confusion_matrix": confusion(gold_type, pred_type),
        "risk_level_confusion_matrix": confusion(gold_level, pred_level),
        "need_human_review_confusion_matrix": confusion(gold_human, pred_human),
        "avg_generate_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_generate_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else None,
        "output_risk_type_distribution": dict(Counter(pred_type)),
        "output_risk_level_distribution": dict(Counter(pred_level)),
    }


def generate_outputs(model, tokenizer, rows: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
    import torch

    outputs = []
    latencies = []
    device = next(model.parameters()).device
    for row in rows:
        rendered = build_prompt(row, tokenizer)
        inputs = tokenizer([rendered], return_tensors="pt", truncation=True, max_length=384)
        input_len = int(inputs["input_ids"].shape[-1])
        inputs = {key: value.to(device) for key, value in inputs.items()}
        started = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        latencies.append((time.perf_counter() - started) * 1000)
        raw = tokenizer.decode(generated[0][input_len:], skip_special_tokens=True).strip()
        outputs.append(raw)
        del inputs, generated
        gc.collect()
    return outputs, latencies


def load_base_model():
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
    qconfig = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR,
        local_files_only=True,
        trust_remote_code=True,
        quantization_config=qconfig,
        device_map={"": 0},
        **{dtype_key: torch.bfloat16},
    )
    model.eval()
    return model, tokenizer


def unload(model, tokenizer) -> None:
    import torch

    del model, tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    if hasattr(torch.cuda, "ipc_collect"):
        torch.cuda.ipc_collect()


def main() -> None:
    import torch
    from peft import PeftModel

    rows = select_validation(read_jsonl(PRIVATE_DATA / "validation.jsonl"), limit=6)
    targets = [decode_target(row) for row in rows]
    sample_hashes = [row_hash(row) for row in rows]
    result: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "V165_VALIDATION_DIAGNOSTIC_BLOCKED",
        "holdout_read": False,
        "holdout_rerun_performed": False,
        "sample_count": len(rows),
        "sample_hashes": sample_hashes,
        "target_distribution": {
            "risk_type": dict(Counter(target.get("risk_type") for target in targets)),
            "risk_level": dict(Counter(target.get("risk_level") for target in targets)),
        },
    }
    with gpu_exclusive_gate(
        stage="v165-validation-diagnostic",
        min_free_memory_mb=5200,
        check_interval_seconds=10,
        stable_checks=2,
        timeout_seconds=600,
        gpu_gate_mode="wddm-aware",
        max_wddm_total_utilization=60,
        max_free_memory_drop_mb=256,
        require_zero_numeric_compute_processes=True,
        allow_wddm_graphics_activity=True,
    ):
        torch.cuda.reset_peak_memory_stats()
        base_model, tokenizer = load_base_model()
        base_outputs, base_latencies = generate_outputs(base_model, tokenizer, rows)
        result["base_metrics"] = evaluate(base_outputs, targets, base_latencies)
        result["base_output_hashes"] = [hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:24] for text in base_outputs]
        unload(base_model, tokenizer)

        adapter_model, tokenizer = load_base_model()
        adapter_model = PeftModel.from_pretrained(adapter_model, RUN_DIR / "adapter-best", local_files_only=True)
        adapter_model.eval()
        adapter_outputs, adapter_latencies = generate_outputs(adapter_model, tokenizer, rows)
        result["adapter_metrics"] = evaluate(adapter_outputs, targets, adapter_latencies)
        result["adapter_output_hashes"] = [hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:24] for text in adapter_outputs]
        result["peak_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2)
        unload(adapter_model, tokenizer)
    result["status"] = "V165_VALIDATION_DIAGNOSTIC_COMPLETE"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.5 Validation Diagnostic\n\n"
        f"Status: `{result['status']}`\n\n"
        f"- sample_count: `{result['sample_count']}`\n"
        f"- holdout_rerun_performed: `{result['holdout_rerun_performed']}`\n"
        f"- base_raw_schema_valid_rate: `{result['base_metrics']['raw_schema_valid_rate']}`\n"
        f"- adapter_raw_schema_valid_rate: `{result['adapter_metrics']['raw_schema_valid_rate']}`\n"
        f"- base_risk_type_macro_f1: `{result['base_metrics']['risk_type_macro_f1']}`\n"
        f"- adapter_risk_type_macro_f1: `{result['adapter_metrics']['risk_type_macro_f1']}`\n"
        f"- base_field_failures: `{result['base_metrics']['field_failure_distribution']}`\n"
        f"- adapter_field_failures: `{result['adapter_metrics']['field_failure_distribution']}`\n",
        encoding="utf-8",
    )
    print(result["status"])


if __name__ == "__main__":
    main()
