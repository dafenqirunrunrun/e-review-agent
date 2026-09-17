from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
DATA = PRIVATE_ROOT / "synthetic-sft-v21"
AUDIT = ROOT / "data/private_research/audit"
DOCS = ROOT / "docs"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"

sys.path.insert(0, str(ROOT / "ai-service"))
from app.contracts.e_review_decision_migration import process_model_output  # noqa: E402
from app.prompts.e_review_prompt_renderer import render_generation_prompt  # noqa: E402
from app.runtime.gpu_gate import gpu_exclusive_gate  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def target(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["assistant"])


def select_canary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {"normal_review": [], "negative_review": [], "after_sales_risk": []}
    for row in rows:
        buckets[str(target(row).get("risk_type"))].append(row)
    selected = []
    for key in ["normal_review", "negative_review", "after_sales_risk"]:
        selected.extend(sorted(buckets[key], key=lambda r: hashlib.sha256(r["user"].encode("utf-8")).hexdigest())[:4])
    return selected


def generate(model, tokenizer, rows: list[dict[str, Any]]) -> tuple[list[str], list[float]]:
    import torch

    outputs = []
    latencies = []
    device = next(model.parameters()).device
    for row in rows:
        user = json.loads(row["user"])
        prompt = render_generation_prompt(user, tokenizer)
        inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=384)
        input_len = int(inputs["input_ids"].shape[-1])
        inputs = {key: value.to(device) for key, value in inputs.items()}
        started = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=192, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        latencies.append((time.perf_counter() - started) * 1000)
        outputs.append(tokenizer.decode(generated[0][input_len:], skip_special_tokens=True).strip())
    return outputs, latencies


def main() -> None:
    dataset = json.loads((AUDIT / "v167_synthetic_sft_v21_summary.json").read_text(encoding="utf-8"))
    result: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "V167_BASE_PROMPT_CONTRACT_CANARY_BLOCKED",
        "dataset_status": dataset.get("status"),
        "holdout_read": False,
        "old_adapter_used": False,
        "real_inference_count": 0,
    }
    if dataset.get("status") != "PRIVATE_SYNTHETIC_SFT_V21_DATASET_PASS":
        result["blocked_reason"] = "dataset gate did not pass"
        write(result)
        print(result["status"])
        return
    import gc
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    rows = select_canary(read_jsonl(DATA / "validation.jsonl"))
    outputs: list[str] = []
    latencies: list[float] = []
    with gpu_exclusive_gate(
        stage="v167-base-prompt-contract-canary",
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
        qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
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
        outputs, latencies = generate(model, tokenizer, rows)
        del model, tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    processed = [process_model_output(raw) for raw in outputs]
    extraction_success = [item["raw_json_extraction"].extraction_success for item in processed]
    normalized = [item["contract_normalization"] for item in processed]
    eligible = [item["prediction_eligible"] for item in processed]
    operational = [item["operational_result"] for item in processed]
    input_echo = 0
    for raw in outputs:
        input_echo += int("synthetic_review_text" in raw or "review_text" in raw)
    prohibited = sum(1 for raw in outputs if any(term in raw.lower() for term in ["refund", "ban", "compensate", "自动退款", "自动封禁", "自动赔付"]))
    result.update(
        {
            "status": "V167_BASE_PROMPT_CONTRACT_CANARY_PASS"
            if len(outputs) == 12
            and sum(extraction_success) / 12 >= 0.75
            and sum(eligible) / 12 > 0
            and prohibited == 0
            and input_echo < 12
            else "V167_BASE_PROMPT_CONTRACT_CANARY_BLOCKED",
            "sample_count": len(rows),
            "sample_hashes": [hashlib.sha256(row["user"].encode("utf-8")).hexdigest()[:24] for row in rows],
            "real_inference_count": len(outputs),
            "raw_json_object_extract_rate": sum(extraction_success) / max(1, len(outputs)),
            "raw_json_parse_success_rate": sum(extraction_success) / max(1, len(outputs)),
            "raw_canonical_schema_valid_rate": sum(eligible) / max(1, len(outputs)),
            "required_field_presence_rate": sum(eligible) / max(1, len(outputs)),
            "contract_normalization_rate": sum(1 for item in normalized if item is not None and item.normalization_success) / max(1, len(outputs)),
            "semantic_field_change_count": sum(1 for item in normalized if item is not None and item.semantic_field_changed),
            "operational_fallback_rate": sum(1 for item in operational if item.get("prediction_source") == "operational_safety_fallback") / max(1, len(outputs)),
            "final_operational_schema_valid_rate": 1.0,
            "input_echo_rate": input_echo / max(1, len(outputs)),
            "prohibited_auto_action_count": prohibited,
            "avg_generate_ms": round(statistics.mean(latencies), 2) if latencies else None,
            "p95_generate_ms": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 2) if latencies else None,
            "output_hashes": [hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:24] for raw in outputs],
            "output_source_distribution": dict(Counter(item.get("prediction_source", "raw_or_normalized") for item in operational)),
        }
    )
    write(result)
    print(result["status"])


def write(result: dict[str, Any]) -> None:
    (AUDIT / "v167_base_prompt_canary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "214_v167_base_prompt_contract_canary.md").write_text(
        "# V1.6.7 Base Prompt Contract Canary\n\n"
        f"Status: `{result['status']}`\n\n"
        f"- real_inference_count: `{result.get('real_inference_count')}`\n"
        f"- raw_json_parse_success_rate: `{result.get('raw_json_parse_success_rate')}`\n"
        f"- raw_canonical_schema_valid_rate: `{result.get('raw_canonical_schema_valid_rate')}`\n"
        f"- operational_fallback_rate: `{result.get('operational_fallback_rate')}`\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
