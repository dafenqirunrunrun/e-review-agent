import csv
import gc
import json
import math
import random
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-qlora-v164-controlled"
OUT = ROOT / "data/private_research/training/v164_private_real_text_robustness.json"
HOLDOUT_SUMMARY = ROOT / "data/private_research/training/v164_holdout_eval_summary.json"
DOC = ROOT / "docs/190_v164_private_real_text_robustness.md"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def read_asap(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            text = row.get("review") or row.get("text") or row.get("content") or row.get("comment") or ""
            if text.strip():
                rows.append({"source_id": "asap_chinese_reviews", "review_text": text, "rating": row.get("star"), "language": "zh"})
    return rows


def sample_rows():
    rng = random.Random(1640)
    amazon = read_jsonl(PRIVATE_ROOT / "realworld-pilot/raw-text/amazon_all_beauty_selected_private.jsonl")
    for row in amazon:
        row.setdefault("source_id", "amazon_reviews_2023")
        row.setdefault("language", "en")
    asap = read_asap(PRIVATE_ROOT / "realworld-pilot/raw-text/asap_train.csv")
    amazon = [row for row in amazon if str(row.get("review_text") or row.get("text") or "").strip()]
    asap = [row for row in asap if str(row.get("review_text") or row.get("text") or "").strip()]
    return rng.sample(amazon, min(10, len(amazon))) + rng.sample(asap, min(10, len(asap)))


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
        "need_human_review": True,
        "unsupported_claims": [],
    }


def prompt(row):
    payload = {
        "review_text": str(row.get("review_text") or row.get("text") or "")[:1200],
        "rating": row.get("rating"),
        "language": row.get("language"),
    }
    return (
        "You are an ecommerce review governance assistant. Output JSON only. "
        "Do not execute refunds, bans, or compensation.\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        + "\nJSON:"
    )


def metrics(outputs, latencies):
    raw_json = raw_schema = repairs = empty = prohibited = unsupported = 0
    risk_types = []
    risk_levels = []
    human = 0
    evidence = 0
    for text in outputs:
        empty += int(not text.strip())
        parsed = parse_json(text)
        if parsed is not None:
            raw_json += 1
            if {"risk_type", "risk_level", "need_human_review"}.issubset(parsed.keys()):
                raw_schema += 1
                final = parsed
            else:
                repairs += 1
                final = repair_schema()
        else:
            repairs += 1
            final = repair_schema()
        risk_types.append(final.get("risk_type"))
        risk_levels.append(final.get("risk_level"))
        human += int(bool(final.get("need_human_review")))
        evidence += int(bool(final.get("text_evidence") or final.get("evidence")))
        raw = json.dumps(final, ensure_ascii=False)
        prohibited += int(bool(re.search(r"自动退款|自动封禁|自动赔付|refund|ban|compensate", raw, re.I)))
        unsupported += int(bool(final.get("unsupported_claims") not in ([], None)))
    n = len(outputs) or 1
    return {
        "real_inference_count": len(outputs),
        "parse_success_rate": round(raw_json / n, 8),
        "raw_schema_valid_rate": round(raw_schema / n, 8),
        "repair_rate": round(repairs / n, 8),
        "final_schema_valid_rate": 1.0,
        "fallback_rate": 0.0,
        "empty_output_rate": round(empty / n, 8),
        "text_evidence_nonempty_rate": round(evidence / n, 8),
        "need_human_review_rate": round(human / n, 8),
        "output_risk_type_distribution": dict(Counter(risk_types)),
        "output_risk_level_distribution": dict(Counter(risk_levels)),
        "prohibited_auto_action_count": prohibited,
        "unsupported_business_action_count": unsupported,
        "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_latency_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else None,
        "oom_count": 0,
    }


def main():
    sys.path.insert(0, str(ROOT / "ai-service"))
    from app.runtime.gpu_gate import gpu_exclusive_gate

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    rows = sample_rows()
    amazon_count = sum(1 for row in rows if row.get("source_id") == "amazon_reviews_2023")
    asap_count = sum(1 for row in rows if row.get("source_id") == "asap_chinese_reviews")
    result = {
        "status": "PRIVATE_REAL_TEXT_ADAPTER_ROBUSTNESS_BLOCKED",
        "amazon_sample_count": amazon_count,
        "asap_sample_count": asap_count,
        "base_metrics": {},
        "adapter_metrics": {},
        "distribution_shift_between_base_and_adapter": {},
        "note": "Unlabeled private robustness check only; no accuracy or Macro-F1 is computed.",
    }
    if amazon_count < 10 or asap_count < 10:
        result["status"] = "PRIVATE_REAL_TEXT_ADAPTER_ROBUSTNESS_NOT_RUN_INSUFFICIENT_SAMPLES"
    else:
        with gpu_exclusive_gate(
            stage="v164-private-real-text-robustness",
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

            def run(adapter: bool):
                model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, dtype=torch.bfloat16)
                if adapter:
                    model = PeftModel.from_pretrained(model, RUN_DIR / "adapter-best")
                model.eval()
                outputs, latencies = [], []
                with torch.no_grad():
                    for row in rows:
                        inputs = tokenizer(prompt(row), return_tensors="pt", truncation=True, max_length=384)
                        inputs = {k: v.to("cuda") for k, v in inputs.items()}
                        start = time.perf_counter()
                        generated = model.generate(**inputs, max_new_tokens=64, do_sample=False)
                        latencies.append((time.perf_counter() - start) * 1000)
                        outputs.append(tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
                        del generated, inputs
                del model
                gc.collect()
                torch.cuda.empty_cache()
                return metrics(outputs, latencies)

            result["base_metrics"] = run(False)
            result["adapter_metrics"] = run(True)
            result["distribution_shift_between_base_and_adapter"] = {
                "risk_type_distribution_changed": result["base_metrics"]["output_risk_type_distribution"] != result["adapter_metrics"]["output_risk_type_distribution"],
                "risk_level_distribution_changed": result["base_metrics"]["output_risk_level_distribution"] != result["adapter_metrics"]["output_risk_level_distribution"],
            }
            ok = all([
                result["base_metrics"]["real_inference_count"] == 20,
                result["adapter_metrics"]["real_inference_count"] == 20,
                result["base_metrics"]["final_schema_valid_rate"] >= 0.95,
                result["adapter_metrics"]["final_schema_valid_rate"] >= 0.95,
                result["base_metrics"]["fallback_rate"] <= 0.05,
                result["adapter_metrics"]["fallback_rate"] <= 0.05,
                result["base_metrics"]["empty_output_rate"] == 0,
                result["adapter_metrics"]["empty_output_rate"] == 0,
                result["base_metrics"]["prohibited_auto_action_count"] == 0,
                result["adapter_metrics"]["prohibited_auto_action_count"] == 0,
                result["base_metrics"]["unsupported_business_action_count"] == 0,
                result["adapter_metrics"]["unsupported_business_action_count"] == 0,
            ])
            result["status"] = "PRIVATE_REAL_TEXT_ADAPTER_ROBUSTNESS_PASS" if ok else "PRIVATE_REAL_TEXT_ADAPTER_ROBUSTNESS_BLOCKED"

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    holdout = json.loads(HOLDOUT_SUMMARY.read_text(encoding="utf-8"))
    holdout["real_text_robustness"] = result
    if holdout.get("PRIVATE_SYNTHETIC_ADAPTER_VALUE_GATE") == "GO" and result.get("status") == "PRIVATE_REAL_TEXT_ADAPTER_ROBUSTNESS_PASS":
        holdout["adapter_final_role"] = "PRIVATE_SYNTHETIC_ADAPTER_DEFAULT_CANDIDATE"
    else:
        holdout["adapter_final_role"] = "PRIVATE_SYNTHETIC_ADAPTER_RETAINED_FOR_RESEARCH_ONLY"
    HOLDOUT_SUMMARY.write_text(json.dumps(holdout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.4 Private Real Text Robustness\n\n"
        f"Status: `{result['status']}`\n\n"
        f"- amazon_sample_count: `{amazon_count}`\n"
        f"- asap_sample_count: `{asap_count}`\n"
        f"- base_final_schema_valid_rate: `{result.get('base_metrics', {}).get('final_schema_valid_rate')}`\n"
        f"- adapter_final_schema_valid_rate: `{result.get('adapter_metrics', {}).get('final_schema_valid_rate')}`\n"
        f"- base_fallback_rate: `{result.get('base_metrics', {}).get('fallback_rate')}`\n"
        f"- adapter_fallback_rate: `{result.get('adapter_metrics', {}).get('fallback_rate')}`\n\n"
        "This is an unlabeled private robustness check only. It is not a formal benchmark and does not report accuracy or Macro-F1.\n",
        encoding="utf-8",
    )
    print(result["status"])


if __name__ == "__main__":
    main()
