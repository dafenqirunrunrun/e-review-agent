from __future__ import annotations

import gc
import json
import random
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from v169_common import AUDIT, DOCS, MODEL_DIR, PRIVATE_ROOT, now, read_json, read_jsonl, target, write_doc, write_json

DATA_V23 = PRIVATE_ROOT / "synthetic-sft-v23"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-sft-v23-v1612"
PRED_DIR = RUN_DIR / "private-eval-predictions"


def generate(model, tokenizer, rows: list[dict[str, Any]], split: str, model_role: str) -> list[dict[str, Any]]:
    import torch
    from app.prompts.e_review_prompt_renderer import render_generation_prompt

    device = next(model.parameters()).device
    outputs = []
    for row in rows:
        prompt = render_generation_prompt(json.loads(row["user"]), tokenizer)
        inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=384)
        input_len = int(inputs["input_ids"].shape[-1])
        inputs = {key: value.to(device) for key, value in inputs.items()}
        started = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=128, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        outputs.append(
            {
                "split": split,
                "model_role": model_role,
                "sample_hash": row["metadata"]["sample_hash"],
                "raw_output": tokenizer.decode(generated[0][input_len:], skip_special_tokens=True).strip(),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        del generated, inputs
    return outputs


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


def metrics(predictions: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    from app.evaluation.e_review_task_evaluator import evaluate_e_review_outputs
    from app.contracts.e_review_decision_migration import process_model_output

    by_hash = {row["sample_hash"]: row["raw_output"] for row in predictions}
    raw = [by_hash[row["metadata"]["sample_hash"]] for row in rows]
    gold = [target(row) for row in rows]
    m = evaluate_e_review_outputs(raw, gold)
    processed = [process_model_output(item) for item in raw]
    operational = [item["operational_result"] for item in processed]
    pred_types = [op.get("risk_type") for op in operational if op.get("prediction_source") != "operational_safety_fallback"]
    return {
        "raw_canonical_schema_valid_rate": m["raw_canonical_schema_valid_rate"],
        "task_coverage_rate": m["task_coverage_rate"],
        "fallback_rate": m["operational_fallback_rate"],
        "coverage_adjusted_accuracy": m["coverage_adjusted_accuracy"],
        "risk_type_macro_f1": m["risk_type_macro_f1"],
        "risk_level_macro_f1": m["risk_level_macro_f1"],
        "need_human_review_f1": m["need_human_review_f1"],
        "evidence_support_rate": sum(1 for op in operational if op.get("text_evidence")) / len(operational),
        "prohibited_action_count": m["prohibited_auto_action_count"],
        "semantic_field_change_count": m["semantic_field_change_count"],
        "distinct_risk_type_count": len(set(pred_types)),
        "dominant_class_rate": (max(Counter(pred_types).values()) / len(pred_types)) if pred_types else 1.0,
        "prediction_source_distribution": m["prediction_source_distribution"],
    }


def paired_bootstrap(base_preds: list[dict[str, Any]], adapter_preds: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    rng = random.Random(1612)
    n = len(rows)
    base_by = {p["sample_hash"]: p for p in base_preds}
    adapter_by = {p["sample_hash"]: p for p in adapter_preds}
    deltas = {"coverage_adjusted_accuracy": [], "risk_type_macro_f1": [], "task_coverage_rate": []}
    for _ in range(2000):
        sample_rows = [rows[rng.randrange(n)] for _ in range(n)]
        b = [base_by[row["metadata"]["sample_hash"]] for row in sample_rows]
        a = [adapter_by[row["metadata"]["sample_hash"]] for row in sample_rows]
        bm = metrics(b, sample_rows)
        am = metrics(a, sample_rows)
        for key in deltas:
            deltas[key].append(am[key] - bm[key])
    def ci(values: list[float]) -> dict[str, float]:
        values = sorted(values)
        return {"low": round(values[int(0.025 * len(values))], 8), "high": round(values[int(0.975 * len(values)) - 1], 8)}
    return {key: ci(values) for key, values in deltas.items()}


def value_gate(base: dict[str, Any], adapter: dict[str, Any], ci: dict[str, Any]) -> dict[str, Any]:
    delta = {key: round(adapter[key] - base[key], 8) for key in ["coverage_adjusted_accuracy", "risk_type_macro_f1", "risk_level_macro_f1", "task_coverage_rate", "fallback_rate", "raw_canonical_schema_valid_rate", "evidence_support_rate"]}
    no_go = (
        delta["task_coverage_rate"] < -0.10
        or delta["fallback_rate"] > 0.10
        or delta["coverage_adjusted_accuracy"] < 0
        or delta["risk_type_macro_f1"] < -0.05
        or adapter["prohibited_action_count"] > 0
        or adapter["distinct_risk_type_count"] < 3
        or adapter["dominant_class_rate"] > 0.70
    )
    go = (
        delta["coverage_adjusted_accuracy"] >= 0.05
        and (delta["risk_type_macro_f1"] >= 0.05 or delta["risk_level_macro_f1"] >= 0.05)
        and delta["task_coverage_rate"] >= -0.03
        and delta["fallback_rate"] <= 0.03
        and delta["raw_canonical_schema_valid_rate"] >= -0.05
        and delta["evidence_support_rate"] >= -0.05
        and adapter["prohibited_action_count"] == 0
        and adapter["distinct_risk_type_count"] >= 3
        and adapter["dominant_class_rate"] <= 0.70
        and adapter["semantic_field_change_count"] == 0
        and ci["coverage_adjusted_accuracy"]["low"] > 0
    )
    status = "GO" if go else ("NO_GO" if no_go else "NEUTRAL")
    return {"status": status, "delta": delta, "bootstrap_ci": ci}


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    from transformers import AutoTokenizer
    from app.runtime.gpu_gate import gpu_exclusive_gate

    train = read_json(AUDIT / "v1612_experiment_a_training_summary.json")
    if train["status"] != "PRIVATE_SYNTHETIC_SFT_V23_EXPERIMENT_A_TRAIN_PASS":
        result = {"generated_at": now(), "status": "V23_EXPERIMENT_A_EVAL_BLOCKED", "blocked_reason": "training did not pass"}
        write_json(AUDIT / "v1612_experiment_a_eval_summary.json", result)
        print(result["status"])
        return
    validation_rows = read_jsonl(DATA_V23 / "validation.jsonl")
    holdout_rows = read_jsonl(DATA_V23 / "engineering_holdout_v23.jsonl")
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    all_predictions = []
    with gpu_exclusive_gate(stage="v1612-v23-experiment-a-eval", min_free_memory_mb=5200, check_interval_seconds=10, stable_checks=2, timeout_seconds=600, gpu_gate_mode="wddm-aware", max_wddm_total_utilization=60, max_free_memory_drop_mb=256, require_zero_numeric_compute_processes=True, allow_wddm_graphics_activity=True):
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
        for role, use_adapter in [("base", False), ("adapter", True)]:
            model = load_model(use_adapter)
            for split, rows in [("validation", validation_rows), ("engineering_holdout_v23", holdout_rows)]:
                preds = generate(model, tokenizer, rows, split, role)
                all_predictions.extend(preds)
            del model
            gc.collect()
            torch.cuda.empty_cache()
        del tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    (PRED_DIR / "v1612_eval_predictions.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_predictions), encoding="utf-8")
    by = {(p["split"], p["model_role"]): [] for p in all_predictions}
    for pred in all_predictions:
        by[(pred["split"], pred["model_role"])].append(pred)
    validation = {"base": metrics(by[("validation", "base")], validation_rows), "adapter": metrics(by[("validation", "adapter")], validation_rows)}
    holdout = {"base": metrics(by[("engineering_holdout_v23", "base")], holdout_rows), "adapter": metrics(by[("engineering_holdout_v23", "adapter")], holdout_rows)}
    ci = paired_bootstrap(by[("engineering_holdout_v23", "base")], by[("engineering_holdout_v23", "adapter")], holdout_rows)
    gate = value_gate(holdout["base"], holdout["adapter"], ci)
    result = {
        "generated_at": now(),
        "status": "V23_ENGINEERING_HOLDOUT_EVALUATED_AND_CLOSED",
        "validation": validation,
        "holdout": holdout,
        "value_gate": gate,
        "raw_prediction_file_label": "<data-private>/training-runs/qwen3-1.7b-synthetic-sft-v23-v1612/private-eval-predictions/v1612_eval_predictions.jsonl",
        "holdout_repeated_evaluation_allowed": False,
        "holdout_closed": True,
    }
    write_json(AUDIT / "v1612_experiment_a_eval_summary.json", result)
    write_doc(DOCS / "256_v1612_experiment_a_eval.md", "V1.6.12 Experiment A Evaluation", [f"Status: `{result['status']}`", f"- value gate: `{gate['status']}`", f"- holdout coverage-adjusted accuracy delta: `{gate['delta']['coverage_adjusted_accuracy']}`", f"- holdout coverage delta: `{gate['delta']['task_coverage_rate']}`", f"- holdout fallback delta: `{gate['delta']['fallback_rate']}`"])
    final_role = "PRIVATE_SYNTHETIC_SFT_V23_ADAPTER_DEFAULT_CANDIDATE" if gate["status"] == "GO" else "PRIVATE_SYNTHETIC_SFT_V23_ADAPTER_RETAINED_FOR_RESEARCH_ONLY"
    write_json(AUDIT / "v1612_experiment_a_closure.json", {"generated_at": now(), "status": final_role, "value_gate": gate["status"], "real_text_robustness": "V23_REAL_TEXT_ROBUSTNESS_SKIPPED_NO_GO" if gate["status"] == "NO_GO" else "NOT_RUN"})
    print(result["status"])
    print(f"PRIVATE_SYNTHETIC_SFT_V23_EXPERIMENT_A_VALUE_GATE={gate['status']}")


if __name__ == "__main__":
    main()
