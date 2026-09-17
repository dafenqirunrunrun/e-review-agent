import argparse
import gc
import json
import math
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DATA = ROOT.parent / "data-private/synthetic-sft-v1633/train.jsonl"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
OUT = ROOT / "data/private_research/audit/synthetic_qlora_budget.json"
DOC = ROOT / "docs/188_v1633_synthetic_qlora_budget.md"


def child_run(result_path: Path, max_length: int, target_scope: str, lora_r: int):
    sys.path.insert(0, str(ROOT / "ai-service"))
    from app.runtime.gpu_gate import gpu_exclusive_gate

    import torch
    import bitsandbytes as bnb
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRIVATE_SYNTHETIC_QLORA_BUDGET_BLOCKED",
        "quantization_backend": "bitsandbytes",
        "quantization_bits": 4,
        "quantized_module_count": 0,
        "target_modules": [],
        "trainable_parameter_count": 0,
        "total_parameter_count": 0,
        "trainable_parameter_ratio": 0.0,
        "memory_before_load_mb": 0.0,
        "memory_after_load_mb": None,
        "memory_after_forward_mb": None,
        "memory_after_backward_mb": None,
        "peak_memory_mb": None,
        "free_memory_at_peak_mb": None,
        "forward_ms": None,
        "backward_ms": None,
        "loss": None,
        "nan_loss": None,
        "inf_loss": None,
        "gradient_present": False,
        "optimizer_step_success": False,
        "oom_count": 0,
        "unload_success": False,
        "gpu_lock_release_success": False,
        "config": {
            "batch_size": 1,
            "max_length": max_length,
            "gradient_accumulation_steps": 8,
            "gradient_checkpointing": True,
            "use_cache": False,
            "bf16": True,
            "lora_r": lora_r,
            "lora_alpha": 16,
            "target_scope": target_scope,
        },
    }
    try:
        with gpu_exclusive_gate(
            stage="synthetic-qlora-budget",
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
            torch.cuda.reset_peak_memory_stats()
            result["memory_before_load_mb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
            row = json.loads(PRIVATE_DATA.read_text(encoding="utf-8").splitlines()[0])
            text = row["system"] + "\n" + row["user"] + "\n" + row["assistant"]
            tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
            qconfig = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
            load_start = time.perf_counter()
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_DIR,
                local_files_only=True,
                trust_remote_code=True,
                quantization_config=qconfig,
                device_map={"": 0},
                dtype=torch.bfloat16,
            )
            result["model_load_ms"] = round((time.perf_counter() - load_start) * 1000, 2)
            model.config.use_cache = False
            model.gradient_checkpointing_enable()
            result["memory_after_load_mb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
            result["quantized_module_count"] = sum(1 for _, m in model.named_modules() if isinstance(m, bnb.nn.Linear4bit))
            targets = []
            allowed_targets = {"q/k/v/o": {"q_proj", "k_proj", "v_proj", "o_proj"}, "q/v": {"q_proj", "v_proj"}}[target_scope]
            for name, _ in model.named_modules():
                last = name.split(".")[-1]
                if last in allowed_targets and last not in targets:
                    targets.append(last)
            result["target_modules"] = targets
            model = prepare_model_for_kbit_training(model)
            model = get_peft_model(
                model,
                LoraConfig(
                    r=lora_r,
                    lora_alpha=16,
                    lora_dropout=0.05,
                    bias="none",
                    task_type=TaskType.CAUSAL_LM,
                    target_modules=targets,
                ),
            )
            trainable = 0
            total = 0
            for _, param in model.named_parameters():
                count = param.numel()
                total += count
                if param.requires_grad:
                    trainable += count
            result["trainable_parameter_count"] = int(trainable)
            result["total_parameter_count"] = int(total)
            result["trainable_parameter_ratio"] = round(trainable / total, 8) if total else 0.0
            model.train()
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
            labels = inputs["input_ids"].clone()
            forward_start = time.perf_counter()
            outputs = model(**inputs, labels=labels)
            loss = outputs.loss
            result["forward_ms"] = round((time.perf_counter() - forward_start) * 1000, 2)
            result["loss"] = float(loss.detach().float().item())
            result["nan_loss"] = bool(torch.isnan(loss).item())
            result["inf_loss"] = bool(torch.isinf(loss).item())
            result["memory_after_forward_mb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
            backward_start = time.perf_counter()
            loss.backward()
            result["backward_ms"] = round((time.perf_counter() - backward_start) * 1000, 2)
            result["memory_after_backward_mb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
            result["gradient_present"] = any(p.grad is not None for p in model.parameters() if p.requires_grad)
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            result["optimizer_step_success"] = True
            free, _ = torch.cuda.mem_get_info()
            result["peak_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2)
            result["free_memory_at_peak_mb"] = round(free / 1024 / 1024, 2)
            ok = all([
                result["quantized_module_count"] > 0,
                result["trainable_parameter_count"] > 0,
                result["trainable_parameter_ratio"] < 0.05,
                math.isfinite(result["loss"]),
                not result["nan_loss"],
                not result["inf_loss"],
                result["gradient_present"],
                result["optimizer_step_success"],
                result["oom_count"] == 0,
                result["free_memory_at_peak_mb"] >= 300,
            ])
            result["status"] = "PRIVATE_SYNTHETIC_QLORA_BUDGET_PASS" if ok else "PRIVATE_SYNTHETIC_QLORA_BUDGET_BLOCKED"
            del optimizer, outputs, loss, inputs, labels, model, tokenizer
            gc.collect()
            torch.cuda.empty_cache()
            result["unload_success"] = True
    except torch.cuda.OutOfMemoryError as exc:
        result["oom_count"] = 1
        result["error_type"] = type(exc).__name__
        result["error_sanitized"] = str(exc)[:500]
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error_sanitized"] = str(exc)[:800]
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parent_run():
    profiles = [
        {"profile_name": "initial", "max_length": 512, "target_scope": "q/k/v/o", "lora_r": 8},
        {"profile_name": "fallback_max_length_384", "max_length": 384, "target_scope": "q/k/v/o", "lora_r": 8},
        {"profile_name": "fallback_target_qv", "max_length": 384, "target_scope": "q/v", "lora_r": 8},
        {"profile_name": "fallback_rank_4", "max_length": 384, "target_scope": "q/v", "lora_r": 4},
    ]
    attempts = []
    result = None
    for profile in profiles:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            result_path = Path(tmp.name)
        proc = subprocess.run([
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            str(result_path),
            "--max-length",
            str(profile["max_length"]),
            "--target-scope",
            profile["target_scope"],
            "--lora-r",
            str(profile["lora_r"]),
        ], text=True)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["profile_name"] = profile["profile_name"]
        result["child_returncode"] = proc.returncode
        result["gpu_lock_release_success"] = True
        result["unload_success"] = bool(result.get("unload_success")) and proc.returncode == 0
        if result["status"] == "PRIVATE_SYNTHETIC_QLORA_BUDGET_PASS" and not result["unload_success"]:
            result["status"] = "PRIVATE_SYNTHETIC_QLORA_BUDGET_BLOCKED"
        attempts.append({
            "profile_name": result["profile_name"],
            "status": result["status"],
            "max_length": result["config"]["max_length"],
            "target_scope": result["config"]["target_scope"],
            "lora_r": result["config"]["lora_r"],
            "peak_memory_mb": result.get("peak_memory_mb"),
            "free_memory_at_peak_mb": result.get("free_memory_at_peak_mb"),
            "oom_count": result.get("oom_count"),
        })
        if result["status"] == "PRIVATE_SYNTHETIC_QLORA_BUDGET_PASS":
            break
    result["fallback_attempts"] = attempts
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.3.3 Synthetic QLoRA Budget\n\n"
        f"Status: `{result['status']}`\n\n"
        f"- quantized_module_count: `{result['quantized_module_count']}`\n"
        f"- target_modules: `{result['target_modules']}`\n"
        f"- trainable_parameter_count: `{result['trainable_parameter_count']}`\n"
        f"- trainable_parameter_ratio: `{result['trainable_parameter_ratio']}`\n"
        f"- forward_ms: `{result['forward_ms']}`\n"
        f"- backward_ms: `{result['backward_ms']}`\n"
        f"- loss: `{result['loss']}`\n"
        f"- peak_memory_mb: `{result['peak_memory_mb']}`\n"
        f"- free_memory_at_peak_mb: `{result['free_memory_at_peak_mb']}`\n"
        f"- oom_count: `{result['oom_count']}`\n"
        f"- unload_success: `{result['unload_success']}`\n",
        encoding="utf-8",
    )
    print(result["status"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--target-scope", choices=["q/k/v/o", "q/v"], default="q/k/v/o")
    parser.add_argument("--lora-r", type=int, default=8)
    args = parser.parse_args()
    if args.child:
        child_run(Path(args.child), args.max_length, args.target_scope, args.lora_r)
    else:
        parent_run()


if __name__ == "__main__":
    main()
