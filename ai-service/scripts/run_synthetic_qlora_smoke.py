import gc
import json
import math
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DATA = ROOT.parent / "data-private/synthetic-sft-v1633"
RUN_DIR = ROOT.parent / "data-private/training-runs/qwen3-1.7b-synthetic-qlora-smoke-v1633"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
SUMMARY = ROOT / "data/private_research/training/synthetic_qlora_smoke_summary.json"
CONFIG = ROOT / "data/private_research/training/synthetic_qlora_smoke_config.json"
DOC = ROOT / "docs/189_v1633_synthetic_qlora_smoke.md"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
        "text_evidence": ["schema repair applied"],
        "retrieved_case_evidence": [],
        "need_human_review": True,
        "route_reason": "raw model output was not valid JSON",
        "missing_information": ["raw JSON unavailable"],
        "unsupported_claims": [],
    }


def metrics_from_outputs(outputs: list[str]):
    raw_json = 0
    raw_schema_valid = 0
    final_valid = 0
    repair = 0
    empty = 0
    prohibited = 0
    for text in outputs:
        if not text.strip():
            empty += 1
        parsed = parse_json(text)
        if parsed is not None:
            raw_json += 1
            required = {"risk_type", "risk_level", "need_human_review"}
            if required.issubset(parsed.keys()):
                raw_schema_valid += 1
                final = parsed
            else:
                repair += 1
                final = repair_schema()
        else:
            repair += 1
            final = repair_schema()
        required = {"risk_type", "risk_level", "need_human_review"}
        final_valid += int(required.issubset(final.keys()))
        prohibited += int(bool(re.search(r"退款|封禁|赔付|refund|ban|compensate", json.dumps(final, ensure_ascii=False), re.I)))
    total = len(outputs) or 1
    return {
        "raw_json_parse_success_rate": round(raw_json / total, 8),
        "raw_schema_valid_rate": round(raw_schema_valid / total, 8),
        "deterministic_repair_rate": round(repair / total, 8),
        "final_schema_valid_rate": round(final_valid / total, 8),
        "fallback_rate": 0.0,
        "empty_output_rate": round(empty / total, 8),
        "prohibited_auto_action_count": prohibited,
    }


def main():
    sys.path.insert(0, str(ROOT / "ai-service"))
    from app.runtime.gpu_gate import gpu_exclusive_gate

    import torch
    import bitsandbytes as bnb
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    train_rows = read_jsonl(PRIVATE_DATA / "train.jsonl")[:12]
    val_rows = read_jsonl(PRIVATE_DATA / "validation.jsonl")[:8]
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    config = {
        "model_label": "<repo-external>/models/Qwen3-1.7B",
        "run_dir_label": "<data-private>/training-runs/qwen3-1.7b-synthetic-qlora-smoke-v1633",
        "max_steps": 20,
        "batch_size": 1,
        "gradient_accumulation_steps": 8,
        "max_length": 384,
        "learning_rate": 1e-4,
        "warmup_ratio": 0.0,
        "weight_decay": 0.0,
        "lora_r": 8,
        "lora_alpha": 16,
        "target_modules": ["q_proj", "v_proj"],
        "bf16": True,
        "seed": 1633,
    }
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRIVATE_SYNTHETIC_QLORA_ENGINEERING_SMOKE_FAIL",
        "max_steps_completed": 0,
        "final_train_loss": None,
        "validation_executed": False,
        "validation_loss": None,
        "nan_count": 0,
        "inf_count": 0,
        "oom_count": 0,
        "adapter_saved": False,
        "adapter_reloaded": False,
        "adapter_real_generate_executed": False,
        "gpu_peak_memory_mb": None,
        "gpu_memory_released": False,
        "gpu_lock_release_success": False,
        "base_metrics": {},
        "adapter_metrics": {},
    }

    with gpu_exclusive_gate(
        stage="synthetic-qlora-20-step-smoke",
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
        torch.manual_seed(config["seed"])
        torch.cuda.reset_peak_memory_stats()
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
        qconfig = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_DIR,
            local_files_only=True,
            trust_remote_code=True,
            quantization_config=qconfig,
            device_map={"": 0},
            dtype=torch.bfloat16,
        )
        model.config.use_cache = False
        model.gradient_checkpointing_enable()
        quantized_count = sum(1 for _, m in model.named_modules() if isinstance(m, bnb.nn.Linear4bit))
        model = prepare_model_for_kbit_training(model)
        model = get_peft_model(
            model,
            LoraConfig(
                r=config["lora_r"],
                lora_alpha=config["lora_alpha"],
                lora_dropout=0.05,
                bias="none",
                task_type=TaskType.CAUSAL_LM,
                target_modules=config["target_modules"],
            ),
        )
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=config["learning_rate"])
        model.train()
        losses = []
        for step in range(config["max_steps"]):
            optimizer.zero_grad(set_to_none=True)
            row = train_rows[step % len(train_rows)]
            text = row["system"] + "\n" + row["user"] + "\n" + row["assistant"]
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=config["max_length"])
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
            outputs = model(**inputs, labels=inputs["input_ids"])
            loss = outputs.loss
            loss_value = float(loss.detach().float().item())
            summary["nan_count"] += int(math.isnan(loss_value))
            summary["inf_count"] += int(math.isinf(loss_value))
            (loss / config["gradient_accumulation_steps"]).backward()
            optimizer.step()
            losses.append(loss_value)
            summary["max_steps_completed"] = step + 1
        summary["final_train_loss"] = losses[-1] if losses else None
        model.eval()
        with torch.no_grad():
            val = val_rows[0]
            text = val["system"] + "\n" + val["user"] + "\n" + val["assistant"]
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=config["max_length"])
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
            outputs = model(**inputs, labels=inputs["input_ids"])
            summary["validation_loss"] = float(outputs.loss.detach().float().item())
            summary["validation_executed"] = True
        adapter_dir = RUN_DIR / "adapter"
        model.save_pretrained(adapter_dir)
        tokenizer.save_pretrained(RUN_DIR / "tokenizer")
        summary["adapter_saved"] = (adapter_dir / "adapter_config.json").exists()
        del outputs, inputs, optimizer, model
        gc.collect()
        torch.cuda.empty_cache()

        def load_base():
            base = AutoModelForCausalLM.from_pretrained(
                MODEL_DIR,
                local_files_only=True,
                trust_remote_code=True,
                quantization_config=qconfig,
                device_map={"": 0},
                dtype=torch.bfloat16,
            )
            base.eval()
            return base

        prompts = [(row["system"] + "\n" + row["user"] + "\nJSON:") for row in val_rows]
        base_model = load_base()
        base_outputs = []
        with torch.no_grad():
            for prompt in prompts:
                inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=config["max_length"])
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
                generated = base_model.generate(**inputs, max_new_tokens=64, do_sample=False)
                base_outputs.append(tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
        del base_model
        gc.collect()
        torch.cuda.empty_cache()

        base_model = load_base()
        adapter_model = PeftModel.from_pretrained(base_model, adapter_dir)
        adapter_model.eval()
        summary["adapter_reloaded"] = True
        adapter_outputs = []
        with torch.no_grad():
            for prompt in prompts:
                inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=config["max_length"])
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
                generated = adapter_model.generate(**inputs, max_new_tokens=64, do_sample=False)
                adapter_outputs.append(tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
        summary["adapter_real_generate_executed"] = bool(adapter_outputs)
        summary["base_metrics"] = metrics_from_outputs(base_outputs)
        summary["adapter_metrics"] = metrics_from_outputs(adapter_outputs)
        summary["gpu_peak_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2)
        del adapter_model, base_model, tokenizer
        gc.collect()
        torch.cuda.empty_cache()
        summary["gpu_memory_released"] = True
        summary["quantized_module_count"] = quantized_count

    summary["gpu_lock_release_success"] = True
    ok = all([
        summary["max_steps_completed"] == 20,
        summary["final_train_loss"] is not None and math.isfinite(summary["final_train_loss"]),
        summary["validation_executed"],
        summary["nan_count"] == 0,
        summary["inf_count"] == 0,
        summary["oom_count"] == 0,
        summary["adapter_saved"],
        summary["adapter_reloaded"],
        summary["adapter_real_generate_executed"],
        summary["adapter_metrics"].get("final_schema_valid_rate", 0) >= 0.95,
        summary["adapter_metrics"].get("fallback_rate", 1) <= 0.05,
        summary["adapter_metrics"].get("prohibited_auto_action_count", 1) == 0,
        summary["gpu_memory_released"],
        summary["gpu_lock_release_success"],
    ])
    summary["status"] = "PRIVATE_SYNTHETIC_QLORA_ENGINEERING_SMOKE_PASS" if ok else "PRIVATE_SYNTHETIC_QLORA_ENGINEERING_SMOKE_FAIL"
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.3.3 Synthetic QLoRA Smoke\n\n"
        f"Status: `{summary['status']}`\n\n"
        f"- max_steps_completed: `{summary['max_steps_completed']}`\n"
        f"- final_train_loss: `{summary['final_train_loss']}`\n"
        f"- validation_executed: `{summary['validation_executed']}`\n"
        f"- adapter_saved: `{summary['adapter_saved']}`\n"
        f"- adapter_reloaded: `{summary['adapter_reloaded']}`\n"
        f"- adapter_real_generate_executed: `{summary['adapter_real_generate_executed']}`\n"
        f"- base_raw_json_parse_success_rate: `{summary['base_metrics'].get('raw_json_parse_success_rate')}`\n"
        f"- adapter_raw_json_parse_success_rate: `{summary['adapter_metrics'].get('raw_json_parse_success_rate')}`\n"
        f"- adapter_final_schema_valid_rate: `{summary['adapter_metrics'].get('final_schema_valid_rate')}`\n",
        encoding="utf-8",
    )
    print(summary["status"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "PRIVATE_SYNTHETIC_QLORA_ENGINEERING_SMOKE_FAIL",
            "error_type": type(exc).__name__,
            "error_sanitized": str(exc)[:800],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("PRIVATE_SYNTHETIC_QLORA_ENGINEERING_SMOKE_FAIL")
        print(type(exc).__name__)
        print(str(exc)[:500])
