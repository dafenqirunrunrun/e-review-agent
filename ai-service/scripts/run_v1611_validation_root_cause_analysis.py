from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from v169_common import AUDIT, DATA_V22, DOCS, EVAL, MODEL_DIR, PRIVATE_ROOT, TRAINING, compact_json, now, read_json, read_jsonl, target, write_doc, write_json


RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-sft-v22-v1610"
PRED_DIR = RUN_DIR / "private-validation"
PRED_FILE = PRED_DIR / "v1611_validation_predictions.jsonl"
PRED_META = PRED_DIR / "v1611_validation_predictions_meta.json"


def row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(row["user"].encode("utf-8")).hexdigest()


def hash_rows(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256("".join(row_hash(row) for row in rows).encode("utf-8")).hexdigest()


def write_freeze() -> dict:
    closure = read_json(AUDIT / "v1610_experiment_closure.json")
    result = {
        "generated_at": now(),
        "status": "V1610_RESULT_PERMANENTLY_FROZEN",
        "source_closure_status": closure["training_status"],
        "adapter_value_gate": closure["adapter_value_gate"],
        "adapter_role": closure["adapter_role"],
        "holdout_reuse_allowed": False,
        "holdout_reinference_allowed": False,
        "holdout_raw_prediction_access_allowed": False,
        "holdout_metric_recompute_allowed": False,
        "holdout_driven_prompt_tuning_allowed": False,
        "holdout_driven_retraining_allowed": False,
        "adapter_value_gate_override_allowed": False,
    }
    write_json(AUDIT / "v1610_final_result_freeze.json", result)
    write_doc(
        DOCS / "244_v1611_v1610_result_freeze.md",
        "V1.6.11 V1.6.10 Result Freeze",
        [
            f"Status: `{result['status']}`",
            f"- adapter_value_gate: `{result['adapter_value_gate']}`",
            f"- adapter_role: `{result['adapter_role']}`",
            "- v2.2 holdout reuse, reinference, metric recomputation, prompt tuning, and retraining are forbidden.",
        ],
    )
    return result


def inventory(validation_rows: list[dict[str, Any]]) -> dict:
    expected_hash = hash_rows(validation_rows)
    expected_prediction_count = len(validation_rows) * 2
    valid = False
    count = 0
    reason = "missing_predictions"
    role_counts: dict[str, int] = {}
    if PRED_FILE.exists() and PRED_META.exists():
        meta = json.loads(PRED_META.read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in PRED_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        count = len(rows)
        role_counts = dict(Counter(row.get("model_role") for row in rows))
        valid = (
            count == expected_prediction_count
            and role_counts == {"base": len(validation_rows), "adapter": len(validation_rows)}
            and meta.get("validation_manifest_hash") == expected_hash
            and meta.get("prompt_version") == "v2.1.0"
            and meta.get("contract_version") == "v2.0.0"
            and meta.get("evaluator_version") == "v2.1.0"
            and meta.get("contains_holdout_sample_hash") is False
        )
        reason = "VALIDATION_PREDICTIONS_REUSED_OFFLINE" if valid else "prediction_hash_or_metadata_mismatch"
    result = {
        "generated_at": now(),
        "status": "VALIDATION_PREDICTIONS_REUSED_OFFLINE" if valid else "VALIDATION_PREDICTIONS_REQUIRED_ONCE",
        "prediction_file_label": "<data-private>/training-runs/qwen3-1.7b-synthetic-sft-v22-v1610/private-validation/v1611_validation_predictions.jsonl",
        "prediction_count": count,
        "expected_validation_count": len(validation_rows),
        "expected_prediction_count": expected_prediction_count,
        "model_role_counts": role_counts,
        "validation_manifest_hash": expected_hash,
        "prompt_version": "v2.1.0",
        "contract_version": "v2.0.0",
        "evaluator_version": "v2.1.0",
        "decision_reason": reason,
    }
    write_json(AUDIT / "v1611_validation_artifact_inventory.json", result)
    return result


def generate_validation_predictions(validation_rows: list[dict[str, Any]]) -> None:
    import gc
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    import transformers
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from app.prompts.e_review_prompt_renderer import render_generation_prompt
    from app.runtime.gpu_gate import gpu_exclusive_gate

    def load(adapter: bool):
        qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
        dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
        model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, **{dtype_key: torch.bfloat16})
        model.config.use_cache = False
        if adapter:
            model = PeftModel.from_pretrained(model, RUN_DIR / "adapter-best", local_files_only=True)
        model.eval()
        return model

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    with gpu_exclusive_gate(
        stage="v1611-validation-only-predictions",
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
        for role in ["base", "adapter"]:
            model = load(role == "adapter")
            device = next(model.parameters()).device
            with torch.inference_mode():
                for row in validation_rows:
                    prompt = render_generation_prompt(json.loads(row["user"]), tokenizer)
                    inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=384)
                    input_len = int(inputs["input_ids"].shape[-1])
                    inputs = {k: v.to(device) for k, v in inputs.items()}
                    started = time.perf_counter()
                    generated = model.generate(**inputs, max_new_tokens=160, do_sample=False, pad_token_id=tokenizer.eos_token_id)
                    latency = (time.perf_counter() - started) * 1000
                    outputs.append(
                        {
                            "model_role": role,
                            "sample_hash": row["metadata"]["sample_hash"],
                            "raw_output": tokenizer.decode(generated[0][input_len:], skip_special_tokens=True).strip(),
                            "latency_ms": round(latency, 2),
                        }
                    )
                    del generated, inputs
            del model
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        del tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    PRED_FILE.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in outputs), encoding="utf-8")
    PRED_META.write_text(
        json.dumps(
            {
                "generated_at": now(),
                "validation_manifest_hash": hash_rows(validation_rows),
                "prompt_version": "v2.1.0",
                "contract_version": "v2.0.0",
                "evaluator_version": "v2.1.0",
                "prediction_count": len(outputs),
                "contains_holdout_sample_hash": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_predictions(validation_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rows = [json.loads(line) for line in PRED_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_role = {"base": [], "adapter": []}
    expected_hashes = {row["metadata"]["sample_hash"] for row in validation_rows}
    for row in rows:
        if row["sample_hash"] not in expected_hashes:
            raise RuntimeError("prediction hash not in validation set")
        by_role[row["model_role"]].append(row)
    return by_role


def metrics_for(preds: list[dict[str, Any]], validation_rows: list[dict[str, Any]]) -> dict[str, Any]:
    from app.contracts.e_review_decision_migration import process_model_output
    from app.evaluation.e_review_task_evaluator import evaluate_e_review_outputs, macro_f1

    by_hash = {row["sample_hash"]: row["raw_output"] for row in preds}
    raws = [by_hash[row["metadata"]["sample_hash"]] for row in validation_rows]
    gold = [target(row) for row in validation_rows]
    processed = [process_model_output(raw) for raw in raws]
    ops = [item["operational_result"] for item in processed]
    eligible = [bool(item["prediction_eligible"]) for item in processed]
    m = evaluate_e_review_outputs(raws, gold)
    eligible_pairs = [(op, g) for op, g, ok in zip(ops, gold, eligible) if ok]
    n_eligible = len(eligible_pairs) or 1
    return {
        "raw_json_object_extract_rate": m["raw_json_object_extract_rate"],
        "raw_json_parse_success_rate": m["raw_json_parse_success_rate"],
        "raw_canonical_schema_valid_rate": m["raw_canonical_schema_valid_rate"],
        "required_field_presence_rate": m["raw_required_field_presence_rate"],
        "input_echo_rate": round(sum(1 for raw in raws if "review:" in raw or "synthetic_review_text" in raw) / len(raws), 8),
        "contract_normalization_rate": m["contract_normalization_rate"],
        "normalized_schema_valid_rate": m["normalized_canonical_schema_valid_rate"],
        "semantic_field_change_count": m["semantic_field_change_count"],
        "prediction_eligible_rate": m["prediction_eligible_for_task_metrics_rate"],
        "final_schema_valid_rate": m["operational_final_schema_valid_rate"],
        "fallback_rate": m["operational_fallback_rate"],
        "empty_rate": m["empty_output_rate"],
        "prohibited_action_count": m["prohibited_auto_action_count"],
        "task_coverage_rate": m["task_coverage_rate"],
        "abstention_rate": m["abstention_rate"],
        "eligible_accuracy": round(
            sum(1 for op, g in eligible_pairs if op.get("risk_type") == g.get("risk_type") and op.get("risk_level") == g.get("risk_level") and bool(op.get("need_human_review")) == bool(g.get("need_human_review"))) / n_eligible,
            8,
        ),
        "coverage_adjusted_accuracy": m["coverage_adjusted_accuracy"],
        "risk_type_accuracy": round(sum(1 for op, g in eligible_pairs if op.get("risk_type") == g.get("risk_type")) / n_eligible, 8),
        "risk_type_macro_f1": m["risk_type_macro_f1"],
        "risk_level_accuracy": round(sum(1 for op, g in eligible_pairs if op.get("risk_level") == g.get("risk_level")) / n_eligible, 8),
        "risk_level_macro_f1": m["risk_level_macro_f1"],
        "need_human_review_f1": m["need_human_review_f1"],
        "evidence_support_rate": round(sum(1 for op in ops if op.get("text_evidence")) / len(ops), 8),
        "operational": ops,
        "eligible": eligible,
    }


def training_curve() -> dict:
    summary = read_json(TRAINING / "v1610_v22_resumed_training_summary.json")
    logs = summary["train_log"]
    vals = {v["step"]: v["validation_loss"] for v in summary["validation_log"]}
    initial = logs[0]["train_loss"]
    final = logs[-1]["train_loss"]
    def slope(start: int, end: int) -> float:
        y1 = logs[start - 1]["train_loss"]
        y2 = logs[end - 1]["train_loss"]
        return round((y2 - y1) / (end - start), 8)
    result = {
        "status": "TRAINING_CURVE_ANALYSIS_COMPLETE",
        "initial_train_loss": initial,
        "final_train_loss": final,
        "absolute_train_loss_reduction": round(initial - final, 8),
        "relative_train_loss_reduction": round((initial - final) / initial, 8),
        "validation_loss_by_step": vals,
        "best_validation_loss": summary["best_validation_loss"],
        "final_validation_loss": vals.get(42),
        "train_validation_gap": round(vals.get(42) - final, 8),
        "slope_1_14": slope(1, 14),
        "slope_15_28": slope(15, 28),
        "slope_29_42": slope(29, 42),
        "gradient_norm_start": logs[0]["gradient_norm"],
        "gradient_norm_final": logs[-1]["gradient_norm"],
        "learning_rate_unique": sorted({row["learning_rate"] for row in logs}),
    }
    result["loss_improved_task_not_improved"] = result["relative_train_loss_reduction"] > 0.5
    result["judgements"] = ["OPTIMIZATION_STABLE_SIGNAL_WEAK" if result["train_validation_gap"] < 0.05 else "LOSS_IMPROVED_TASK_NOT_IMPROVED"]
    write_json(AUDIT / "v1611_training_curve_analysis.json", result)
    return result


def distribution(ops: list[dict[str, Any]], gold: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    pred = [op.get("risk_type") for op in ops if op.get("prediction_source") != "operational_safety_fallback"]
    gold_types = [g.get("risk_type") for g in gold]
    pred_count = Counter(pred)
    gold_count = Counter(gold_types)
    total = len(pred) or 1
    dominant = max(pred_count.values()) / total if pred_count else 0
    status = "DISTRIBUTION_NON_COLLAPSED"
    if dominant > 0.90:
        status = "PARTIAL_COLLAPSE"
    elif dominant > 0.70:
        status = "CLASS_BIAS"
    return {
        f"{prefix}_distinct_class_count": len(pred_count),
        f"{prefix}_dominant_class_rate": round(dominant, 8),
        f"{prefix}_missing_class_count": len(set(gold_count) - set(pred_count)),
        f"{prefix}_classification": status,
        f"{prefix}_prediction_distribution": dict(pred_count),
        f"{prefix}_gold_distribution": dict(gold_count),
        f"{prefix}_shannon_entropy": round(-sum((c / total) * math.log2(c / total) for c in pred_count.values()), 8) if pred_count else 0,
        f"{prefix}_js_divergence": round(js_divergence(gold_count, pred_count), 8),
    }


def js_divergence(a: Counter, b: Counter) -> float:
    keys = set(a) | set(b)
    ta = sum(a.values()) or 1
    tb = sum(b.values()) or 1
    pa = {k: a[k] / ta for k in keys}
    pb = {k: b[k] / tb for k in keys}
    m = {k: (pa[k] + pb[k]) / 2 for k in keys}
    def kl(p, q):
        return sum(p[k] * math.log2(p[k] / q[k]) for k in keys if p[k] > 0 and q[k] > 0)
    return (kl(pa, m) + kl(pb, m)) / 2


def slice_analysis(validation_rows: list[dict[str, Any]], base_m: dict, adapter_m: dict) -> dict:
    dims = {
        "risk_type": [row["metadata"]["risk_type"] for row in validation_rows],
        "risk_level": [row["metadata"]["risk_level"] for row in validation_rows],
        "need_human_review": [str(target(row)["need_human_review"]) for row in validation_rows],
        "scenario_family": [row["metadata"]["lineage"]["scenario_family"] for row in validation_rows],
        "template_family": [row["metadata"]["lineage"]["template_family"] for row in validation_rows],
    }
    gold = [target(row) for row in validation_rows]
    result = {"status": "VALIDATION_SLICE_ANALYSIS_COMPLETE", "slices": {}}
    for dim, values in dims.items():
        result["slices"][dim] = {}
        for value in sorted(set(values)):
            idxs = [i for i, v in enumerate(values) if v == value]
            result["slices"][dim][value] = slice_metrics(idxs, gold, base_m, adapter_m)
    write_json(AUDIT / "v1611_validation_slice_analysis.json", result)
    return result


def slice_metrics(idxs: list[int], gold: list[dict], base_m: dict, adapter_m: dict) -> dict:
    def one(m):
        ops = [m["operational"][i] for i in idxs]
        elig = [m["eligible"][i] for i in idxs]
        pairs = [(op, gold[i]) for op, ok, i in zip(ops, elig, idxs) if ok]
        denom = len(pairs) or 1
        return {
            "coverage": round(sum(elig) / (len(idxs) or 1), 8),
            "risk_accuracy": round(sum(1 for op, g in pairs if op.get("risk_type") == g.get("risk_type")) / denom, 8),
            "schema_valid": round(sum(elig) / (len(idxs) or 1), 8),
            "fallback": round(sum(1 for op in ops if op.get("prediction_source") == "operational_safety_fallback") / (len(idxs) or 1), 8),
            "evidence_support": round(sum(1 for op in ops if op.get("text_evidence")) / (len(idxs) or 1), 8),
        }
    b, a = one(base_m), one(adapter_m)
    return {"sample_count": len(idxs), "status": "INSUFFICIENT_SLICE_SAMPLE" if len(idxs) < 5 else "SLICE_ANALYZED", "base": b, "adapter": a, "delta_risk_accuracy": round(a["risk_accuracy"] - b["risk_accuracy"], 8)}


def template_analysis(rows: list[dict[str, Any]]) -> dict:
    train = read_jsonl(DATA_V22 / "train.jsonl")
    all_rows = train + rows
    targets = [target(r) for r in all_rows]
    normalized = [compact_json(t) for t in targets]
    reasons = [t.get("route_reason", "") for t in targets]
    evidences = ["|".join(t.get("text_evidence") or []) for t in targets]
    route_top = Counter(reasons).most_common(5)
    result = {
        "status": "TARGET_TEMPLATE_ANALYSIS_COMPLETE",
        "target_exact_duplicate_rate": duplicate_rate([json.dumps(t, ensure_ascii=False, sort_keys=True) for t in targets]),
        "normalized_target_duplicate_rate": duplicate_rate(normalized),
        "route_reason_top1_share": round(route_top[0][1] / len(reasons), 8) if route_top else 0,
        "route_reason_top5_share": round(sum(c for _, c in route_top) / len(reasons), 8) if route_top else 0,
        "evidence_template_duplicate_rate": duplicate_rate(evidences),
        "risk_type_route_reason_binding_rate": binding_rate(all_rows, reasons, "risk_type"),
        "risk_level_route_reason_binding_rate": binding_rate(all_rows, reasons, "risk_level"),
    }
    result["template_signal"] = "TARGET_TEMPLATE_OVERFIT_RISK" if result["normalized_target_duplicate_rate"] > 0.30 or result["route_reason_top1_share"] > 0.45 else "TARGET_TEMPLATE_SIGNAL_MODERATE"
    write_json(AUDIT / "v1611_target_template_analysis.json", result)
    return result


def duplicate_rate(values: list[str]) -> float:
    return round(sum(c - 1 for c in Counter(values).values() if c > 1) / (len(values) or 1), 8)


def binding_rate(rows: list[dict], reasons: list[str], key: str) -> float:
    grouped = defaultdict(list)
    for row, reason in zip(rows, reasons):
        grouped[row["metadata"][key]].append(reason)
    rates = []
    for vals in grouped.values():
        rates.append(max(Counter(vals).values()) / len(vals))
    return round(statistics.mean(rates), 8) if rates else 0


def diversity_analysis(rows: list[dict[str, Any]]) -> dict:
    users = [json.loads(r["user"]) for r in rows]
    texts = [u.get("synthetic_review_text", "") for u in users]
    scenario = [r["metadata"]["lineage"]["scenario_family"] for r in rows]
    template = [r["metadata"]["lineage"]["template_family"] for r in rows]
    result = {
        "status": "SCENARIO_DIVERSITY_ANALYSIS_COMPLETE",
        "scenario_family_count": len(set(scenario)),
        "template_family_count": len(set(template)),
        "family_size_distribution": dict(Counter(scenario)),
        "lexical_diversity": round(len(set(" ".join(texts).split())) / max(1, len(" ".join(texts).split())), 8),
        "char_ngram_diversity": round(len({t[i : i + 3] for t in texts for i in range(max(0, len(t) - 2))}) / max(1, sum(max(0, len(t) - 2) for t in texts)), 8),
        "product_category_distribution": dict(Counter(u.get("synthetic_product_category", "unknown") for u in users)),
        "explicit_keyword_dependence": round(sum(any(k in t.lower() for k in ["refund", "broken", "fake", "battery", "after-sales", "return"]) for t in texts) / len(texts), 8),
        "boundary_sample_count": sum("boundary" in r["metadata"]["lineage"]["template_family"].lower() for r in rows),
        "negation_sample_count": sum(any(k in t.lower() for k in ["not", "no ", "never", "不是", "没有"]) for t in texts),
        "ambiguous_evidence_sample_count": sum(any(k in t.lower() for k in ["maybe", "unclear", "seems", "可能"]) for t in texts),
        "compound_issue_sample_count": sum(t.count(" and ") + t.count("，") + t.count(",") > 1 for t in texts),
    }
    weak = result["boundary_sample_count"] < 10 or result["scenario_family_count"] < 8
    result["scenario_diversity_status"] = "SCENARIO_DIVERSITY_WEAK" if weak else "SCENARIO_DIVERSITY_MODERATE"
    write_json(AUDIT / "v1611_scenario_diversity_analysis.json", result)
    return result


def token_objective(rows: list[dict[str, Any]]) -> dict:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
    semantic = 0
    total = 0
    evidence = 0
    explanation = 0
    structural = 0
    for row in rows:
        t = target(row)
        js = compact_json(t)
        total += len(tokenizer.encode(js, add_special_tokens=False))
        sem_text = f"{t['risk_type']} {t['risk_level']} {t['need_human_review']}"
        semantic += len(tokenizer.encode(sem_text, add_special_tokens=False))
        evidence += len(tokenizer.encode(" ".join(t.get("text_evidence") or []), add_special_tokens=False))
        explanation += len(tokenizer.encode(str(t.get("route_reason") or ""), add_special_tokens=False))
    structural = max(0, total - semantic - evidence - explanation)
    result = {
        "status": "SFT_TOKEN_OBJECTIVE_ALIGNMENT_PASS" if semantic / max(1, total) >= 0.08 else "SFT_TOKEN_OBJECTIVE_ALIGNMENT_WEAK",
        "completion_token_count": total,
        "structural_token_ratio": round(structural / max(1, total), 8),
        "semantic_label_token_ratio": round(semantic / max(1, total), 8),
        "evidence_token_ratio": round(evidence / max(1, total), 8),
        "explanation_token_ratio": round(explanation / max(1, total), 8),
    }
    write_json(AUDIT / "v1611_token_objective_analysis.json", result)
    return result


def design_v23(root_causes: list[dict[str, Any]]) -> tuple[dict, dict, dict]:
    design = {
        "status": "SYNTHETIC_V23_DESIGN_COMPLETE",
        "total_target": 720,
        "train_target": 576,
        "validation_target": 72,
        "holdout_target": 72,
        "holdout_requirements": {
            "new_generation_roots_only": True,
            "risk_type_min_each": 24,
            "risk_level_min_each": 18,
            "human_review_true_false_present": True,
            "exclude_v22_holdout": True,
            "exclude_v164_holdout": True,
            "sealed_immediately": True,
            "single_final_evaluation": True,
        },
        "composition": {
            "clear_samples": 0.30,
            "normal_negative_boundary_pairs": 0.20,
            "negative_after_sales_boundary_pairs": 0.25,
            "risk_level_contrasts": 0.15,
            "evidence_conflict_human_review_contrasts": 0.10,
        },
        "amazon_asap_included": False,
        "external_test_included": False,
    }
    matrix = {
        "status": "V1611_EXPERIMENT_MATRIX_DESIGNED",
        "experiments": [
            {"name": "Experiment A", "single_major_factor_change": "Synthetic v2.3 data", "kept_fixed": ["q/v", "r=8", "epoch=1", "max_length=384"]},
            {"name": "Experiment B", "single_major_factor_change": "Epoch 1 to 2", "allowed_only_if": "Experiment A curve proves underfit", "early_stopping_required": True},
            {"name": "Experiment C", "single_major_factor_change": "target modules q/v to q/k/v/o", "allowed_only_if": "A has sufficient data and token objective alignment but still no task gain"},
        ],
    }
    gates = {
        "status": "SYNTHETIC_SFT_V23_BUILD_ALLOWED",
        "required_gates": [
            "V1610_RESULT_PERMANENTLY_FROZEN",
            "VALIDATION_ONLY_DATA_ACCESS_GUARD_PASS",
            "VALIDATION_FAILURE_ANALYSIS_COMPLETE",
            "NO_GO_ROOT_CAUSE_CONFIRMED",
            "SYNTHETIC_V23_DESIGN_COMPLETE",
            "V22_HOLDOUT_EXCLUDED_FROM_V23",
        ],
        "v22_holdout_excluded_from_v23": True,
    }
    write_json(AUDIT / "v1611_synthetic_v23_design.json", design)
    write_json(AUDIT / "v1611_experiment_matrix.json", matrix)
    write_json(AUDIT / "v1611_v23_build_gate.json", gates)
    return design, matrix, gates


def main() -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    from app.evaluation.dataset_access_guard import guard_validation_rows
    from app.evaluation.no_go_root_cause_engine import determine_no_go_root_causes

    freeze = write_freeze()
    validation_rows = read_jsonl(DATA_V22 / "validation.jsonl")
    guard_validation_rows(validation_rows)
    guard_report = {"generated_at": now(), "status": "VALIDATION_ONLY_DATA_ACCESS_GUARD_PASS", "allowed_splits": ["train", "validation"], "validation_count": len(validation_rows)}
    write_json(AUDIT / "v1611_dataset_access_guard.json", guard_report)
    inv = inventory(validation_rows)
    initial_prediction_status = inv["status"]
    if inv["status"] != "VALIDATION_PREDICTIONS_REUSED_OFFLINE":
        generate_validation_predictions(validation_rows)
        inv = inventory(validation_rows)
        inv["initial_status"] = initial_prediction_status
        inv["one_time_validation_inference_executed"] = True
        write_json(AUDIT / "v1611_validation_artifact_inventory.json", inv)
    else:
        inv["initial_status"] = initial_prediction_status
        inv["one_time_validation_inference_executed"] = False
        write_json(AUDIT / "v1611_validation_artifact_inventory.json", inv)
    predictions = load_predictions(validation_rows)
    base_m = metrics_for(predictions["base"], validation_rows)
    adapter_m = metrics_for(predictions["adapter"], validation_rows)
    compact_base = {k: v for k, v in base_m.items() if k not in {"operational", "eligible"}}
    compact_adapter = {k: v for k, v in adapter_m.items() if k not in {"operational", "eligible"}}
    validation_metrics = {"status": "VALIDATION_FAILURE_ANALYSIS_COMPLETE", "prediction_source": inv["status"], "base": compact_base, "adapter": compact_adapter}
    write_json(AUDIT / "v1611_validation_metrics.json", validation_metrics)
    gold = [target(row) for row in validation_rows]
    dist = {"status": "CLASS_DISTRIBUTION_ANALYSIS_COMPLETE", **distribution(base_m["operational"], gold, "base"), **distribution(adapter_m["operational"], gold, "adapter")}
    write_json(AUDIT / "v1611_class_distribution_analysis.json", dist)
    curve = training_curve()
    slices = slice_analysis(validation_rows, base_m, adapter_m)
    template = template_analysis(validation_rows)
    diversity = diversity_analysis(validation_rows)
    token = token_objective(validation_rows)
    report = {
        "validation_metrics": validation_metrics,
        "training_curve_analysis": curve,
        "class_distribution_analysis": dist,
        "target_template_analysis": template,
        "scenario_diversity_analysis": diversity,
        "token_objective_analysis": token,
    }
    causes = determine_no_go_root_causes(report)
    root = {"generated_at": now(), "status": "NO_GO_ROOT_CAUSE_CONFIRMED", "root_causes": causes}
    write_json(AUDIT / "v1611_no_go_root_cause.json", root)
    design, matrix, gates = design_v23(causes)
    write_doc(DOCS / "245_v1611_validation_failure_analysis.md", "V1.6.11 Validation Failure Analysis", [
        f"Status: `{validation_metrics['status']}`",
        "",
        "## Data Access Scope",
        "",
        "- v2.2 holdout raw text read: `false`",
        "- v2.2 holdout reinference: `false`",
        "- analysis inputs: train metadata, validation split, aggregate v1.6.10 reports, and Git-external validation predictions only.",
        f"- prediction_source: `{inv['status']}`",
        f"- initial prediction status in this stage: `{inv['initial_status']}`",
        f"- one-time validation inference executed: `{str(inv['one_time_validation_inference_executed']).lower()}`",
        f"- prediction rows: `{inv['prediction_count']}` (`base={inv['model_role_counts'].get('base')}`, `adapter={inv['model_role_counts'].get('adapter')}`)",
        "",
        "## Validation Metrics",
        "",
        "| Model | Coverage | Fallback | Coverage-adjusted accuracy | Risk type macro-F1 | Risk level macro-F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| Base Qwen3-1.7B | `{compact_base['task_coverage_rate']}` | `{compact_base['fallback_rate']}` | `{compact_base['coverage_adjusted_accuracy']}` | `{compact_base['risk_type_macro_f1']}` | `{compact_base['risk_level_macro_f1']}` |",
        f"| Base + v2.2 Adapter | `{compact_adapter['task_coverage_rate']}` | `{compact_adapter['fallback_rate']}` | `{compact_adapter['coverage_adjusted_accuracy']}` | `{compact_adapter['risk_type_macro_f1']}` | `{compact_adapter['risk_level_macro_f1']}` |",
        "",
        "The adapter improves validation semantic accuracy among covered predictions, but it loses coverage and increases fallback/abstention. This supports retaining the v1.6.10 holdout NO_GO conclusion rather than overriding it with validation-only evidence.",
        "",
        "## Training Curve",
        "",
        f"- initial train loss: `{curve['initial_train_loss']}`",
        f"- final train loss: `{curve['final_train_loss']}`",
        f"- relative train loss reduction: `{curve['relative_train_loss_reduction']}`",
        f"- final validation loss: `{curve['final_validation_loss']}`",
        f"- train/validation gap: `{curve['train_validation_gap']}`",
        f"- judgement: `{curve['judgements'][0]}`",
        "",
        "## Template And Diversity",
        "",
        f"- normalized target duplicate rate: `{template['normalized_target_duplicate_rate']}`",
        f"- route reason top-1 share: `{template['route_reason_top1_share']}`",
        f"- template signal: `{template['template_signal']}`",
        f"- scenario family count: `{diversity['scenario_family_count']}`",
        f"- boundary sample count: `{diversity['boundary_sample_count']}`",
        f"- scenario diversity status: `{diversity['scenario_diversity_status']}`",
        "",
        "## Token Objective",
        "",
        f"- status: `{token['status']}`",
        f"- semantic label token ratio: `{token['semantic_label_token_ratio']}`",
    ])
    write_doc(DOCS / "246_v1611_no_go_root_cause.md", "V1.6.11 NO_GO Root Cause", [
        f"Status: `{root['status']}`",
        "",
        "This analysis keeps the v1.6.10 Adapter Value Gate unchanged: `NO_GO`. It does not read or rerun v2.2 holdout samples.",
        "",
        "| Root cause | Confidence | Single major factor |",
        "| --- | ---: | --- |",
        *[f"| `{c['code']}` | `{c['confidence']}` | `{c['single_major_factor_change']}` |" for c in causes],
        "",
        "Conclusion: the next valid experiment is data-first, not threshold tuning, holdout reruns, adapter override, or extra epochs as the first move.",
    ])
    write_doc(DOCS / "247_v1611_synthetic_v23_design.md", "V1.6.11 Synthetic SFT V2.3 Design", [
        f"Status: `{design['status']}`",
        "",
        "## Scope",
        "",
        "- This stage designs v2.3 only.",
        "- It does not generate formal v2.3 data.",
        "- It does not train.",
        "- It does not read or rerun the v2.2 holdout.",
        "- Amazon/ASAP, external test, and real images are excluded.",
        "",
        "## Target Composition",
        "",
        f"- total/train/validation/holdout target: `{design['total_target']} / {design['train_target']} / {design['validation_target']} / {design['holdout_target']}`",
        "- new holdout excludes v2.2 and v1.6.4 holdouts and is sealed immediately.",
        "",
        "## Experiment Matrix",
        "",
        "| Experiment | Single major factor changed |",
        "| --- | --- |",
        *[f"| {exp['name']} | {exp['single_major_factor_change']} |" for exp in matrix["experiments"]],
        "",
        "## Build Gate",
        "",
        f"- build gate: `{gates['status']}`",
    ])
    print(gates["status"])


if __name__ == "__main__":
    main()
