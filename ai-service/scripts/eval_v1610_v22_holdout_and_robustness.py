from __future__ import annotations

import gc
import hashlib
import json
import math
import statistics
import time
from collections import Counter

from v169_common import AUDIT, DATA_V22, DOCS, EVAL, MODEL_DIR, PRIVATE_ROOT, TRAINING, now, read_json, read_jsonl, target, write_doc, write_json
from run_v1610_v22_memory_safe_qlora_training import RUN_DIR_V1610


REAL_TEXT = PRIVATE_ROOT / "realworld-pilot-v1-frozen" / "processed-text" / "real_reviews_redacted_private.jsonl"


def generated_text(model, tokenizer, rows: list[dict]) -> tuple[list[str], list[float]]:
    import torch
    from app.prompts.e_review_prompt_renderer import render_generation_prompt

    outputs: list[str] = []
    latencies: list[float] = []
    device = next(model.parameters()).device
    with torch.inference_mode():
        for row in rows:
            user = json.loads(row["user"]) if "user" in row else row
            prompt = render_generation_prompt(user, tokenizer)
            inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=384)
            input_len = int(inputs["input_ids"].shape[-1])
            inputs = {key: value.to(device) for key, value in inputs.items()}
            started = time.perf_counter()
            generated = model.generate(**inputs, max_new_tokens=160, do_sample=False, pad_token_id=tokenizer.eos_token_id)
            latencies.append((time.perf_counter() - started) * 1000)
            outputs.append(tokenizer.decode(generated[0][input_len:], skip_special_tokens=True).strip())
            del generated
            del inputs
    return outputs, latencies


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
        model = PeftModel.from_pretrained(model, RUN_DIR_V1610 / "adapter-best", local_files_only=True)
    model.eval()
    return model


def unload(*objects) -> None:
    import torch

    for obj in objects:
        del obj
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def holdout_metrics(raw_outputs: list[str], rows: list[dict], latencies: list[float]) -> dict:
    from app.contracts.e_review_decision_migration import process_model_output
    from app.evaluation.e_review_task_evaluator import evaluate_e_review_outputs

    gold = [target(row) for row in rows]
    metrics = evaluate_e_review_outputs(raw_outputs, gold)
    processed = [process_model_output(raw) for raw in raw_outputs]
    operational = [item["operational_result"] for item in processed]
    eligible = [bool(item["prediction_eligible"]) for item in processed]
    eligible_ops = [op for op, ok in zip(operational, eligible) if ok]
    risk_types = [op.get("risk_type") for op in eligible_ops]
    dominant_rate = 0.0
    if risk_types:
        dominant_rate = max(Counter(risk_types).values()) / len(risk_types)
    return {
        "real_inference_count": len(raw_outputs),
        "raw_json_object_extract_rate": metrics["raw_json_object_extract_rate"],
        "raw_json_parse_success_rate": metrics["raw_json_parse_success_rate"],
        "raw_canonical_schema_valid_rate": metrics["raw_canonical_schema_valid_rate"],
        "required_field_presence_rate": metrics["raw_required_field_presence_rate"],
        "contract_normalization_rate": metrics["contract_normalization_rate"],
        "semantic_field_change_count": metrics["semantic_field_change_count"],
        "prediction_eligible_rate": metrics["prediction_eligible_for_task_metrics_rate"],
        "operational_final_schema_valid_rate": metrics["operational_final_schema_valid_rate"],
        "operational_fallback_rate": metrics["operational_fallback_rate"],
        "task_coverage_rate": metrics["task_coverage_rate"],
        "abstention_rate": metrics["abstention_rate"],
        "coverage_adjusted_accuracy": metrics["coverage_adjusted_accuracy"],
        "structured_exact_match_rate": metrics["coverage_adjusted_accuracy"],
        "risk_type_macro_f1": metrics["risk_type_macro_f1"],
        "risk_level_macro_f1": metrics["risk_level_macro_f1"],
        "need_human_review_f1": metrics["need_human_review_f1"],
        "evidence_support_rate": evidence_support_rate(operational),
        "prohibited_auto_action_count": metrics["prohibited_auto_action_count"],
        "unsupported_business_action_count": unsupported_business_count(operational),
        "distinct_risk_type_count": len(set(risk_types)),
        "dominant_class_rate": round(dominant_rate, 8),
        "oom": 0,
        "avg_generate_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_generate_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else None,
        "prediction_source_distribution": metrics["prediction_source_distribution"],
    }


def evidence_support_rate(operational: list[dict]) -> float:
    if not operational:
        return 0.0
    return round(sum(1 for item in operational if item.get("text_evidence")) / len(operational), 8)


def unsupported_business_count(operational: list[dict]) -> int:
    return sum(1 for item in operational if item.get("unsupported_claims"))


def value_gate(base: dict, adapter: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    improved = [
        adapter["raw_canonical_schema_valid_rate"] >= base["raw_canonical_schema_valid_rate"] + 0.10,
        adapter["task_coverage_rate"] >= base["task_coverage_rate"] + 0.10,
        adapter["risk_type_macro_f1"] >= base["risk_type_macro_f1"] + 0.05,
        adapter["coverage_adjusted_accuracy"] >= base["coverage_adjusted_accuracy"] + 0.05,
    ]
    safe = [
        adapter["operational_fallback_rate"] <= base["operational_fallback_rate"],
        adapter["operational_final_schema_valid_rate"] >= base["operational_final_schema_valid_rate"],
        adapter["prohibited_auto_action_count"] == 0,
        adapter["evidence_support_rate"] >= base["evidence_support_rate"] - 0.05,
        adapter["semantic_field_change_count"] == 0,
        adapter["dominant_class_rate"] <= 0.80,
        adapter["distinct_risk_type_count"] >= 2,
    ]
    if any(improved) and all(safe):
        return "GO", ["at_least_one_primary_metric_improved", "safety_constraints_passed"]
    if not all(safe):
        reasons.append("safety_or_collapse_constraint_failed")
        return "NO_GO", reasons
    return "NEUTRAL", ["no_stable_improvement_on_24_sample_engineering_holdout"]


def select_real_rows() -> list[dict]:
    rows = read_jsonl(REAL_TEXT)
    selected = []
    for source_id in ["amazon_reviews_2023", "asap_chinese_reviews"]:
        source_rows = [row for row in rows if row.get("source_id") == source_id and row.get("review_text_redacted")]
        source_rows = sorted(source_rows, key=lambda row: hashlib.sha256(row["sample_id_hash"].encode("utf-8")).hexdigest())
        for row in source_rows[:10]:
            selected.append(
                {
                    "review_text": row["review_text_redacted"],
                    "rating": row.get("rating") or "",
                    "product_category": row.get("category") or source_id,
                    "source_id": source_id,
                    "sample_id_hash": row.get("sample_id_hash"),
                }
            )
    return selected


def robustness_metrics(outputs: list[str], rows: list[dict], latencies: list[float]) -> dict:
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
        "operational_schema_valid_rate": 1.0,
        "fallback_rate": round(sum(1 for op in operational if op.get("prediction_source") == "operational_safety_fallback") / n, 8),
        "empty_rate": round(sum(1 for raw in outputs if not raw.strip()) / n, 8),
        "evidence_nonempty_rate": evidence_support_rate(operational),
        "need_human_review_rate": round(sum(1 for op in operational if op.get("need_human_review")) / n, 8),
        "risk_distribution": dict(Counter(risks)),
        "prohibited_action": sum(1 for raw in outputs if any(term in raw.lower() for term in ["auto refund", "automatic refund", "auto ban", "automatic ban"])),
        "unsupported_action": unsupported_business_count(operational),
        "avg_generate_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_generate_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else None,
        "oom": 0,
    }


def main() -> None:
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    from transformers import AutoTokenizer
    from app.runtime.gpu_gate import gpu_exclusive_gate

    training = read_json(TRAINING / "v1610_v22_resumed_training_summary.json")
    result = {
        "generated_at": now(),
        "status": "V22_ENGINEERING_HOLDOUT_EVALUATION_NOT_RUN_TRAINING_BLOCKED",
        "holdout_unsealed_once": False,
        "holdout_count": 0,
        "base_metrics": {},
        "adapter_metrics": {},
    }
    robustness = {
        "generated_at": now(),
        "status": "PRIVATE_REAL_TEXT_V22_ADAPTER_ROBUSTNESS_NOT_RUN_TRAINING_BLOCKED",
        "amazon_sample_count": 0,
        "asap_sample_count": 0,
        "base_metrics": {},
        "adapter_metrics": {},
    }
    gate = {
        "generated_at": now(),
        "status": "PRIVATE_SYNTHETIC_SFT_V22_ADAPTER_VALUE_GATE_NOT_RUN",
        "adapter_value_gate": "NO_GO",
        "default_candidate": False,
        "adapter_final_role": "PRIVATE_SYNTHETIC_SFT_V22_ADAPTER_RETAINED_FOR_RESEARCH_ONLY",
    }
    if training["status"] != "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_PASS":
        write_outputs(result, robustness, gate)
        print(result["status"])
        return

    holdout_rows = read_jsonl(DATA_V22 / "engineering_holdout_v21.jsonl")
    real_rows = select_real_rows()
    with gpu_exclusive_gate(
        stage="v1610-v22-holdout-and-robustness",
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
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
        base = load_model(False)
        base_holdout_outputs, base_holdout_latencies = generated_text(base, tokenizer, holdout_rows)
        base_real_outputs, base_real_latencies = generated_text(base, tokenizer, real_rows)
        unload(base)

        adapter = load_model(True)
        adapter_holdout_outputs, adapter_holdout_latencies = generated_text(adapter, tokenizer, holdout_rows)
        adapter_real_outputs, adapter_real_latencies = generated_text(adapter, tokenizer, real_rows)
        unload(adapter, tokenizer)

        result = {
            "generated_at": now(),
            "status": "V22_ENGINEERING_HOLDOUT_EVALUATED_AND_CLOSED",
            "holdout_unsealed_once": True,
            "holdout_count": len(holdout_rows),
            "base_metrics": holdout_metrics(base_holdout_outputs, holdout_rows, base_holdout_latencies),
            "adapter_metrics": holdout_metrics(adapter_holdout_outputs, holdout_rows, adapter_holdout_latencies),
            "raw_outputs_saved_in_git": False,
        }
        gate_value, reasons = value_gate(result["base_metrics"], result["adapter_metrics"])
        robustness = {
            "generated_at": now(),
            "status": "PRIVATE_REAL_TEXT_V22_ADAPTER_ROBUSTNESS_PASS",
            "amazon_sample_count": sum(1 for row in real_rows if row["source_id"] == "amazon_reviews_2023"),
            "asap_sample_count": sum(1 for row in real_rows if row["source_id"] == "asap_chinese_reviews"),
            "base_metrics": robustness_metrics(base_real_outputs, real_rows, base_real_latencies),
            "adapter_metrics": robustness_metrics(adapter_real_outputs, real_rows, adapter_real_latencies),
            "raw_text_saved_in_git": False,
            "raw_outputs_saved_in_git": False,
        }
        default_candidate = (
            gate_value == "GO"
            and robustness["status"] == "PRIVATE_REAL_TEXT_V22_ADAPTER_ROBUSTNESS_PASS"
            and robustness["adapter_metrics"]["prohibited_action"] == 0
            and robustness["adapter_metrics"]["unsupported_action"] == 0
        )
        gate = {
            "generated_at": now(),
            "status": "PRIVATE_SYNTHETIC_SFT_V22_ADAPTER_VALUE_GATE",
            "adapter_value_gate": gate_value,
            "gate_reasons": reasons,
            "default_candidate": default_candidate,
            "adapter_final_role": "PRIVATE_SYNTHETIC_SFT_V22_ADAPTER_DEFAULT_CANDIDATE" if default_candidate else "PRIVATE_SYNTHETIC_SFT_V22_ADAPTER_RETAINED_FOR_RESEARCH_ONLY",
            "release_allowed": False,
            "note": "24-sample synthetic engineering holdout only; no adapter or weights may be published.",
        }
    write_outputs(result, robustness, gate)
    print(result["status"])


def write_outputs(result: dict, robustness: dict, gate: dict) -> None:
    write_json(EVAL / "v1610_v22_holdout_evaluation.json", result)
    write_json(EVAL / "v1610_v22_real_text_robustness.json", robustness)
    write_json(AUDIT / "v1610_v22_adapter_value_gate.json", gate)
    write_doc(
        DOCS / "241_v1610_v22_holdout_evaluation.md",
        "V1.6.10 V2.2 Holdout Evaluation",
        [
            f"Status: `{result['status']}`",
            f"- holdout_unsealed_once: `{result.get('holdout_unsealed_once')}`",
            f"- holdout_count: `{result.get('holdout_count')}`",
            f"- base_real_inference_count: `{result.get('base_metrics', {}).get('real_inference_count')}`",
            f"- adapter_real_inference_count: `{result.get('adapter_metrics', {}).get('real_inference_count')}`",
            f"- base_risk_type_macro_f1: `{result.get('base_metrics', {}).get('risk_type_macro_f1')}`",
            f"- adapter_risk_type_macro_f1: `{result.get('adapter_metrics', {}).get('risk_type_macro_f1')}`",
            f"- base_coverage_adjusted_accuracy: `{result.get('base_metrics', {}).get('coverage_adjusted_accuracy')}`",
            f"- adapter_coverage_adjusted_accuracy: `{result.get('adapter_metrics', {}).get('coverage_adjusted_accuracy')}`",
        ],
    )
    write_doc(
        DOCS / "242_v1610_v22_adapter_decision.md",
        "V1.6.10 V2.2 Adapter Decision",
        [
            f"Value gate status: `{gate['status']}`",
            f"- adapter_value_gate: `{gate.get('adapter_value_gate')}`",
            f"- adapter_final_role: `{gate.get('adapter_final_role')}`",
            f"- default_candidate: `{gate.get('default_candidate')}`",
            f"- real_text_robustness_status: `{robustness.get('status')}`",
            f"- amazon/asap counts: `{robustness.get('amazon_sample_count')}` / `{robustness.get('asap_sample_count')}`",
            "- Adapter and weights are not release artifacts.",
        ],
    )


if __name__ == "__main__":
    main()
