from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from collections import Counter
from pathlib import Path

from v169_common import AUDIT, DOCS, MODEL_DIR, PRIVATE_ROOT, now, read_json, read_jsonl, target, write_doc, write_json

DATA_V23 = PRIVATE_ROOT / "synthetic-sft-v23"


def select_rows(rows: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {"normal_review": [], "negative_review": [], "after_sales_risk": []}
    for row in rows:
        buckets[target(row)["risk_type"]].append(row)
    selected = []
    for key in ["normal_review", "negative_review", "after_sales_risk"]:
        selected.extend(sorted(buckets[key], key=lambda row: hashlib.sha256(row["user"].encode("utf-8")).hexdigest())[:6])
    return selected


def generate(model, tokenizer, rows: list[dict]) -> tuple[list[str], list[float]]:
    import torch
    from app.prompts.e_review_prompt_renderer import render_generation_prompt

    outputs, latencies = [], []
    device = next(model.parameters()).device
    for row in rows:
        prompt = render_generation_prompt(json.loads(row["user"]), tokenizer)
        inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=384)
        input_len = int(inputs["input_ids"].shape[-1])
        inputs = {key: value.to(device) for key, value in inputs.items()}
        started = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=160, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        latencies.append((time.perf_counter() - started) * 1000)
        outputs.append(tokenizer.decode(generated[0][input_len:], skip_special_tokens=True).strip())
        del generated, inputs
    return outputs, latencies


def main() -> None:
    import gc
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from app.contracts.e_review_decision_migration import process_model_output
    from app.runtime.gpu_gate import gpu_exclusive_gate

    dataset_gate = read_json(AUDIT / "v1612_synthetic_v23_dataset_audit.json")
    seal = read_json(AUDIT / "v23_holdout_seal.json")
    result = {"generated_at": now(), "status": "V23_BASE_DATA_CANARY_BLOCKED", "holdout_read": False, "old_adapter_used": False, "real_inference_count": 0}
    if dataset_gate["status"] != "PRIVATE_SYNTHETIC_SFT_V23_DATASET_PASS" or seal["status"] != "V23_ENGINEERING_HOLDOUT_SEALED":
        result["blocked_reason"] = "v23 data or holdout seal did not pass"
        write(result)
        print(result["status"])
        return
    rows = select_rows(read_jsonl(DATA_V23 / "validation.jsonl"))
    outputs: list[str] = []
    latencies: list[float] = []
    oom = 0
    try:
        with gpu_exclusive_gate(stage="v1612-v23-base-data-canary", min_free_memory_mb=5200, check_interval_seconds=10, stable_checks=2, timeout_seconds=600, gpu_gate_mode="wddm-aware", max_wddm_total_utilization=60, max_free_memory_drop_mb=256, require_zero_numeric_compute_processes=True, allow_wddm_graphics_activity=True):
            tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
            qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
            dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
            model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, **{dtype_key: torch.bfloat16})
            model.eval()
            outputs, latencies = generate(model, tokenizer, rows)
            del model, tokenizer
            gc.collect()
            torch.cuda.empty_cache()
    except torch.cuda.OutOfMemoryError:
        oom = 1
    processed = [process_model_output(raw) for raw in outputs]
    eligible = [item["prediction_eligible"] for item in processed]
    operational = [item["operational_result"] for item in processed]
    extraction = [item["raw_json_extraction"].extraction_success for item in processed]
    n = max(1, len(outputs))
    result.update(
        {
            "real_inference_count": len(outputs),
            "sample_count": len(rows),
            "raw_schema_valid_rate": sum(eligible) / n,
            "task_coverage_rate": sum(eligible) / n,
            "fallback_rate": sum(1 for item in operational if item.get("prediction_source") == "operational_safety_fallback") / n,
            "raw_json_object_extract_rate": sum(extraction) / n,
            "input_echo_rate": sum(1 for raw in outputs if "synthetic_review_text" in raw or "review:" in raw) / n,
            "prohibited_action_count": sum(1 for raw in outputs if any(term in raw.lower() for term in ["automatic refund", "auto refund", "automatic ban", "auto ban"])),
            "oom_count": oom,
            "avg_generate_ms": round(statistics.mean(latencies), 2) if latencies else None,
            "p95_generate_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else None,
            "output_source_distribution": dict(Counter(item.get("prediction_source", "raw_or_normalized") for item in operational)),
        }
    )
    passed = len(outputs) == 18 and result["raw_schema_valid_rate"] > 0 and result["task_coverage_rate"] >= 0.70 and result["fallback_rate"] <= 0.30 and result["prohibited_action_count"] == 0 and oom == 0
    result["status"] = "V23_BASE_DATA_CANARY_PASS" if passed else "V23_BASE_DATA_CANARY_BLOCKED"
    write(result)
    print(result["status"])


def write(result: dict) -> None:
    write_json(AUDIT / "v1612_base_data_canary.json", result)
    write_doc(DOCS / "253_v1612_base_data_canary.md", "V1.6.12 Base Data Canary", [f"Status: `{result['status']}`", f"- real_inference_count: `{result.get('real_inference_count')}`", f"- task_coverage_rate: `{result.get('task_coverage_rate')}`", f"- fallback_rate: `{result.get('fallback_rate')}`", f"- oom_count: `{result.get('oom_count')}`"])


if __name__ == "__main__":
    main()
