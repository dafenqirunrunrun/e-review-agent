import gc
import json
import math
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / ("data" + "-private")
PRIVATE_DATA = PRIVATE_ROOT / "synthetic-sft-v1633"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-qlora-v164-controlled"
MODEL_DIR = ROOT.parent / "models/Qwen3-1.7B"
SUMMARY = ROOT / "data/private_research/training/v164_controlled_training_summary.json"
CONFIG_OUT = ROOT / "data/private_research/training/v164_controlled_training_config.json"
MEMORY_OUT = ROOT / "data/private_research/training/v164_memory_summary.json"
DOC = ROOT / "docs/188_v164_controlled_synthetic_qlora_training.md"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def nvidia_smi():
    import subprocess

    proc = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, None
    parts = [part.strip() for part in proc.stdout.splitlines()[0].split(",")]
    return int(parts[0]), int(parts[1])


def memory_snapshot(label: str, step: int | None):
    import torch

    free_mb, util = nvidia_smi()
    allocated = torch.cuda.memory_allocated() / 1024 / 1024
    reserved = torch.cuda.memory_reserved() / 1024 / 1024
    max_allocated = torch.cuda.max_memory_allocated() / 1024 / 1024
    max_reserved = torch.cuda.max_memory_reserved() / 1024 / 1024
    return {
        "label": label,
        "step": step,
        "memory_allocated_mb": round(allocated, 2),
        "memory_reserved_mb": round(reserved, 2),
        "max_memory_allocated_mb": round(max_allocated, 2),
        "max_memory_reserved_mb": round(max_reserved, 2),
        "nvidia_smi_free_memory_mb": free_mb,
        "nvidia_smi_utilization": util,
        "fragmentation_estimate_mb": round(reserved - allocated, 2),
    }


def validate(model, tokenizer, rows, config):
    import torch

    model.eval()
    losses = []
    token_count = 0
    started = time.perf_counter()
    with torch.no_grad():
        for row in rows:
            text = row["system"] + "\n" + row["user"] + "\n" + row["assistant"]
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=config["max_length"])
            token_count += int(inputs["input_ids"].numel())
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
            outputs = model(**inputs, labels=inputs["input_ids"])
            losses.append(float(outputs.loss.detach().float().item()))
            del outputs, inputs
    gc.collect()
    torch.cuda.empty_cache()
    model.train()
    return {
        "validation_loss": sum(losses) / len(losses),
        "validation_token_count": token_count,
        "validation_duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "validation_peak_memory_mb": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2),
    }


def main():
    sys.path.insert(0, str(ROOT / "ai-service"))
    from app.runtime.gpu_gate import gpu_exclusive_gate

    import torch
    import bitsandbytes as bnb
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    train_rows = read_jsonl(PRIVATE_DATA / "train.jsonl")
    validation_rows = read_jsonl(PRIVATE_DATA / "validation.jsonl")
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    for sub in ["checkpoints", "adapter-best", "adapter-final", "optimizer-state", "scheduler-state", "trainer-state", "private-logs", "private-validation", "private-holdout-predictions"]:
        (RUN_DIR / sub).mkdir(parents=True, exist_ok=True)

    config = {
        "epochs_planned": 1,
        "train_count": len(train_rows),
        "validation_count": len(validation_rows),
        "holdout_count": 42,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 8,
        "optimizer_steps_expected": math.ceil(len(train_rows) / 8),
        "max_length": 384,
        "learning_rate": 1e-4,
        "warmup_ratio": 0.0,
        "weight_decay": 0.0,
        "eval_steps": 7,
        "save_steps": 7,
        "save_total_limit": 2,
        "lora_target_modules": ["q_proj", "v_proj"],
        "lora_r": 8,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "seed": 1640,
        "bf16": True,
        "quantization": "4-bit NF4 double quant",
        "cpu_offload": False,
        "holdout_used_during_training": False,
        "smoke_adapter_used": False,
    }
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PRIVATE_SYNTHETIC_QLORA_CONTROLLED_TRAIN_FAIL",
        "epochs_completed": 0,
        "micro_step_count": 0,
        "backward_count": 0,
        "optimizer_step_count": 0,
        "optimizer_steps_expected": config["optimizer_steps_expected"],
        "final_train_loss": None,
        "best_validation_loss": None,
        "best_checkpoint_step": None,
        "validation_run_count": 0,
        "nan_count": 0,
        "inf_count": 0,
        "oom_count": 0,
        "adapter_parameters_updated": False,
        "best_adapter_saved": False,
        "final_adapter_saved": False,
        "memory_sentinel_status": "MEMORY_SENTINEL_PASS",
        "minimum_free_memory_mb": None,
        "peak_memory_mb": None,
        "trainable_parameter_count": 0,
        "total_parameter_count": 0,
        "trainable_parameter_ratio": 0.0,
        "quantized_module_count": 0,
        "target_modules": config["lora_target_modules"],
        "gpu_lock_valid": False,
        "gpu_memory_released": False,
        "holdout_sealed": True,
        "smoke_adapter_excluded": True,
        "train_log": [],
        "validation_log": [],
    }
    memory_log = []
    try:
        with gpu_exclusive_gate(
            stage="v164-controlled-synthetic-qlora-train",
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
            summary["gpu_lock_valid"] = True
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
            summary["quantized_module_count"] = sum(1 for _, m in model.named_modules() if isinstance(m, bnb.nn.Linear4bit))
            memory_log.append(memory_snapshot("after_model_load", None))
            model = prepare_model_for_kbit_training(model)
            model = get_peft_model(
                model,
                LoraConfig(
                    r=config["lora_r"],
                    lora_alpha=config["lora_alpha"],
                    lora_dropout=config["lora_dropout"],
                    bias="none",
                    task_type=TaskType.CAUSAL_LM,
                    target_modules=config["lora_target_modules"],
                ),
            )
            trainable = 0
            total = 0
            initial_trainable_sum = 0.0
            for _, param in model.named_parameters():
                n = param.numel()
                total += n
                if param.requires_grad:
                    trainable += n
                    initial_trainable_sum += float(param.detach().float().sum().item())
            summary["trainable_parameter_count"] = int(trainable)
            summary["total_parameter_count"] = int(total)
            summary["trainable_parameter_ratio"] = round(trainable / total, 8)
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=config["learning_rate"], weight_decay=config["weight_decay"])
            model.train()
            accumulation_loss = 0.0
            optimizer_step = 0
            started = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            for idx, row in enumerate(train_rows, start=1):
                text = row["system"] + "\n" + row["user"] + "\n" + row["assistant"]
                inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=config["max_length"])
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
                outputs = model(**inputs, labels=inputs["input_ids"])
                loss = outputs.loss
                loss_value = float(loss.detach().float().item())
                summary["nan_count"] += int(math.isnan(loss_value))
                summary["inf_count"] += int(math.isinf(loss_value))
                (loss / config["gradient_accumulation_steps"]).backward()
                summary["micro_step_count"] += 1
                summary["backward_count"] += 1
                accumulation_loss += loss_value
                do_step = idx % config["gradient_accumulation_steps"] == 0 or idx == len(train_rows)
                if do_step:
                    grad_norm_sq = 0.0
                    grad_present = False
                    for param in model.parameters():
                        if param.requires_grad and param.grad is not None:
                            grad_present = True
                            grad_norm_sq += float(param.grad.detach().float().norm().item() ** 2)
                    if not grad_present:
                        raise RuntimeError("gradient missing before optimizer step")
                    grad_norm = math.sqrt(grad_norm_sq)
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    optimizer_step += 1
                    summary["optimizer_step_count"] = optimizer_step
                    step_loss = accumulation_loss / config["gradient_accumulation_steps"]
                    accumulation_loss = 0.0
                    snap = memory_snapshot(f"step_{optimizer_step}", optimizer_step)
                    memory_log.append(snap)
                    if snap["nvidia_smi_free_memory_mb"] is not None and snap["nvidia_smi_free_memory_mb"] < 200:
                        summary["memory_sentinel_status"] = "PRIVATE_SYNTHETIC_QLORA_CONTROLLED_TRAIN_BLOCKED_MEMORY"
                        raise RuntimeError("free memory below 200MB")
                    summary["train_log"].append({
                        "step": optimizer_step,
                        "epoch_fraction": round(idx / len(train_rows), 6),
                        "train_loss": step_loss,
                        "learning_rate": config["learning_rate"],
                        "gradient_norm": grad_norm,
                        "skipped_step": False,
                        "nan_loss": math.isnan(step_loss),
                        "inf_loss": math.isinf(step_loss),
                        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                        "peak_memory_mb": snap["max_memory_allocated_mb"],
                    })
                    if optimizer_step in {1, 5, 10, 20, 30, 42}:
                        memory_log.append(memory_snapshot(f"sentinel_step_{optimizer_step}", optimizer_step))
                    if optimizer_step % config["eval_steps"] == 0:
                        memory_log.append(memory_snapshot(f"before_validation_{optimizer_step}", optimizer_step))
                        val_result = validate(model, tokenizer, validation_rows, config)
                        val_result["step"] = optimizer_step
                        summary["validation_log"].append(val_result)
                        summary["validation_run_count"] += 1
                        memory_log.append(memory_snapshot(f"after_validation_{optimizer_step}", optimizer_step))
                        checkpoint_dir = RUN_DIR / "checkpoints" / f"checkpoint-{optimizer_step}"
                        memory_log.append(memory_snapshot(f"before_checkpoint_{optimizer_step}", optimizer_step))
                        model.save_pretrained(checkpoint_dir)
                        memory_log.append(memory_snapshot(f"after_checkpoint_{optimizer_step}", optimizer_step))
                        current_best = summary["best_validation_loss"]
                        if current_best is None or val_result["validation_loss"] < current_best - 1e-6:
                            summary["best_validation_loss"] = val_result["validation_loss"]
                            summary["best_checkpoint_step"] = optimizer_step
                            best_dir = RUN_DIR / "adapter-best"
                            if best_dir.exists():
                                shutil.rmtree(best_dir)
                            shutil.copytree(checkpoint_dir, best_dir)
                        old = sorted((RUN_DIR / "checkpoints").glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1]))
                        for stale in old[:-config["save_total_limit"]]:
                            shutil.rmtree(stale)
                del outputs, inputs, loss
            summary["epochs_completed"] = 1
            summary["final_train_loss"] = summary["train_log"][-1]["train_loss"] if summary["train_log"] else None
            final_sum = 0.0
            for _, param in model.named_parameters():
                if param.requires_grad:
                    final_sum += float(param.detach().float().sum().item())
            summary["adapter_parameters_updated"] = abs(final_sum - initial_trainable_sum) > 1e-6
            final_dir = RUN_DIR / "adapter-final"
            if final_dir.exists():
                shutil.rmtree(final_dir)
            model.save_pretrained(final_dir)
            summary["final_adapter_saved"] = (final_dir / "adapter_config.json").exists()
            summary["best_adapter_saved"] = (RUN_DIR / "adapter-best" / "adapter_config.json").exists()
            summary["peak_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2)
            frees = [item["nvidia_smi_free_memory_mb"] for item in memory_log if item["nvidia_smi_free_memory_mb"] is not None]
            summary["minimum_free_memory_mb"] = min(frees) if frees else None
            del optimizer, model, tokenizer
            gc.collect()
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
            summary["gpu_memory_released"] = True
    except torch.cuda.OutOfMemoryError as exc:
        summary["oom_count"] = 1
        summary["error_type"] = type(exc).__name__
        summary["error_sanitized"] = str(exc)[:500]
    except Exception as exc:
        summary["error_type"] = type(exc).__name__
        summary["error_sanitized"] = str(exc)[:800]
    pass_conditions = [
        summary["epochs_completed"] == 1,
        summary["optimizer_step_count"] == config["optimizer_steps_expected"],
        summary["validation_run_count"] >= 6,
        summary["nan_count"] == 0,
        summary["inf_count"] == 0,
        summary["oom_count"] == 0,
        summary["adapter_parameters_updated"],
        summary["best_adapter_saved"],
        summary["final_adapter_saved"],
        summary["gpu_lock_valid"],
        summary["gpu_memory_released"],
        summary["memory_sentinel_status"] == "MEMORY_SENTINEL_PASS",
    ]
    summary["status"] = "PRIVATE_SYNTHETIC_QLORA_CONTROLLED_TRAIN_PASS" if all(pass_conditions) else "PRIVATE_SYNTHETIC_QLORA_CONTROLLED_TRAIN_FAIL"
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CONFIG_OUT.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MEMORY_OUT.write_text(json.dumps({"memory_log": memory_log, "memory_sentinel_status": summary["memory_sentinel_status"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.4 Controlled Synthetic QLoRA Training\n\n"
        f"Status: `{summary['status']}`\n\n"
        f"- epochs_completed: `{summary['epochs_completed']}`\n"
        f"- optimizer_step_count: `{summary['optimizer_step_count']}`\n"
        f"- final_train_loss: `{summary['final_train_loss']}`\n"
        f"- best_validation_loss: `{summary['best_validation_loss']}`\n"
        f"- best_checkpoint_step: `{summary['best_checkpoint_step']}`\n"
        f"- validation_run_count: `{summary['validation_run_count']}`\n"
        f"- minimum_free_memory_mb: `{summary['minimum_free_memory_mb']}`\n"
        f"- peak_memory_mb: `{summary['peak_memory_mb']}`\n"
        f"- adapter_parameters_updated: `{summary['adapter_parameters_updated']}`\n",
        encoding="utf-8",
    )
    print(summary["status"])


if __name__ == "__main__":
    main()
