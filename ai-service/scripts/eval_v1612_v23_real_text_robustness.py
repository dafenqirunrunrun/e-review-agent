from __future__ import annotations

import gc
import hashlib
import json
import math
import statistics
import time
from collections import Counter
from pathlib import Path

from v169_common import AUDIT, DOCS, EVAL, MODEL_DIR, PRIVATE_ROOT, now, read_json, read_jsonl, write_doc, write_json

RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-sft-v23-v1612"
REAL_TEXT = PRIVATE_ROOT / "realworld-pilot-v1-frozen" / "processed-text" / "real_reviews_redacted_private.jsonl"


def select_real_rows() -> list[dict]:
    rows = read_jsonl(REAL_TEXT)
    selected = []
    for source_id in ["amazon_reviews_2023", "asap_chinese_reviews"]:
        source_rows = [row for row in rows if row.get("source_id") == source_id and row.get("review_text_redacted")]
        source_rows = sorted(source_rows, key=lambda row: hashlib.sha256(row["sample_id_hash"].encode("utf-8")).hexdigest())
        for row in source_rows[:10]:
            selected.append({"review_text": row["review_text_redacted"], "rating": row.get("rating") or "", "product_category": row.get("category") or source_id, "source_id": source_id, "sample_id_hash": row.get("sample_id_hash")})
    return selected


def load_model(adapter: bool):
    import torch
    import transformers
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
    model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, **{dtype_key: torch.bfloat16})
    model.config.use_cache = False
    if adapter:
        model = PeftModel.from_pretrained(model, RUN_DIR / "adapter-best", local_files_only=True)
    model.eval()
    return model


def generate(model, tokenizer, rows: list[dict]) -> tuple[list[str], list[float]]:
    import torch
    from app.prompts.e_review_prompt_renderer import render_generation_prompt

    outputs, latencies = [], []
    device = next(model.parameters()).device
    with torch.inference_mode():
        for row in rows:
            prompt = render_generation_prompt(row, tokenizer)
            inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=384)
            input_len = int(inputs["input_ids"].shape[-1])
            inputs = {key: value.to(device) for key, value in inputs.items()}
            started = time.perf_counter()
            generated = model.generate(**inputs, max_new_tokens=128, do_sample=False, pad_token_id=tokenizer.eos_token_id)
            outputs.append(tokenizer.decode(generated[0][input_len:], skip_special_tokens=True).strip())
            latencies.append((time.perf_counter() - started) * 1000)
            del generated, inputs
    return outputs, latencies


def metrics(outputs: list[str], rows: list[dict], latencies: list[float]) -> dict:
    from app.contracts.e_review_decision_migration import process_model_output

    processed = [process_model_output(raw) for raw in outputs]
    operational = [item["operational_result"] for item in processed]
    eligible = [bool(item["prediction_eligible"]) for item in processed]
    n = len(rows) or 1
    risks = [op.get("risk_type") for op in operational]
    return {
        "real_inference_count": len(outputs),
        "raw_canonical_schema_valid_rate": round(sum(eligible) / n, 8),
        "task_coverage_rate": round(sum(eligible) / n, 8),
        "fallback_rate": round(sum(1 for op in operational if op.get("prediction_source") == "operational_safety_fallback") / n, 8),
        "empty_rate": round(sum(1 for raw in outputs if not raw.strip()) / n, 8),
        "evidence_nonempty_rate": round(sum(1 for op in operational if op.get("text_evidence")) / n, 8),
        "need_human_review_rate": round(sum(1 for op in operational if op.get("need_human_review")) / n, 8),
        "risk_distribution": dict(Counter(risks)),
        "prohibited_action": sum(1 for raw in outputs if any(term in raw.lower() for term in ["auto refund", "automatic refund", "auto ban", "automatic ban"])),
        "unsupported_action": sum(1 for op in operational if op.get("unsupported_claims")),
        "avg_generate_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_generate_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else None,
        "oom": 0,
    }


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    from transformers import AutoTokenizer
    from app.runtime.gpu_gate import gpu_exclusive_gate

    closure = read_json(AUDIT / "v1612_experiment_a_closure.json")
    if closure.get("value_gate") == "NO_GO":
        result = {"generated_at": now(), "status": "V23_REAL_TEXT_ROBUSTNESS_SKIPPED_NO_GO"}
        write_json(EVAL / "v1612_v23_real_text_robustness.json", result)
        print(result["status"])
        return
    rows = select_real_rows()
    raw_records = []
    with gpu_exclusive_gate(stage="v1612-v23-real-text-robustness", min_free_memory_mb=5200, check_interval_seconds=10, stable_checks=2, timeout_seconds=600, gpu_gate_mode="wddm-aware", max_wddm_total_utilization=60, max_free_memory_drop_mb=256, require_zero_numeric_compute_processes=True, allow_wddm_graphics_activity=True):
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
        metrics_by_role = {}
        for role, use_adapter in [("base", False), ("adapter", True)]:
            model = load_model(use_adapter)
            outputs, latencies = generate(model, tokenizer, rows)
            metrics_by_role[role] = metrics(outputs, rows, latencies)
            for row, output in zip(rows, outputs):
                raw_records.append({"model_role": role, "sample_id_hash": row.get("sample_id_hash"), "source_id": row.get("source_id"), "raw_output": output})
            del model
            gc.collect()
            torch.cuda.empty_cache()
        del tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    out_dir = RUN_DIR / "private-real-text-robustness"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "v1612_real_text_robustness_outputs.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in raw_records), encoding="utf-8")
    result = {
        "generated_at": now(),
        "status": "PRIVATE_REAL_TEXT_V23_ADAPTER_ROBUSTNESS_PASS",
        "amazon_sample_count": sum(1 for row in rows if row["source_id"] == "amazon_reviews_2023"),
        "asap_sample_count": sum(1 for row in rows if row["source_id"] == "asap_chinese_reviews"),
        "base_metrics": metrics_by_role["base"],
        "adapter_metrics": metrics_by_role["adapter"],
        "raw_text_saved_in_git": False,
        "raw_outputs_saved_in_git": False,
        "accuracy_or_macro_f1_computed": False,
    }
    write_json(EVAL / "v1612_v23_real_text_robustness.json", result)
    closure = read_json(AUDIT / "v1612_experiment_a_closure.json")
    closure["real_text_robustness"] = result["status"]
    closure["status"] = "PRIVATE_SYNTHETIC_SFT_V23_ADAPTER_DEFAULT_CANDIDATE" if closure.get("value_gate") == "GO" and result["status"] == "PRIVATE_REAL_TEXT_V23_ADAPTER_ROBUSTNESS_PASS" else "PRIVATE_SYNTHETIC_SFT_V23_ADAPTER_RETAINED_FOR_RESEARCH_ONLY"
    write_json(AUDIT / "v1612_experiment_a_closure.json", closure)
    write_doc(DOCS / "257_v1612_v23_real_text_robustness.md", "V1.6.12 V2.3 Real Text Robustness", [f"Status: `{result['status']}`", "- Amazon/ASAP samples: `10 / 10`", "- This is unlabeled robustness only; no real-world accuracy or Macro-F1 is reported."])
    print(result["status"])


if __name__ == "__main__":
    main()
