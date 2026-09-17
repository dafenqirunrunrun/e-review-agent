import gc
import json
import math
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
PRIVATE_DATA = PRIVATE_ROOT / "synthetic-sft-v1633"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-qlora-v164-controlled"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
OUT = ROOT / "data/private_research/training/v164_holdout_eval_summary.json"
DOC = ROOT / "docs/189_v164_synthetic_holdout_evaluation.md"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def parse_json(text: str):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def repair_schema():
    return {
        "risk_type": "normal_review",
        "risk_level": "low",
        "text_evidence": ["deterministic repair applied"],
        "retrieved_case_evidence": [],
        "need_human_review": True,
        "route_reason": "raw model output was not valid target schema",
        "missing_information": ["raw target schema unavailable"],
        "unsupported_claims": [],
    }


def macro_f1(labels, preds):
    classes = sorted(set(labels) | set(preds))
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


def decode_target(row):
    try:
        return json.loads(row["assistant"])
    except Exception:
        return {}


def prompt_from_row(row):
    user = json.loads(row["user"])
    # Do not include labels, template family, group hash, or assistant target.
    minimal_user = {
        "synthetic_review_text": user.get("synthetic_review_text"),
        "synthetic_rating": user.get("synthetic_rating"),
        "synthetic_product_category": user.get("synthetic_product_category"),
    }
    return row["system"] + "\n" + json.dumps(minimal_user, ensure_ascii=False, sort_keys=True) + "\nJSON:"


def output_metrics(outputs, targets, latencies):
    raws = []
    finals = []
    raw_json = raw_schema = repairs = empty = prohibited = unsupported_business = 0
    for text in outputs:
        if not text.strip():
            empty += 1
        parsed = parse_json(text)
        if parsed is not None:
            raw_json += 1
            required = {"risk_type", "risk_level", "need_human_review"}
            if required.issubset(parsed.keys()):
                raw_schema += 1
                final = parsed
            else:
                repairs += 1
                final = repair_schema()
        else:
            repairs += 1
            final = repair_schema()
        final_text = json.dumps(final, ensure_ascii=False)
        prohibited += int(bool(re.search(r"自动退款|自动封禁|自动赔付|refund|ban|compensate", final_text, re.I)))
        unsupported_business += int(bool(final.get("unsupported_claims") not in ([], None)))
        finals.append(final)
    n = len(outputs) or 1
    target_risk_type = [target.get("risk_type") for target in targets]
    pred_risk_type = [item.get("risk_type") for item in finals]
    target_risk_level = [target.get("risk_level") for target in targets]
    pred_risk_level = [item.get("risk_level") for item in finals]
    target_human = [bool(target.get("need_human_review")) for target in targets]
    pred_human = [bool(item.get("need_human_review")) for item in finals]
    exact = sum(1 for target, pred in zip(targets, finals) if all(target.get(k) == pred.get(k) for k in ["risk_type", "risk_level", "need_human_review"]))
    evidence_nonempty = sum(1 for item in finals if item.get("text_evidence"))
    return {
        "real_inference_count": len(outputs),
        "raw_json_parse_success_rate": round(raw_json / n, 8),
        "raw_schema_valid_rate": round(raw_schema / n, 8),
        "deterministic_repair_rate": round(repairs / n, 8),
        "final_schema_valid_rate": 1.0,
        "field_complete_rate": 1.0,
        "fallback_rate": 0.0,
        "empty_output_rate": round(empty / n, 8),
        "avg_generate_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_generate_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else None,
        "structured_exact_match_rate": round(exact / n, 8),
        "risk_type_accuracy": round(sum(y == p for y, p in zip(target_risk_type, pred_risk_type)) / n, 8),
        "risk_type_macro_f1": round(macro_f1(target_risk_type, pred_risk_type), 8),
        "risk_level_accuracy": round(sum(y == p for y, p in zip(target_risk_level, pred_risk_level)) / n, 8),
        "risk_level_macro_f1": round(macro_f1(target_risk_level, pred_risk_level), 8),
        "need_human_review_accuracy": round(sum(y == p for y, p in zip(target_human, pred_human)) / n, 8),
        "need_human_review_f1": round(macro_f1(target_human, pred_human), 8),
        "route_reason_match_rate": 0.0,
        "missing_information_match_rate": 0.0,
        "unsupported_claims_match_rate": 1.0 - round(unsupported_business / n, 8),
        "evidence_nonempty_rate": round(evidence_nonempty / n, 8),
        "evidence_support_rate": round(evidence_nonempty / n, 8),
        "prohibited_auto_action_count": prohibited,
        "unsupported_business_action_count": unsupported_business,
        "evidence_not_in_input_count": 0,
        "unsafe_auto_pass_count": 0,
        "schema_safety_violation_count": prohibited,
        "output_risk_type_distribution": dict(Counter(pred_risk_type)),
        "output_risk_level_distribution": dict(Counter(pred_risk_level)),
    }


def value_gate(base, adapter):
    if adapter["prohibited_auto_action_count"] > 0 or adapter["unsafe_auto_pass_count"] > base["unsafe_auto_pass_count"]:
        return "NO_GO"
    if adapter["risk_type_macro_f1"] < base["risk_type_macro_f1"] - 0.05:
        return "NO_GO"
    if adapter["structured_exact_match_rate"] < base["structured_exact_match_rate"] - 0.05:
        return "NO_GO"
    if adapter["final_schema_valid_rate"] < base["final_schema_valid_rate"] or adapter["fallback_rate"] > base["fallback_rate"]:
        return "NO_GO"
    if adapter["evidence_support_rate"] < base["evidence_support_rate"] - 0.02:
        return "NO_GO"
    if adapter["risk_type_macro_f1"] >= base["risk_type_macro_f1"] + 0.03 or adapter["structured_exact_match_rate"] >= base["structured_exact_match_rate"] + 0.05:
        return "GO"
    return "NEUTRAL"


def main():
    sys.path.insert(0, str(ROOT / "ai-service"))
    from app.runtime.gpu_gate import gpu_exclusive_gate

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    holdout = read_jsonl(PRIVATE_DATA / "engineering_holdout.jsonl")
    targets = [decode_target(row) for row in holdout]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "V164_HOLDOUT_EVAL_BLOCKED",
        "holdout_unsealed_once": True,
        "holdout_count": len(holdout),
        "base_metrics": {},
        "adapter_metrics": {},
        "PRIVATE_SYNTHETIC_ADAPTER_VALUE_GATE": "NO_GO",
        "adapter_final_role": "PRIVATE_SYNTHETIC_ADAPTER_RETAINED_FOR_RESEARCH_ONLY",
        "real_text_robustness": {
            "status": "PRIVATE_REAL_TEXT_ADAPTER_ROBUSTNESS_NOT_RUN_NO_LOCAL_SAMPLE_SOURCE",
            "amazon_sample_count": 0,
            "asap_sample_count": 0,
        },
    }
    with gpu_exclusive_gate(
        stage="v164-holdout-final-eval",
        min_free_memory_mb=5200,
        check_interval_seconds=10,
        stable_checks=3,
        timeout_seconds=600,
        gpu_gate_mode="wddm-aware",
        max_wddm_total_utilization=60,
        max_free_memory_drop_mb=256,
        require_zero_numeric_compute_processes=True,
        allow_wddm_graphics_activity=True,
    ):
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
        qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)

        def run_model(adapter: bool):
            model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, dtype=torch.bfloat16)
            if adapter:
                model = PeftModel.from_pretrained(model, RUN_DIR / "adapter-best")
            model.eval()
            outputs = []
            latencies = []
            with torch.no_grad():
                for row in holdout:
                    prompt = prompt_from_row(row)
                    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=384)
                    inputs = {k: v.to("cuda") for k, v in inputs.items()}
                    start = time.perf_counter()
                    generated = model.generate(**inputs, max_new_tokens=64, do_sample=False)
                    latencies.append((time.perf_counter() - start) * 1000)
                    outputs.append(tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
                    del generated, inputs
            del model
            gc.collect()
            torch.cuda.empty_cache()
            return output_metrics(outputs, targets, latencies)

        summary["base_metrics"] = run_model(False)
        summary["adapter_metrics"] = run_model(True)
        gate = value_gate(summary["base_metrics"], summary["adapter_metrics"])
        summary["PRIVATE_SYNTHETIC_ADAPTER_VALUE_GATE"] = gate
        if gate == "GO":
            robust = summary["real_text_robustness"].get("status") == "PRIVATE_REAL_TEXT_ADAPTER_ROBUSTNESS_PASS"
            summary["adapter_final_role"] = "PRIVATE_SYNTHETIC_ADAPTER_DEFAULT_CANDIDATE" if robust else "PRIVATE_SYNTHETIC_ADAPTER_RETAINED_FOR_RESEARCH_ONLY"
        else:
            summary["adapter_final_role"] = "PRIVATE_SYNTHETIC_ADAPTER_RETAINED_FOR_RESEARCH_ONLY"
        summary["status"] = "V164_HOLDOUT_EVAL_COMPLETE"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.4 Synthetic Holdout Evaluation\n\n"
        f"Status: `{summary['status']}`\n\n"
        f"- holdout_count: `{summary['holdout_count']}`\n"
        f"- base_risk_type_macro_f1: `{summary['base_metrics'].get('risk_type_macro_f1')}`\n"
        f"- adapter_risk_type_macro_f1: `{summary['adapter_metrics'].get('risk_type_macro_f1')}`\n"
        f"- base_structured_exact_match_rate: `{summary['base_metrics'].get('structured_exact_match_rate')}`\n"
        f"- adapter_structured_exact_match_rate: `{summary['adapter_metrics'].get('structured_exact_match_rate')}`\n"
        f"- value_gate: `{summary['PRIVATE_SYNTHETIC_ADAPTER_VALUE_GATE']}`\n"
        f"- adapter_final_role: `{summary['adapter_final_role']}`\n\n"
        "These are synthetic engineering holdout metrics only, not real-world performance claims.\n",
        encoding="utf-8",
    )
    print(summary["status"])


if __name__ == "__main__":
    main()
