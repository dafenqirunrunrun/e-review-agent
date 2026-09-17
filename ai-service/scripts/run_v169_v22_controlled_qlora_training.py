from __future__ import annotations

import gc
import json
import math
import shutil
import time

from v169_common import AUDIT, DATA_V22, DOCS, MODEL_DIR, RUN_DIR, TRAINING, nvidia_smi, now, read_json, read_jsonl, write_doc, write_json


CONFIG = {
    "epochs_planned": 1,
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 8,
    "optimizer_steps_planned": 42,
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
    "seed": 1690,
    "bf16": True,
    "fp16": False,
    "quantization": "4-bit NF4 double quant",
    "cpu_offload": False,
    "holdout_path_accepted_by_training": False,
}


def encode_batch(row, tokenizer):
    import torch
    from app.training.completion_only import encode_completion_only_sample

    enc = encode_completion_only_sample(row, tokenizer, max_length=CONFIG["max_length"])
    return {
        "input_ids": torch.tensor([enc.input_ids], dtype=torch.long, device="cuda"),
        "attention_mask": torch.tensor([enc.attention_mask], dtype=torch.long, device="cuda"),
        "labels": torch.tensor([enc.labels], dtype=torch.long, device="cuda"),
    }, sum(1 for label in enc.labels if label != -100)


def validate(model, tokenizer, rows):
    import torch

    model.eval()
    losses = []
    trainable_tokens = 0
    started = time.perf_counter()
    with torch.no_grad():
        for row in rows:
            batch, trainable = encode_batch(row, tokenizer)
            outputs = model(**batch)
            losses.append(float(outputs.loss.detach().float().item()))
            trainable_tokens += trainable
            del outputs, batch
    duration = (time.perf_counter() - started) * 1000
    peak = torch.cuda.max_memory_allocated() / 1024 / 1024
    model.train()
    return {
        "validation_loss": sum(losses) / len(losses),
        "validation_trainable_tokens": trainable_tokens,
        "validation_duration_ms": round(duration, 2),
        "validation_peak_memory_mb": round(peak, 2),
    }


def main() -> None:
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    import bitsandbytes as bnb
    import transformers
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from app.runtime.gpu_gate import gpu_exclusive_gate

    budget = read_json(AUDIT / "v169_v22_qlora_budget.json")
    summary = {
        "generated_at": now(),
        "status": "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_BLOCKED",
        "new_adapter_initialized_from_base": False,
        "old_adapter_loaded": False,
        "epochs_completed": 0,
        "micro_step_count": 0,
        "backward_count": 0,
        "optimizer_step_count": 0,
        "optimizer_steps_planned": CONFIG["optimizer_steps_planned"],
        "validation_run_count": 0,
        "nan_count": 0,
        "inf_count": 0,
        "oom_count": 0,
        "adapter_parameters_updated": False,
        "best_adapter_saved": False,
        "final_adapter_saved": False,
        "holdout_read_during_training": False,
        "gpu_lock_released": False,
        "gpu_memory_released": False,
        "train_log": [],
        "validation_log": [],
    }
    if budget["status"] != "V22_COMPLETION_ONLY_QLORA_BUDGET_PASS":
        summary["blocked_reason"] = "budget did not pass"
        write(summary)
        print(summary["status"])
        return
    train_rows = read_jsonl(DATA_V22 / "train.jsonl")
    validation_rows = read_jsonl(DATA_V22 / "validation.jsonl")
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    for sub in ["checkpoints", "adapter-best", "adapter-final", "optimizer-state", "scheduler-state", "trainer-state", "private-train-logs", "private-validation", "private-holdout-predictions", "private-real-text-robustness"]:
        (RUN_DIR / sub).mkdir(parents=True, exist_ok=True)
    model = tokenizer = optimizer = None
    memory_free_values = []
    try:
        with gpu_exclusive_gate(
            stage="v169-v22-controlled-qlora-training",
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
            torch.manual_seed(CONFIG["seed"])
            torch.cuda.reset_peak_memory_stats()
            tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
            qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
            dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
            model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, **{dtype_key: torch.bfloat16})
            model.config.use_cache = False
            model.gradient_checkpointing_enable()
            summary["quantized_module_count"] = sum(1 for _, module in model.named_modules() if isinstance(module, bnb.nn.Linear4bit))
            model = prepare_model_for_kbit_training(model)
            model = get_peft_model(
                model,
                LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, bias="none", task_type=TaskType.CAUSAL_LM, target_modules=["q_proj", "v_proj"]),
            )
            summary["new_adapter_initialized_from_base"] = True
            initial_sum = sum(float(p.detach().float().sum().item()) for p in model.parameters() if p.requires_grad)
            summary["trainable_parameter_count"] = int(sum(p.numel() for p in model.parameters() if p.requires_grad))
            summary["total_parameter_count"] = int(sum(p.numel() for p in model.parameters()))
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=CONFIG["learning_rate"], weight_decay=CONFIG["weight_decay"])
            model.train()
            optimizer.zero_grad(set_to_none=True)
            accumulation_loss = 0.0
            no_grad_steps = 0
            started = time.perf_counter()
            for idx, row in enumerate(train_rows, start=1):
                batch, trainable_tokens = encode_batch(row, tokenizer)
                outputs = model(**batch)
                loss = outputs.loss
                loss_value = float(loss.detach().float().item())
                summary["nan_count"] += int(math.isnan(loss_value))
                summary["inf_count"] += int(math.isinf(loss_value))
                if not math.isfinite(loss_value):
                    raise RuntimeError("non-finite train loss")
                (loss / CONFIG["gradient_accumulation_steps"]).backward()
                summary["micro_step_count"] += 1
                summary["backward_count"] += 1
                accumulation_loss += loss_value
                do_step = idx % CONFIG["gradient_accumulation_steps"] == 0 or idx == len(train_rows)
                if do_step:
                    grad_norm_sq = 0.0
                    grad_present = False
                    for param in model.parameters():
                        if param.requires_grad and param.grad is not None:
                            grad_present = True
                            grad_norm_sq += float(param.grad.detach().float().norm().item() ** 2)
                    if not grad_present:
                        no_grad_steps += 1
                    else:
                        no_grad_steps = 0
                    if no_grad_steps >= 3:
                        raise RuntimeError("three optimizer steps without gradient")
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    summary["optimizer_step_count"] += 1
                    free_mb, _ = nvidia_smi()
                    if free_mb is not None:
                        memory_free_values.append(free_mb)
                        if free_mb < 200:
                            raise RuntimeError("free memory below 200MB")
                    step_loss = accumulation_loss / CONFIG["gradient_accumulation_steps"]
                    accumulation_loss = 0.0
                    summary["train_log"].append(
                        {
                            "optimizer_step": summary["optimizer_step_count"],
                            "micro_steps": idx,
                            "train_loss": step_loss,
                            "learning_rate": CONFIG["learning_rate"],
                            "gradient_norm": math.sqrt(grad_norm_sq),
                            "trainable_tokens": trainable_tokens,
                            "skipped_step": False,
                            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                            "allocated_memory_mb": round(torch.cuda.memory_allocated() / 1024 / 1024, 2),
                            "reserved_memory_mb": round(torch.cuda.memory_reserved() / 1024 / 1024, 2),
                            "nvidia_free_memory_mb": free_mb,
                        }
                    )
                    if summary["optimizer_step_count"] % CONFIG["eval_steps"] == 0:
                        val = validate(model, tokenizer, validation_rows)
                        if not math.isfinite(val["validation_loss"]):
                            raise RuntimeError("non-finite validation loss")
                        val["step"] = summary["optimizer_step_count"]
                        summary["validation_log"].append(val)
                        summary["validation_run_count"] += 1
                        checkpoint_dir = RUN_DIR / "checkpoints" / f"checkpoint-{summary['optimizer_step_count']}"
                        model.save_pretrained(checkpoint_dir)
                        best = summary.get("best_validation_loss")
                        if best is None or val["validation_loss"] < best - 1e-6:
                            summary["best_validation_loss"] = val["validation_loss"]
                            summary["best_checkpoint_step"] = summary["optimizer_step_count"]
                            best_dir = RUN_DIR / "adapter-best"
                            if best_dir.exists():
                                shutil.rmtree(best_dir)
                            shutil.copytree(checkpoint_dir, best_dir)
                        checkpoints = sorted((RUN_DIR / "checkpoints").glob("checkpoint-*"), key=lambda path: int(path.name.split("-")[-1]))
                        for stale in checkpoints[:-CONFIG["save_total_limit"]]:
                            shutil.rmtree(stale)
                del outputs, loss, batch
            summary["epochs_completed"] = 1
            summary["final_train_loss"] = summary["train_log"][-1]["train_loss"] if summary["train_log"] else None
            final_sum = sum(float(p.detach().float().sum().item()) for p in model.parameters() if p.requires_grad)
            summary["adapter_parameters_updated"] = abs(final_sum - initial_sum) > 1e-6
            model.save_pretrained(RUN_DIR / "adapter-final")
            summary["best_adapter_saved"] = (RUN_DIR / "adapter-best" / "adapter_config.json").exists()
            summary["final_adapter_saved"] = (RUN_DIR / "adapter-final" / "adapter_config.json").exists()
            summary["peak_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2)
            summary["minimum_free_memory_mb"] = min(memory_free_values) if memory_free_values else None
            del model, tokenizer, optimizer
            model = tokenizer = optimizer = None
            gc.collect()
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
            summary["gpu_memory_released"] = True
    except torch.cuda.OutOfMemoryError as exc:
        summary["oom_count"] = 1
        summary["error_type"] = type(exc).__name__
    except Exception as exc:
        summary["error_type"] = type(exc).__name__
        summary["error_sanitized"] = str(exc)[:500]
    finally:
        try:
            del model, tokenizer, optimizer
        except Exception:
            pass
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                if hasattr(torch.cuda, "ipc_collect"):
                    torch.cuda.ipc_collect()
        except Exception:
            pass
        summary["gpu_lock_released"] = True
    pass_conditions = [
        summary["epochs_completed"] == 1,
        summary["optimizer_step_count"] == CONFIG["optimizer_steps_planned"],
        summary["validation_run_count"] == 6,
        summary["nan_count"] == 0,
        summary["inf_count"] == 0,
        summary["oom_count"] == 0,
        summary["adapter_parameters_updated"],
        summary["best_adapter_saved"],
        summary["final_adapter_saved"],
        not summary["holdout_read_during_training"],
        summary["gpu_lock_released"],
        summary["gpu_memory_released"],
    ]
    summary["status"] = "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_PASS" if all(pass_conditions) else "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_BLOCKED"
    write(summary)
    print(summary["status"])


def write(summary: dict) -> None:
    write_json(TRAINING / "v169_v22_training_summary.json", summary)
    write_json(TRAINING / "v169_v22_training_config.json", CONFIG)
    write_doc(
        DOCS / "233_v169_v22_training.md",
        "V1.6.9 V2.2 Controlled Training",
        [
            f"Status: `{summary['status']}`",
            f"- epochs_completed: `{summary.get('epochs_completed')}`",
            f"- optimizer_step_count: `{summary.get('optimizer_step_count')}`",
            f"- validation_run_count: `{summary.get('validation_run_count')}`",
            f"- final_train_loss: `{summary.get('final_train_loss')}`",
            f"- best_validation_loss: `{summary.get('best_validation_loss')}`",
            f"- best_checkpoint_step: `{summary.get('best_checkpoint_step')}`",
            f"- peak_memory_mb: `{summary.get('peak_memory_mb')}`",
            f"- minimum_free_memory_mb: `{summary.get('minimum_free_memory_mb')}`",
        ],
    )


if __name__ == "__main__":
    main()
